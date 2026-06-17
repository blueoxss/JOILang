# cloud_judge/judge_gpt.py
"""
사용자 정의 Custom GPT Judge (예: GPT-4o) - 단일 쌍 평가기

- LangSmith Criteria(메인) 보조 Judge로 쓰기 좋은 JSON 점수(0~1) 반환
- 라이브러리 미설치/키 미설정 시 안전하게 건너뜀
- 응답 JSON을 안전 파싱하고 점수를 0~1로 클램프
- 두 인터페이스 제공:
    1) run_custom_gpt_judge(candidate_code, ground_truth_code, command) -> {"score": float, "comment": str}
    2) score_pair(command, candidate_code, gt_code) -> {"score": float, "comment": str}  # 호환용
"""

from __future__ import annotations
import json
import importlib
import os
from pathlib import Path
import re
import sys
import time
from typing import Dict, Any, List

try:
    from . import config  # CUSTOM_GPT_JUDGE_MODEL, CUSTOM_GPT_JUDGE_SYSTEM_PROMPT 등을 읽음
except ImportError:
    import config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# OpenAI 클라이언트 준비(없어도 다른 모드 실행 가능하도록 방어)
_OPENAI_AVAILABLE = False
_OpenAIClient = None  # type: ignore

try:
    from openai import OpenAI, APITimeoutError, APIConnectionError, RateLimitError  # type: ignore
    _OpenAIClient = OpenAI
    _OPENAI_AVAILABLE = True
except Exception as _e:
    # 라이브러리 미존재 또는 초기 임포트 실패 시, 이후 함수에서 우아하게 건너뛰도록 플래그만 설정
    print(f"⚠️ Custom GPT Judge: openai 라이브러리 임포트 실패: {_e}")
    _OPENAI_AVAILABLE = False

    class APITimeoutError(Exception):
        """Fallback timeout error (openai 미설치 시 사용)"""
        pass

    class APIConnectionError(Exception):
        """Fallback connection error (openai 미설치 시 사용)"""
        pass

    class RateLimitError(Exception):
        """Fallback rate limit error (openai 미설치 시 사용)"""
        pass

    # 더미 클라이언트(실제 호출은 수행하지 않음)
    class OpenAI:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise RuntimeError("OpenAI client unavailable (openai package not installed)")


def _build_openai_client(context: str):
    api_key = config.require_openai_api_key(context)
    kwargs = {"api_key": api_key}
    base_url = getattr(config, "get_openai_base_url", lambda: os.environ.get("OPENAI_BASE_URL"))()
    if base_url:
        kwargs["base_url"] = base_url
    return _OpenAIClient(**kwargs)

def _clamp01(x) -> float:
    try: v = float(x)
    except Exception: return 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

def _strip_fence(s: str) -> str:
    if not isinstance(s, str): return ""
    t = s.strip()
    if t.startswith("```json"): t = t[7:]
    if t.startswith("```"): t = t[3:]
    if t.endswith("```"): t = t[:-3]
    return t.strip()


def _extract_json_object(raw: str) -> Dict[str, Any]:
    txt = _strip_fence(raw)
    try:
        data = json.loads(txt)
        return data if isinstance(data, dict) else {}
    except Exception:
        pass

    start = txt.find("{")
    end = txt.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            data = json.loads(txt[start:end + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def _normalize_text_for_match(text: str) -> str:
    if not isinstance(text, str):
        return ""
    normalized = text.strip().lower()
    normalized = re.sub(r"[\s\.,!?\"'“”‘’`~:;_\-/\\()\[\]{}]+", "", normalized)
    return normalized


def _build_demo_korean_rewrite_prompt(code: str) -> str:
    return f"""You are a Korean linguist master.
Please rewrite the following JOI Lang code into a precise, clear Korean command up to 3 lines.

** Device and Service Range Specification (with Logical Conditions): **
- ✅ First, extract and display the following [Tag Mapping] before generating the final sentence:
  - For each expression like `(#Curtain).curtain_close()` or `all(#Curtain).curtain_close()`, extract:
    - Tag: `#Curtain`
    - Modifier: `all`, `any`, or `none` (if neither is present)

# [Tag Mapping] (must always show this section):
- Tag: `#Curtain`, Modifier: `none` → say: "임의의 커튼"
- Tag: `#Light`, Modifier: `all` → say: "모든 조명"
- Tag: `#Window`, Modifier: `any` → say: "전체 창문 중 하나라도"

- ✅ Use the following mappings for translation:
  - If the code uses `all(...)`: → say “모든 [장치명]”
  - If the code uses `any(...)`: → say “전체 중 하나의 [장치명]”
  - If the code uses just `(#Device)` with no `all` or `any`: → say “임의의 [장치명]”

- ✅ Apply this logic to both **conditions** and **actions**

---

**Make sure to satisfy ALL of the following conditions:**
- ✅ Always **follow the actual execution order** of the code.
- ✅ If the command includes `break`, it **must be translated as a loop termination** (e.g., "반복을 종료한다").
- ✅ Use temporal connectors like:
  > “먼저 ~하고, 그 다음 ~하면, 이후 ~한다”
  to clearly express **time and logic flow**.

- ❗ Absolutely **no hallucination**:
  Only use devices, conditions, or services that are **explicitly present in the JOI code**.
  Do NOT hallucinate or assume anything beyond what's shown in the JOI code. Use only what is explicitly provided.

**Only output the final sentence. Do not output anything else.**
- Do not show [Tag Mapping], labels, comments, or explanation.
- Only print the natural Korean sentence generated from the JOI Lang code below.
**Do not print labels or sections like [Tag Mapping] or [Final Rewritten...].**
[Final Rewritten Natural Korean Command (with correct logic order)]:
(✅ Only the **Korean sentence generated below** should be shown to the user.)

---

JOI Lang Code:
{code}

Generate the final Korean sentence here.
"""

def _parse_list_json(raw: str) -> List[dict]:
    """
    cloud_similarity 형식: JSON 리스트 반환.
    파싱 실패 시 빈 리스트 반환.
    """
    try:
        txt = _strip_fence(raw)
        data = json.loads(txt)
        if isinstance(data, list): return data
        if isinstance(data, dict): return [data]
        return []
    except Exception as e:
        print(f"Custom GPT Judge Parse Error: {e}\nRAW (head): {raw[:400]}")
        return []

def _build_batch_message(candidate_code: str, gt_code: str) -> str:
    """
    cloud_similarity 'user_content' 형식으로 단일 페어 구성
    """
    return f"Generated Code {candidate_code}\nGround Truth Code {gt_code}\n"

def _build_model_input(candidate_code: str, gt_code: str) -> Dict[str, Any]:
    sys_prompt = getattr(config, "CUSTOM_GPT_JUDGE_BATCH_PROMPT", None) or getattr(
        config, "CUSTOM_GPT_JUDGE_SYSTEM_PROMPT",
        "You are a strict JSON judge. Return a JSON list with one object containing {cloud_similarity_gpt4o, explanation}."
    )

    model_name = getattr(config, "CUSTOM_GPT_JUDGE_MODEL", "gpt-4o")
    user_content = _build_batch_message(candidate_code, gt_code)
    return {
        "model": model_name,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ],
        # batch 프롬프트는 리스트(JSON)를 요구하므로 일반 텍스트 모드로 둔다.
        # 모델이 펜스를 붙여도 파서가 제거한다.
    }

def _call_once(client, model_input: Dict[str, Any]) -> Dict[str, Any]:
    resp = client.chat.completions.create(**model_input, timeout=60.0)
    msg = (resp.choices[0].message.content or "").strip()
    return {"message": msg}

def _generate_with_retry(client, model_input: Dict[str, Any]) -> Dict[str, Any]:
    if not _OPENAI_AVAILABLE:
        return {"error": "openai library not available", "message": "[]"}
    max_retries = 3
    base_delay = 8
    for attempt in range(1, max_retries + 1):
        try:
            return _call_once(client, model_input)
        except (APITimeoutError, APIConnectionError, RateLimitError) as e:
            print(f"Custom GPT Judge transient error ({type(e).__name__}): {e}. retry {attempt}/{max_retries}")
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** (attempt - 1)))
            else:
                return {"error": f"{type(e).__name__}: {e}", "message": "[]"}
        except Exception as e:
            print(f"Custom GPT Judge unexpected error: {e}")
            return {"error": str(e), "message": "[]"}
    return {"error": "unknown failure", "message": "[]"}


def reverse_translate_code_to_korean(
    candidate_code: str,
    connected_devices: Dict[str, Any] | None = None,
    other_params: Any = None,
) -> Dict[str, Any]:
    if not isinstance(candidate_code, str) or not candidate_code.strip():
        return {
            "translated_sentence": "",
            "comment": "skipped (empty code)",
            "translation_model": "",
        }

    if not _OPENAI_AVAILABLE:
        return {
            "translated_sentence": "",
            "comment": "skipped (openai library not available)",
            "translation_model": "",
        }

    try:
        client = _build_openai_client("Custom GPT reconversion translator")
    except RuntimeError:
        raise
    except Exception as e:
        return {
            "translated_sentence": "",
            "comment": f"skipped (openai init failed: {e})",
            "translation_model": "",
        }

    try:
        config_loader_module = importlib.import_module("gpt_mg.version0_6_reconverted.config_loader")
        load_version_config = getattr(config_loader_module, "load_version_config")
        _, model_input = load_version_config(
            _build_demo_korean_rewrite_prompt(candidate_code),
            connected_devices=connected_devices or {},
            other_params=other_params,
        )
        translation_model = str(model_input.get("model", ""))
        resp = client.chat.completions.create(**model_input)
        translated_sentence = (resp.choices[0].message.content or "").strip()
        if not translated_sentence:
            return {
                "translated_sentence": "",
                "comment": "empty translation",
                "translation_model": translation_model,
            }
        return {
            "translated_sentence": translated_sentence,
            "comment": "",
            "translation_model": translation_model,
        }
    except Exception as e:
        return {
            "translated_sentence": "",
            "comment": f"error ({e})",
            "translation_model": "",
        }


def judge_reconverted_sentence_equivalence(
    original_sentence: str,
    reconverted_sentence: str,
    original_sentence_kor: str = "",
) -> Dict[str, Any]:
    original_sentence = (original_sentence or "").strip()
    original_sentence_kor = (original_sentence_kor or "").strip()
    reconverted_sentence = (reconverted_sentence or "").strip()

    if not reconverted_sentence:
        return {"score": 0.0, "same": False, "comment": "skipped (empty reconverted sentence)"}

    preferred_original = original_sentence_kor or original_sentence
    if preferred_original and _normalize_text_for_match(preferred_original) == _normalize_text_for_match(reconverted_sentence):
        return {"score": 1.0, "same": True, "comment": "exact_match_after_normalization"}

    if not _OPENAI_AVAILABLE:
        return {"score": 0.0, "same": False, "comment": "skipped (openai library not available)"}

    try:
        client = _build_openai_client("Custom GPT reconverted equivalence judge")
    except RuntimeError:
        raise
    except Exception as e:
        return {"score": 0.0, "same": False, "comment": f"skipped (openai init failed: {e})"}

    model_input = {
        "model": getattr(config, "CUSTOM_GPT_JUDGE_MODEL", "gpt-4o"),
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict bilingual equivalence judge for JOI natural-language instructions. "
                    "Return JSON only. Mark same=true only when the two instructions request the same "
                    "devices, actions, conditions, time constraints, quantities, repetition, and ordering. "
                    "Ignore wording differences only."
                ),
            },
            {
                "role": "user",
                "content": f"""
Compare the original instruction and the reverse-converted Korean instruction.

Original instruction (exact):
{original_sentence or "(empty)"}

Original instruction Korean reference (if available):
{original_sentence_kor or "(none)"}

Reverse-converted Korean instruction from code:
{reconverted_sentence}

Rules:
- `same` must be true only if the requested behavior is effectively identical.
- Any missing or extra device, service, condition, delay, cron/period, count, or ordering should make `same` false.
- Surface wording differences or harmless paraphrases are allowed.

Return JSON only:
{{
  "same": true,
  "score": 1.0,
  "reason": "short explanation"
}}
""".strip(),
            },
        ],
    }
    logs = _generate_with_retry(client, model_input)
    if "error" in logs:
        return {"score": 0.0, "same": False, "comment": logs["error"]}

    parsed = _extract_json_object(logs.get("message", "{}"))
    same_raw = parsed.get("same", False)
    if isinstance(same_raw, bool):
        same = same_raw
    else:
        same = str(same_raw).strip().lower() in {"1", "true", "yes", "same"}
    comment = parsed.get("reason", "")
    if not isinstance(comment, str):
        comment = str(comment)

    score_raw = parsed.get("score", 1.0 if same else 0.0)
    try:
        score = float(score_raw)
    except Exception:
        score = 1.0 if same else 0.0
    score = 1.0 if same else 0.0

    return {"score": score, "same": same, "comment": comment}


def run_reconverted_fallback_judge(
    candidate_code: str,
    original_sentence: str,
    original_sentence_kor: str = "",
    connected_devices: Dict[str, Any] | None = None,
    other_params: Any = None,
) -> Dict[str, Any]:
    translated = reverse_translate_code_to_korean(
        candidate_code=candidate_code,
        connected_devices=connected_devices,
        other_params=other_params,
    )
    translated_sentence = translated.get("translated_sentence", "")
    if not translated_sentence:
        return {
            "score": 0.0,
            "same": False,
            "comment": translated.get("comment", "translation_failed"),
            "translated_sentence": "",
            "translation_model": translated.get("translation_model", ""),
            "translation_comment": translated.get("comment", ""),
        }

    judged = judge_reconverted_sentence_equivalence(
        original_sentence=original_sentence,
        reconverted_sentence=translated_sentence,
        original_sentence_kor=original_sentence_kor,
    )
    return {
        "score": judged.get("score", 0.0),
        "same": judged.get("same", False),
        "comment": judged.get("comment", ""),
        "translated_sentence": translated_sentence,
        "translation_model": translated.get("translation_model", ""),
        "translation_comment": translated.get("comment", ""),
    }

# ------------- public API -------------

def run_custom_gpt_judge(candidate_code: str, ground_truth_code: str, command: str) -> Dict[str, Any]:
    """
    Custom GPT Judge 실행(단일 쌍).
    - cloud_similarity.py의 Batch 프롬프트를 유지
    - user_content에는 페어 1개만 포함
    - 모델 응답(JSON 리스트) 첫 항목을 사용
    반환: {"score": float, "comment": str}
    """
    if not _OPENAI_AVAILABLE:
        return {"score": 0.0, "comment": "skipped (openai library not available)"}

    try:
        client = _build_openai_client("Custom GPT semantic judge")
    except RuntimeError:
        raise
    except Exception as e:
        return {"score": 0.0, "comment": f"skipped (openai init failed: {e})"}

    model_input = _build_model_input(candidate_code=candidate_code, gt_code=ground_truth_code)
    logs = _generate_with_retry(client, model_input)
    if "error" in logs:
        return {"score": 0.0, "comment": logs["error"]}

    items = _parse_list_json(logs.get("message", "[]"))
    if not items:
        return {"score": 0.0, "comment": "parse_failed_or_empty"}

    first = items[0] if isinstance(items[0], dict) else {}
    score = _clamp01(first.get("cloud_similarity_gpt4o", 0.0))
    comment = first.get("explanation", "")
    if not isinstance(comment, str):
        comment = str(comment)

    return {"score": score, "comment": comment}

# 호환용 시그니처
def score_pair(command: str, candidate_code: str, gt_code: str) -> Dict[str, Any]:
    return run_custom_gpt_judge(candidate_code=candidate_code, ground_truth_code=gt_code, command=command)
