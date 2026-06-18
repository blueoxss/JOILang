"""
JOI Lang cloud semantic evaluator.

Modes:
- det: legacy local deterministic evaluator for debugging/backward compatibility.
- lang: local CLI multi-criteria semantic judge via ChatOpenAI/LangChain.
- gpt: custom GPT holistic semantic similarity judge with optional reconverted
  Korean fallback when GT code is unavailable.
- hybrid: legacy hybrid mode that expands to det+lang+gpt. This is separate
  from the official strict DET benchmark.

Official benchmark metrics come from
gpt_mg/version0_15_update20260413/scripts/run_benchmark.py and its strict DET
reports. Official rich feedback is produced by
utils/merge_strict_det_with_cloud_judges.py, which merges strict DET reports
with this module's lang/gpt result CSV.

CLI:
  python main_evaluator.py [modes] [family] {row_index} [model_version_path]
  python main_evaluator.py [modes] [family] [model_version_path] [--out-dir DIR]

Supported families: joi, cap, qwen.
"""
import pandas as pd
import numpy as np
import json
import sys
import os
import ast  # CSV 파싱용
from datetime import datetime
from tqdm import tqdm
import importlib  # 동적 임포트용
import time  # 시간 측정용
import re  # 파일명 안전화용
from typing import Any, Dict, Optional, List, Union  # 타입 힌팅용
import traceback  # 상세 오류 출력용
from pathlib import Path  # 경로 처리용

CURRENT_FILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_FILE_DIR.parents[1]
PARENT_DIR = REPO_ROOT

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(CURRENT_FILE_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_FILE_DIR))

try:
    from cloud_judge import config
except ImportError:
    from eval_tools import config

def _label_overall_final(score: Any) -> str:
    """overall_final 점수로 최종 라벨(fail/partial/pass) 반환."""
    OVERALL_FINAL_FAIL_LT = getattr(config, "OVERALL_FINAL_FAIL_LT", 0.5)
    OVERALL_FINAL_PARTIAL_LT = getattr(config, "OVERALL_FINAL_PARTIAL_LT", 0.85)
    try:
        s = float(score)
    except Exception:
        return ""  # 점수 없음 → 빈 값
    if s < OVERALL_FINAL_FAIL_LT:
        return "fail"
    if s < OVERALL_FINAL_PARTIAL_LT:
        return "partial"
    return "pass"


def _row_matches_selected_cats(row_index_int: int, selected_cats):
    """row_index가 selected_cats 조건을 만족하는지 확인. 만족하지 않으면 False."""
    if not selected_cats:
        return True
    try:
        data_path = _resolve_project_path(config.DATA_FILE_PATH)
        df = pd.read_csv(str(data_path), encoding="utf-8-sig")
        if not (0 <= row_index_int < len(df)):
            return False
        val = pd.to_numeric(df.iloc[row_index_int].get("category_analysis"), errors="coerce")
        if pd.isna(val):
            return False
        return int(val) in set(selected_cats)
    except Exception:
        return False
    
def _extract_category_value(row) -> Optional[int]:
    try:
        cat_val_raw = row.get("category_analysis", None)
        cat_val_num = pd.to_numeric(cat_val_raw, errors="coerce")
        if pd.notna(cat_val_num):
            return int(cat_val_num)
    except Exception:
        pass
    return None

def _parse_cat_values(spec: str):
    """
    '1,3,5', '1-3, 7', '1 2 3' 등 다양한 표현을 받아
    중복 제거된 오름차순 정수 리스트로 반환.
    """
    if not isinstance(spec, str):
        return []
    s = spec.strip()
    if not s:
        return []
    # 쉼표/세미콜론/여러 공백을 공백 하나로 통일
    s = s.replace(",", " ").replace(";", " ")
    s = re.sub(r"\s+", " ", s).strip()

    out = set()
    for tok in s.split(" "):
        tok = tok.strip()
        if not tok:
            continue
        # 범위 표기  a-b
        m = re.fullmatch(r"(\d+)\-(\d+)", tok)
        if m:
            a = int(m.group(1)); b = int(m.group(2))
            lo, hi = (a, b) if a <= b else (b, a)
            for v in range(lo, hi + 1):
                out.add(v)
            continue
        # 단일 숫자
        if tok.isdigit():
            out.add(int(tok))
            continue
        # 그 외는 무시
    return sorted(out)

def _filter_df_by_categories(df: pd.DataFrame, selected_cats):
    """
    category_analysis 열을 숫자로 변환한 뒤 selected_cats(Set[int])에 포함되는 행만 남김.
    반환: (filtered_df, positions_list)
    positions_list는 원본 CSV 기준의 위치 인덱스(df.index)를 돌려줌.
    """
    if not selected_cats:
        return df, df.index.tolist()
    if "category_analysis" not in df.columns:
        print("⚠️ Warning: 'category_analysis' column not found. Category filter ignored.")
        return df, df.index.tolist()

    cat_series = pd.to_numeric(df["category_analysis"], errors="coerce").astype("Int64")
    mask = cat_series.isin(list(selected_cats))
    df_f = df[mask]
    pos = df_f.index.tolist()
    print(f"  ▶ Category filter applied: {sorted(selected_cats)} "
          f"(kept {len(df_f)}/{len(df)} rows)")
    return df_f, pos


def _resolve_project_path(path_like: str) -> Path:
    p = Path(path_like)
    return p if p.is_absolute() else (CURRENT_FILE_DIR / p).resolve()

# ---------- 유틸 ----------
def _normalize_connected_devices(raw):
    # 기대 형태: dict[str, {category: str, tags: list[str], ...}]
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        # 리스트로 들어오면 인덱스 키로 dict 변환 (CAP의 .values()가 동작하도록)
        return {str(i): v for i, v in enumerate(raw) if isinstance(v, dict)}
    # 문자열인 경우 ast.literal_eval 등 상위에서 처리됨. 여기선 안전하게 빈 dict
    return {}

def _extract_json_from_text(text: str) -> str:
    """코드블록 펜스(```json ... ```)를 제거하고 내용만 반환."""
    if not isinstance(text, str):
        return ""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 1)[1]
        if "\n" in s:
            s = s.split("\n", 1)[1]
        if "```" in s:
            s = s.rsplit("```", 1)[0]
        s = s.strip()
    return s

def _compact_json_for_csv(obj):
    import json as _json
    try:
        # 공백 최소화 + 유니코드 그대로
        return _json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        # 혹시 직렬화 실패 시 문자열로 폴백
        return str(obj)

def _safe_load_json(raw):
    """GT/후보 문자열을 최대한 안전하게 JSON으로 파싱.
    반환: (obj or None, normalized_str_for_csv)"""
    import json as _json
    import ast as _ast
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, ""
    s = str(raw)
    s = _extract_json_from_text(s).strip()
    if not s:
        return None, ""
    # 스마트따옴표 → 표준 따옴표
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    # 1차: 표준 JSON
    try:
        obj = _json.loads(s)
        return obj, s
    except Exception:
        pass
    # 1.5차: 개행 복구 - 실제 개행을 \n으로 치환 후 재시도
    try:
        s2 = s.replace("\r\n", "\\n").replace("\n", "\\n")
        obj = _json.loads(s2)
        return obj, s2
    except Exception:
        pass

    # 2차: Python literal 허용(예: {'a':1})
    try:
        obj = _ast.literal_eval(s)
        if isinstance(obj, (dict, list)):
            return obj, _json.dumps(obj, ensure_ascii=False)
    except Exception:
        pass
    return None, s[:200]  # 진단용 앞부분만 보존

def _safe_float(x):
    try:
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            return float(x.strip())
    except Exception:
        return None
    return None

def _extract_usage_from_resp(resp):
    """OpenAI ChatCompletion 스타일/커스텀 로그를 통합 파싱.
    반환 키:
      - llm_prompt_tokens, llm_completion_tokens, llm_total_tokens (int | None)
      - report_time (float 초 | None)
    """
    usage = {}
    if not isinstance(resp, dict):
        return usage

    # 1) usage 우선, 없으면 log 사용
    blob = resp.get("usage")
    if blob is None:
        blob = resp.get("log", {}) if isinstance(resp.get("log"), dict) else {}

    # 공용 getter
    def _get(obj, *names):
        for n in names:
            if isinstance(obj, dict):
                v = obj.get(n)
            else:
                v = getattr(obj, n, None)
            if v not in (None, ""):
                return v
        return None

    # 안전 변환기
    def _as_int(x):
        try:
            if x in (None, ""):
                return None
            return int(float(str(x).strip()))
        except Exception:
            return None

    def _as_float_seconds(v):
        try:
            if v is None:
                return None
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v)
            # "0.1234 seconds" 같은 형식에서 숫자만 추출
            import re
            m = re.search(r"([0-9]*\.?[0-9]+)", s)
            return float(m.group(1)) if m else None
        except Exception:
            return None

    # 2) 토큰 추출 (dict/obj 모두 대응)
    usage["llm_prompt_tokens"]     = _as_int(_get(blob, "prompt_tokens", "input_tokens"))
    usage["llm_completion_tokens"] = _as_int(_get(blob, "completion_tokens", "output_tokens"))
    usage["llm_total_tokens"]      = _as_int(_get(blob, "total_tokens"))

    # 3) 시간 추출: resp["response_time"] → blob["response_time"/"report_time"]
    rt = _get(resp, "response_time") or _get(blob, "response_time", "report_time", "responseTime")
    usage["report_time"] = _as_float_seconds(rt)

    return usage


def _unescape_for_display(s: str) -> str:
    if not isinstance(s, str):
        return s
    # CRLF → LF, \n / \t 이스케이프만 표시용으로 실제 문자로
    return s.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "\t")

def _pretty_json(s_or_obj):
    import json as _json
    # 표시 전용: json.dumps로 예쁘게 찍되, 문자열 내부의 \n/\t는 실제 개행/탭으로 복구
    def _dump_and_unescape(obj):
        dumped = _json.dumps(obj, ensure_ascii=False, indent=2)
        # 표시 전용 복구: "\\r\\n" -> "\n", "\\n" -> "\n", "\\t" -> "\t"
        return _unescape_for_display(dumped)

    if isinstance(s_or_obj, str):
        txt = s_or_obj.strip()
        try:
            txt = _extract_json_from_text(txt)
        except Exception:
            pass
        # 1) 표준 JSON으로 파싱 성공 시: dumps + 개행 복구
        try:
            obj = _json.loads(txt)
            return _dump_and_unescape(obj)
        except Exception:
            # 2) 파싱 실패 시: 원문을 보여주되, \n/\t만 표시용 복구
            return _unescape_for_display(s_or_obj)
    else:
        try:
            return _dump_and_unescape(s_or_obj)
        except Exception:
            return _unescape_for_display(str(s_or_obj))


def _number_lines(text: str):
    lines = (text or "").splitlines()
    return [f"{i+1:4d} | {line}" for i, line in enumerate(lines)]

# region: 병렬 출력을 위한 함수
try:
    from wcwidth import wcswidth, wcwidth
except Exception:
    # wcwidth 미설치 시 안전한 폴백(정확도 낮음)
    def wcwidth(ch): return 1
    def wcswidth(s): return len(s)

def _disp_width(s: str) -> int:
    return max(0, wcswidth(s) if isinstance(s, str) else 0)

def _wrap_by_disp_width(text: str, width: int):
    """한 줄을 가시 폭 기준으로 width에 맞게 강제 감싸기(공백 단어 경계 없어도 안전)."""
    out = []
    line = text or ""
    cur = ""
    curw = 0
    for ch in line:
        w = wcwidth(ch)
        if w < 0: w = 0
        if curw + w > width and cur:
            out.append(cur)
            cur, curw = "", 0
        cur += ch
        curw += w
    out.append(cur)
    return out

def _number_and_wrap(text: str, width: int):
    """
    번호 접두사 '#### | '를 포함한 상태로 가시 폭 기준 감싸기.
    후속 줄은 번호 대신 동일한 공백 폭으로 들여쓰기.
    """
    out = []
    for i, raw in enumerate((text or "").splitlines(), 1):
        prefix = f"{i:4d} | "
        avail = max(1, width - _disp_width(prefix))
        parts = _wrap_by_disp_width(raw, avail)
        for j, seg in enumerate(parts):
            out.append((prefix if j == 0 else " " * len(prefix)) + seg)
    # 빈 문자열도 최소 한 줄은 보장
    if not out:
        out.append(f"{1:4d} | ")
    return out

def _pad_to_width(s: str, width: int):
    """가시 폭 기준 우측 패딩."""
    gap = width - _disp_width(s)
    return s + (" " * gap if gap > 0 else "")

def _make_rule(width: int) -> str:
    return "─" * width  # 전각이더라도 wcwidth가 1로 계산되는 문자 선택


def _print_side_by_side_json(title_left: str, left_text: str,
                             title_right: str, right_text: str, col_width: int = 90):
    # 번호+줄바꿈을 가시폭(col_width)에 맞춰 래핑
    left_lines  = _number_and_wrap(left_text,  col_width)
    right_lines = _number_and_wrap(right_text, col_width)

    # 헤더도 가시폭 패딩으로 맞춤
    print("\n=== Parallel View (JSON) ===")
    left_header  = _pad_to_width(f"[L] {title_left}",  col_width)
    right_header = f"[R] {title_right}"
    print(left_header + " || " + right_header)

    # 구분선도 동일 폭으로
    rule = _make_rule(col_width)
    print(rule + " || " + rule)

    # 본문: 각 줄을 가시폭 기준으로 패딩 후 나란히 출력
    L = max(len(left_lines), len(right_lines))
    for i in range(L):
        l = left_lines[i]  if i < len(left_lines)  else ""
        r = right_lines[i] if i < len(right_lines) else ""
        print(_pad_to_width(l, col_width) + " || " + r)

# endregion

def _choose_rep_gt_for_display(det_eval_results, gt_json_list, gt_str_list):
    """우선순위: evidence.best_gt_json → gt_json_list[0] → gt_str_list[0] → placeholder"""
    import json as _json
    # 1) evidence에 저장된 대표 GT (DET 실행 시 기록됨)
    try:
        idx = det_eval_results["evidence"].get("best_gt_index", None)
        js  = det_eval_results["evidence"].get("best_gt_json", "")
        if js:
            return (idx if idx is not None else 0), _pretty_json(js)
    except Exception:
        pass
    # 2) 객체 리스트가 있으면 0번
    if gt_json_list:
        try:
            return 0, _json.dumps(gt_json_list[0], ensure_ascii=False, indent=2)
        except Exception:
            pass
    # 3) 문자열 리스트가 있으면 첫 항목
    for raw in (gt_str_list or []):
        pr = _pretty_json(raw)
        if pr and pr.strip():
            return 0, pr
    # 4) 아무것도 없으면 플레이스홀더
    return "—", "〈No valid GT parsed / provided〉"

# --- (A) GPT 호출 함수 임포트 (수정: selector + ../ 경로 지원) ---
CURRENT_FILE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CURRENT_FILE_DIR.parents[1]
PARENT_DIR = REPO_ROOT

from contextlib import contextmanager
@contextmanager
def chdir_temporarily(path: Path):
    prev = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(prev)

PARENT_DIR = CURRENT_FILE_DIR.parent  # -> .../<repo_root>/
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))  # ../gpt_mg, ../gpt_cap 임포트 가능

FAMILY_ALIAS_MAP = {
    "joi": "gpt_mg",
    "cap": "gpt_cap",
    "qwen": "qwen",
}

def _load_generate_func(family: str):
    """가족 토큰('joi'|'cap')로 run.generate_joi_code 동적 로드."""
    family = (family or "joi").lower()
    family_module = FAMILY_ALIAS_MAP.get(family, config.DEFAULT_MODEL_PATH)
    family_version = FAMILY_ALIAS_MAP.get(family, config.DEFAULT_MODEL_VERSION)
    try:
        gpt_runner_module = importlib.import_module(f"{family_module}.run")
        get_script_gpt = getattr(gpt_runner_module, "generate_joi_code")
        print(f"✅ 실제 GPT 호출 함수 ('{family_module}.run.generate_joi_code') 로드 성공.")
        return get_script_gpt, family_module, family_version
    except Exception as e:
        print(f"❌ GPT 호출 함수 로드 실패: {family_module}.run.generate_joi_code ({e})")
        raise

# --- (B) 결정론적 평가 함수 ---
def run_deterministic_evaluation(candidate_json: dict, gt_json_list: List[dict], policy_hints: dict) -> dict:
    def _is_noop_code_str(code: str) -> bool:
        if not isinstance(code, str):
            return True if (code is None) else False
        # 주석 제거
        s = re.sub(r"//.*?$|/\*.*?\*/", "", code, flags=re.S | re.M)
        # 의미 없는 세미콜론 제거
        s = s.replace(";", "").strip()
        return s == ""
    
    def _period_equivalent(p_cand, p_gt, tol_ms: int = 0) -> bool:
        # -1(한 번), 0(무한), >0(ms) 규칙
        try:
            pc, pg = int(p_cand), int(p_gt)
        except Exception:
            return False
        if pc in (-1, 0) or pg in (-1, 0):
            return pc == pg
        # 양수는 기본적으로 ‘정확히 같음’. 필요하면 tol_ms 적용 가능
        return abs(pc - pg) <= tol_ms

    def _cron_equivalent(cand: str, gt: str) -> bool:
        a = (cand or "").strip()
        b = (gt or "").strip()
        if a == b:
            return True
        # 선택: croniter가 설치돼 있으면 첫 K회 트리거 비교로 ‘사실상 동치’ 허용
        try:
            from croniter import croniter
            import datetime as dt
            base = dt.datetime(2025, 1, 1, 0, 0, 0)
            K = 3
            seq_a = [croniter(a, base).get_next(dt.datetime) for _ in range(K)]
            seq_b = [croniter(b, base).get_next(dt.datetime) for _ in range(K)]
            return seq_a == seq_b
        except Exception:
            # 라이브러리 없음/파싱 실패 시엔 문자열 동일만 인정
            return False

    def _schedule_pair_equivalent(cand_json: dict, gt_json: dict) -> bool:
        cron_ok   = _cron_equivalent(cand_json.get("cron"),   gt_json.get("cron"))
        period_ok = _period_equivalent(cand_json.get("period"), gt_json.get("period"))
        return cron_ok and period_ok

    try:
        from eval_tools import syntax_checker, policy_checker, similarity_checker
    except Exception as e:
        print(f"❌ DET Error: eval_tools init failed ({e}).")
        return {"scores": {}, "evidence": {"error": f"Init Error: {e}"}}

    scores, evidence = {}, {}
    candidate_code = candidate_json.get("code", "")
    cand_is_noop = _is_noop_code_str(candidate_code)

    # 1) Syntax
    try:
        pv_result = syntax_checker.parse_validate(candidate_code)
        pv_errors = pv_result.get("errors", []) if isinstance(pv_result.get("errors"), list) else []
        evidence["syntax_errors"] = str(pv_errors) if pv_errors else "[]"
    except Exception as e:
        pv_result = {"ok": False, "errors": [f"PV_ERR:{e}"], "ast": None}
        evidence["syntax_errors"] = str(pv_result["errors"])

    if not pv_result.get("ok"):
        scores["syntax_schema"] = 0.0
        ast_node = None
    else:
        scores["syntax_schema"] = 1.0
        ast_node = pv_result.get("ast")

    # 2) Logic Rules (정적 규칙)
    FORBIDDEN_LOOP_DETECTED = False
    if pv_result.get("ok"):
        try:
            sr = syntax_checker.check_static_rules(candidate_json)
            sr_viol = sr.get("violations", []) if isinstance(sr.get("violations"), list) else []
            evidence["rule_violations"] = str(sr_viol) if sr_viol else "[]"

            score = 1.0
            # 경미/중간 위반
            if any("spinning_misuse" in v for v in sr_viol): score -= 0.2
            if any("potential_init_misuse" in v for v in sr_viol): score -= 0.1

            # 치명: 금지 루프 → 즉시 0점
            if any("fatal_forbidden_loop" in v for v in sr_viol) or \
               (" for " in f" {candidate_code} ") or (" while " in f" {candidate_code} ") or \
               any("forbidden_loop" in e for e in pv_errors):
                score = 0.0
                FORBIDDEN_LOOP_DETECTED = True
                # 증거에 치명 플래그 보강
                import ast as _ast
                cur = evidence.get("rule_violations", "[]")
                try: cur_list = _ast.literal_eval(cur) if cur != "[]" else []
                except Exception: cur_list = []
                if not any("fatal_forbidden_loop" in v for v in cur_list):
                    evidence["rule_violations"] = str(cur_list + ["fatal_forbidden_loop"])

            scores["logic_rules"] = max(0.0, score)
        except Exception as e:
            print(f"  ❌ Static Rules Check Error: {e}")
            scores["logic_rules"] = 0.0
            evidence["rule_violations"] = f"Error:{e}"
    else:
        scores["logic_rules"] = 0.0
        evidence["rule_violations"] = "Parse failed"

    # 3) Function Calls (정책)
    fatal_compilation_from_calls = False
    if ast_node is not None:
        try:
            pc = policy_checker.check_function_calls(ast_node, policy_hints)
            pc_issues = pc.get("issues", []) if isinstance(pc.get("issues"), list) else []
            evidence["function_call_issues"] = str(pc_issues) if pc_issues else "[]"

            def has_any(s, kws):
                s = str(s).lower()
                return any(k in s for k in kws)

            SEVERE_KW = [
                "unresolved_function", "unknown_function", "unknown_service",
                "unknown_device", "unknown_device_context",
                "arity_mismatch", "invalid_arity",
                "invalid_argument", "invalid_arg_type", "invalid_argument_type",
                "missing_required_arg", "signature_mismatch", "not_callable"
            ]
            HALLUC_KW = ["hallucinated"]
            # 분류
            severe = sum(1 for i in pc_issues if has_any(i, SEVERE_KW))
            halluc = sum(1 for i in pc_issues if has_any(i, HALLUC_KW))
            minor  = max(0, len(pc_issues) - severe - halluc)

            # 점수 = 1.0 - 0.8*severe - 0.6*halluc - 0.25*minor
            score = 1.0 - 0.8*severe - 0.6*halluc - 0.25*minor
            if severe > 0:
                fatal_compilation_from_calls = True
            scores["function_calls"] = max(0.0, score)
        except Exception as e:
            print(f"  ❌ Function Call Check Error: {e}")
            scores["function_calls"] = 0.0
            evidence["function_call_issues"] = f"Error:{e}"
    else:
        # AST가 없더라도 '빈 코드(no-op)'라면 함수 호출 위반은 없다 → 1.0
        if cand_is_noop:
            scores["function_calls"] = 1.0
            evidence["function_call_issues"] = "[]"
        else:
            scores["function_calls"] = 0.0
            evidence["function_call_issues"] = "Parse failed"

    # 4) Semantic (Z3/AST) Similarity
    best_sem = 0.0
    best_sim_details = {}
    equivalent_overall = True

    best_gt_index = None
    best_gt_json_str = None

    if not gt_json_list:
        scores["semantic_intent_z3"] = 0.0
        evidence["similarity_diff"] = "No GTs provided"
        equivalent_overall = False
    else:
        for i, gt_json in enumerate(gt_json_list):
            try:
                sim_result = similarity_checker.calculate_similarity(candidate_json, gt_json)
                code_eq = bool(sim_result.get("equivalent"))
                code_sim = sim_result.get("similarity", {}).get("code", 0.0)

                sched_ok = _schedule_pair_equivalent(candidate_json, gt_json)

                # 코드 동치 + 스케줄 동치 => 즉시 1.0 확정 & break
                if code_eq and sched_ok:
                    best_sem = 1.0
                    best_sim_details = sim_result
                    best_gt_index = i
                    import json as _json
                    best_gt_json_str = _json.dumps(gt_json, ensure_ascii=False, indent=2)
                    equivalent_overall = True
                    evidence["schedule_match"] = {"gt_index": i, "cron": True, "period": True}
                    break

                # 그 외엔 ‘최고 유사도’ 계속 추적 (스케줄 불일치면 그대로 반영)
                if code_sim >= best_sem:
                    best_sem = code_sim
                    best_sim_details = sim_result
                    best_gt_index = i
                    import json as _json
                    best_gt_json_str = _json.dumps(gt_json, ensure_ascii=False, indent=2)

            except ImportError:
                best_sem = 0.0
                equivalent_overall = "skipped (z3-solver not installed)"
                break
            except Exception as e:
                best_sem = 0.0
                equivalent_overall = f"SIM_ERR({e})"
                break

        scores["semantic_intent_z3"] = best_sem
        evidence["equivalent_z3"]    = best_sim_details.get("equivalent", equivalent_overall) if best_sim_details else equivalent_overall
        evidence["best_gt_index"]    = best_gt_index
        evidence["best_gt_json"]     = best_gt_json_str or ""

    # 5) Overall (DET) + 수렴 게이트
    #    기본: 가중합 (config.WEIGHTS), 단 수렴 조건이면 0 강제
    overall_det = 0.0
    for k in config.WEIGHTS:
        key = "semantic_intent_z3" if k == "semantic_intent" else k
        overall_det += scores.get(key, 0.0) * config.WEIGHTS[k]

    fatal_flags = []
    if not pv_result.get("ok"):              fatal_flags.append("fatal_parse_error")
    if FORBIDDEN_LOOP_DETECTED:              fatal_flags.append("fatal_forbidden_loop")
    if fatal_compilation_from_calls:         fatal_flags.append("fatal_function_signature")

    if fatal_flags:
        overall_det = 0.0
        evidence["fatal_flags"] = str(fatal_flags)

    scores["overall_deterministic"] = max(0.0, min(1.0, overall_det))
    return {"scores": scores, "evidence": evidence}


# --- (C) LangSmith Judge (원본 유지) ---
def build_llm_semantic_judge(criteria_prompt):
    try:
        from langchain_openai import ChatOpenAI  # noqa: F401
    except Exception as e:
        print(f"⚠️ LLM Judge 초기화 실패 (langchain_openai 미설치): {e}")
        return None

    if isinstance(criteria_prompt, dict):
        crit_text = "\n".join([f"- {k}: {v}" for k, v in criteria_prompt.items()])
    elif isinstance(criteria_prompt, str) and criteria_prompt.strip():
        crit_text = criteria_prompt.strip()
    else:
        crit_text = (
            "Judge whether the PREDICTION's code fulfills the INPUT instruction. "
            "Use the REFERENCE code as guidance if provided. Return a JSON with "
            "'score' in [0,1] and concise 'reasoning'."
        )

    llm = config.build_chat_openai(
        model=getattr(config, "LS_JUDGE_MODEL", "gpt-4o"),
        temperature=0,
        context="Lang semantic judge",
    )

    class _Judge:
        def __init__(self, llm, crit_text):
            self.llm = llm
            self.crit_text = crit_text

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json
            import re as _re
            sys_prompt = (
                "You are a strict evaluator for a DSL (JoI-Lang). "
                "Only evaluate intent alignment, not syntax correctness."
            )
            user_prompt = f"""
## CRITERIA
{self.crit_text}

## INPUT (natural language instruction)
{input}

## REFERENCE (ground truth code; may be empty)
{reference}

## PREDICTION (candidate code)
{prediction}

Respond ONLY with a JSON object:
{{
  "score": <float between 0 and 1>,
  "reasoning": "<short explanation>"
}}
"""
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res))
            except Exception as e:
                return {"score": 0.0, "reasoning": f"invoke_error: {e}", "raw": ""}

            def _extract_json_block(s: str):
                try:
                    start = s.find("{"); end = s.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        return s[start:end+1]
                except Exception:
                    pass
                return None

            js_raw = _extract_json_block(text)
            parsed = None
            if js_raw:
                try:
                    parsed = _json.loads(js_raw)
                except Exception:
                    parsed = None

            score = 0.0
            reasoning = ""
            if isinstance(parsed, dict):
                score = parsed.get("score", 0.0)
                reasoning = parsed.get("reasoning", "")
            else:
                m = _re.search(r"score\s*[:=]\s*([01](?:\.\d+)?)", text, flags=_re.IGNORECASE)
                if m:
                    try:
                        score = float(m.group(1))
                    except Exception:
                        score = 0.0
                reasoning = text.strip()

            try:
                score = float(score)
            except Exception:
                score = 0.0
            score = max(0.0, min(1.0, score))
            return {"score": score, "reasoning": reasoning, "raw": text}

    return _Judge(llm, crit_text)

def build_llm_multi_criteria_judge(criteria: Dict[str, str]):
    try:
        from langchain_openai import ChatOpenAI  # noqa: F401
    except Exception as e:
        print(f"⚠️ LLM Multi Judge 초기화 실패: {e}")
        return None

    if not isinstance(criteria, dict) or not criteria:
        return None

    llm = config.build_chat_openai(
        model=getattr(config, "LS_JUDGE_MODEL", "gpt-4o"),
        temperature=0,
        context="Lang multi-criteria semantic judge",
    )

    class _MultiJudge:
        def __init__(self, llm, criteria):
            self.llm = llm
            self.criteria = criteria

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json
            crit_text = "\n".join([f"- {k}: {v}" for k, v in self.criteria.items()])
            sys_prompt = (
                "You are a strict evaluator for a DSL (JoI-Lang). "
                "Return a JSON object with per-criterion scores in [0,1] and short rationales."
            )
            user_prompt = f"""
## CRITERIA
{crit_text}

## INPUT
{input}

## REFERENCE
{reference}

## PREDICTION
{prediction}

Respond ONLY with a JSON object:
{{
  "scores": {{
    "<criterion_name>": <float 0..1>, ...
  }},
  "rationales": {{
    "<criterion_name>": "<short reason>", ...
  }}
}}
"""
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res)).strip()
            except Exception as e:
                return {"scores": {}, "rationales": {"_error": f"invoke_error: {e}"}}

            try:
                start = text.find("{"); end = text.rfind("}")
                js = text[start:end+1] if start != -1 and end != -1 else "{}"
                obj = _json.loads(js)
            except Exception:
                obj = {}
            scores = obj.get("scores", {})
            rats = obj.get("rationales", {})
            clean_scores = {}
            for k in self.criteria.keys():
                v = scores.get(k, 0.0)
                try: v = float(v)
                except: v = 0.0
                clean_scores[k] = max(0.0, min(1.0, v))
            return {"scores": clean_scores, "rationales": rats}

    return _MultiJudge(llm, criteria)

# --- (D) 로컬 테스트 함수 (모든 모드 통합) ---
def run_local_test(
    modes: List[str],
    row_index: int,
    model_version_path: str,
    family_token: str = "joi",
    batch_context: bool = False,
    output_dir: str = ".",
):
    """ 로컬 테스트 모드 실행을 위한 통합 로직 """
    valid_modes = {"det", "lang", "gpt", "hybrid"}
    requested_modes = [m for m in modes if m in valid_modes]
    if not requested_modes:
        print("Error: No valid mode specified.")
        return
    if any(m == "hybrid" for m in requested_modes):
        requested_modes = ["det", "lang", "gpt"]
    requested_modes = sorted(set(requested_modes), key=lambda x: ["det","lang","gpt","hybrid"].index(x) if x in ["det","lang","gpt","hybrid"] else 9)
    run_det = "det" in requested_modes
    run_lang = "lang" in requested_modes
    run_gpt_j = "gpt" in requested_modes
    mode_str = "+".join(m.upper() for m in requested_modes)

    # generate_joi_code 로드
    model_version = model_version_path
    try:
        get_script_gpt, family_module, model_version_path = _load_generate_func(family_token)
    except Exception:
        return

    # 1. 모델 이름 및 파일명 설정
    # model_version_path = "version0_2"
    full_model_name = f"{family_module}.{model_version}"
    print(f"--- 🚀 Running {mode_str} Local Test for Row Index: {row_index} using Model: {full_model_name} ---")
    safe_model_path_name_for_file = re.sub(r"[^\w\-]+", "_", full_model_name)
    output_path = Path(output_dir or ".") / f"result_{safe_model_path_name_for_file}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_filename = str(output_path)
    print(f"   (Results will be appended/updated in: {output_filename})")

    # 2. 데이터 로드
    try:
        data_path = _resolve_project_path(config.DATA_FILE_PATH)
        df = pd.read_csv(str(data_path), encoding="utf-8-sig")
        if not (0 <= row_index < len(df)):
            print(f"Error: Row index {row_index} out of bounds.")
            return
        row = df.iloc[row_index]
    except FileNotFoundError:
        print(f"Error: 데이터 파일({config.DATA_FILE_PATH}) 없음.")
        return
    except Exception as e:
        print(f"Error loading data: {e}")
        traceback.print_exc()
        return

    original_index = row.get("index", row_index)
    command = row.get(config.COMMAND_COLUMN, "Command not found")
    raw_command_kor = row.get("command_kor", "")
    if raw_command_kor is None or (isinstance(raw_command_kor, float) and pd.isna(raw_command_kor)):
        command_kor = ""
    else:
        command_kor = str(raw_command_kor).strip()
    category_for_csv = None
    category_for_csv = _extract_category_value(row)

    print(f"[1/N] 명령어 로드 `(Original Index: {original_index}, category={category_for_csv}): {command}")
    print(f" >> command: {command}")
    # 3. GPT 모델 호출 (생성 속도 측정)
    connected_devices_str = row.get("connected_devices")
    try:
        raw_cd = (
            ast.literal_eval(connected_devices_str)
            if pd.notna(connected_devices_str) and isinstance(connected_devices_str, str) and connected_devices_str.strip()
            else {}
        )
    except Exception:
        raw_cd = {}
    connected_devices = _normalize_connected_devices(raw_cd)

    # 🔹 추가: category 저장용 값 추출 (category_analysis -> category)
    try:
        cat_val_raw = row.get("category_analysis", None)
        cat_val_num = pd.to_numeric(cat_val_raw, errors="coerce")
        category_for_csv = int(cat_val_num) if pd.notna(cat_val_num) else None
    except Exception:
        category_for_csv = None

    # 누락되어 있던 줄 추가!
    other_params_str = row.get("options")

    try:
        other_params = (
            ast.literal_eval(other_params_str)
            if pd.notna(other_params_str) and isinstance(other_params_str, str) and other_params_str.strip()
            else []
        )
    except Exception:
        other_params = []

    print(f"   Calling get_script_gpt with model='{full_model_name}'")

    # 타이머
    t0_gen = time.perf_counter()
    gen_started_at_iso = datetime.now().isoformat(timespec="seconds")

    resp = {}
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with chdir_temporarily(REPO_ROOT):
            resp = get_script_gpt(
                sentence=command,
                model=full_model_name,
                current_time=current_time_str,
                connected_devices=connected_devices,
                other_params=other_params,
            )
        if not isinstance(resp, dict):
            print(f"❌ GPT 모델 함수 반환 타입 오류: {type(resp)}")
            return
        try:
            from eval_tools.registry import build_policy_hints_from_service_lists
            service_files = [
                str((PARENT_DIR / "gpt_cap" / "files" / "service_list_ver1.5.3.json").resolve()),
            ]
            policy_hints = build_policy_hints_from_service_lists(service_files)
        except Exception as e:
            policy_hints = {}
            print(f"⚠️ policy hints skipped (legacy eval_tools registry unavailable: {e})")

    except TypeError as te:
        print(f"❌ GPT 모델 호출 인자 오류: {te}")
        print("   'generate_joi_code' 함수의 인자(sentence, model, current_time 등)를 확인하세요.")
        return
    except Exception as e:
        print(f"❌ GPT 모델 호출 오류: {e}")
        return

    t1_gen = time.perf_counter()
    gen_finished_at_iso = datetime.now().isoformat(timespec="seconds")
    elapse_time = round(t1_gen - t0_gen, 6) 

    usage_info = _extract_usage_from_resp(resp)
    ## print("[DEBUG usage]", usage_info)

    report_time = usage_info.get("report_time", None)  
    llm_prompt_tokens = usage_info.get("llm_prompt_tokens", None)
    llm_completion_tokens = usage_info.get("llm_completion_tokens", None)
    llm_total_tokens = usage_info.get("llm_total_tokens", None)

    response_time = usage_info.get("report_time", elapse_time)  

    generated_code_output = resp.get("code") if isinstance(resp, dict) else None

    if isinstance(generated_code_output, list):
        generated_code_json_str = generated_code_output[0]
    elif isinstance(generated_code_output, str):
        generated_code_json_str = generated_code_output
    else:
        generated_code_json_str = "{}"

    # 펜스 제거
    # print("   Extracting JSON from GPT response...", generated_code_json_str, type(generated_code_json_str))
    if isinstance(generated_code_json_str, str):
        generated_code_json_str = _extract_json_from_text(generated_code_json_str)
        try:
            candidate_json = json.loads(generated_code_json_str) if generated_code_json_str and generated_code_json_str.strip() else {"code": ""}
        except json.JSONDecodeError as e:
            print(f"Error: GPT 반환 JSON 파싱 실패: {e}")
            candidate_json = {"code": f"INVALID JSON: {generated_code_json_str}"}
    else:  # 이미 json 형태인 경우
        candidate_json = generated_code_json_str if generated_code_json_str else {"code": ""}
    print(f"[2/N] 후보 JSON 생성 ({response_time:.3f}초, 측정 {elapse_time:.3f}s):\n{generated_code_json_str}")

    # 4. Ground Truth 로드 (안전 파서)
    def _gt_order_key(c: str) -> int:
        m = re.match(r"gt(\d+)$", c.lower())
        return int(m.group(1)) if m else 10**9  # 숫자 없는건 뒤로
    gt_columns = sorted(
        [c for c in df.columns if c.lower().startswith("gt")],
        key=_gt_order_key
    )    

    gt_json_list, gt_str_list = [], []
    print(len(gt_columns))
    print(gt_columns[0])
    for gt_col in gt_columns:
        raw = row.get(gt_col)
        obj, norm = _safe_load_json(raw)
        if obj is None:
            if isinstance(raw, str) and raw.strip():
                sample = raw.replace("\n", "\\n")[:120]
                print(f"Warning: GT column '{gt_col}' JSON 파싱 실패. sample={sample}")
            continue
        gt_json_list.append(obj)
        gt_str_list.append(norm if isinstance(norm, str) and norm else json.dumps(obj, ensure_ascii=False))
    print(f"[3/N] {len(gt_json_list)}개의 유효한 Ground Truth 로드 완료.")

    # 5. 결정론적 평가 실행 (선택)
    det_eval_results = {"scores": {}, "evidence": {}}
    if run_det:
        policy_hints = {}
        det_eval_results = run_deterministic_evaluation(candidate_json, gt_json_list, policy_hints)
        print(f"[4/N] 결정론적 평가 완료.")

    step_order = 4 if run_det else 3

    # 6. LangSmith Judge (선택)
    semantic_intent_ls = None
    ls_judge_reasoning = ""
    ls_multi_scores = {}
    if run_lang:
        step_order += 1
        print(f"[{step_order}/N] LangSmith Criteria Judge (로컬 실행) 시작...")

        try:
            from cloud_judge.judge import get_default_multi_criteria_judge
        except ImportError as e1:
            try:
                from evaluation.cloud_judge.judge import get_default_multi_criteria_judge
            except ImportError as e2:
                get_default_multi_criteria_judge = None
                import traceback
                print("⚠️ 경고: get_default_multi_criteria_judge import 실패")
                print(f"  - cloud_judge.judge 실패: {e1}")
                print(f"  - evaluation.cloud_judge.judge 실패: {e2}")
                print(f"  - cwd: {os.getcwd()}")
                print(f"  - file: {__file__}")
                print("  - sys.path(head 8):")
                for p in sys.path[:8]:
                    print("    ", p)
                here = Path(__file__).resolve().parent
                print("  - exists:", (here / "cloud_judge" / "judge.py").exists(), str(here / "cloud_judge" / "judge.py"))
                traceback.print_exc()


        crit = getattr(config, "SEMANTIC_JUDGE_CRITERIA", None) or getattr(config, "SEMANTIC_JUDGE_CRITERIA_PROMPT", "")
        reference_code = gt_json_list[0]["code"] if gt_json_list and "code" in gt_json_list[0] else ""
        try:
            if get_default_multi_criteria_judge is not None:
                evaluator = get_default_multi_criteria_judge()
                res = evaluator.evaluate_strings(
                    prediction=candidate_json.get("code", ""),
                    input=command,
                    reference=reference_code,
                )
                ls_multi_scores = res.get("scores", {})
                # semantic_intent 대표값 추출(없으면 평균)
                key_pref = ["semantic_intent", "intent", "overall"]
                for k in key_pref:
                    if k in ls_multi_scores:
                        semantic_intent_ls = float(ls_multi_scores[k]); break
                if semantic_intent_ls is None and ls_multi_scores:
                    semantic_intent_ls = float(np.mean(list(ls_multi_scores.values())))
                ls_judge_reasoning = res.get("rationales", {})
                print(f"  - LangSmith Multi-Criteria: {ls_multi_scores}")

            else:
                # 폴백: 기존 로컬 빌더 유지
                if isinstance(crit, dict) and len(crit) > 1:
                    evaluator = build_llm_multi_criteria_judge(crit)
                    if evaluator is None:
                        ls_judge_reasoning = "skipped (libs unavailable)"
                    else:
                        res = evaluator.evaluate_strings(
                            prediction=candidate_json.get("code", ""),
                            input=command,
                            reference=reference_code,
                        )
                        ls_multi_scores = res.get("scores", {})
                        key_pref = ["semantic_intent", "intent", "overall"]
                        for k in key_pref:
                            if k in ls_multi_scores:
                                semantic_intent_ls = float(ls_multi_scores[k]); break
                        if semantic_intent_ls is None and ls_multi_scores:
                            semantic_intent_ls = float(np.mean(list(ls_multi_scores.values())))
                        ls_judge_reasoning = res.get("rationales", {})
                        print(f"  - LangSmith Multi-Criteria: {ls_multi_scores}")
                else:
                    evaluator = build_llm_semantic_judge(crit)
                    if evaluator is None:
                        ls_judge_reasoning = "skipped (libs unavailable)"
                    else:
                        eval_result = evaluator.evaluate_strings(
                            prediction=candidate_json.get("code", ""),
                            input=command,
                            reference=reference_code,
                        )
                        score = eval_result.get("score", None)
                        if score is None:
                            score = 0.0
                        semantic_intent_ls = float(score)
                        ls_judge_reasoning = eval_result.get("reasoning", "N/A")
                        print(f"  - LangSmith Judge Score (semantic_intent_ls): {semantic_intent_ls:.4f}")
        except Exception as e:
            print(f"  ❌ LangSmith Judge 실행 중 오류: {e}")
            ls_judge_reasoning = f"error ({e})"

    # 7. Custom GPT Judge (선택)
    raw_gpt_similarity = None
    gpt_judge_reasoning = ""
    gpt_reconverted_sentence = ""
    gpt_reconverted_reference_sentence = ""
    gpt_reconverted_same = ""
    gpt_reconverted_score = None
    gpt_reconverted_reasoning = ""
    if run_gpt_j:
        step_order += 1
        print(f"[{step_order}/N] Custom GPT Judge (로컬 실행) 시작...")
        try:
            from cloud_judge import judge_gpt
            run_custom_gpt_judge_func = judge_gpt.run_custom_gpt_judge
            run_reconverted_fallback_judge_func = getattr(judge_gpt, "run_reconverted_fallback_judge", None)
            custom_judge_available = True
        except ImportError as e1:
            try:
                from evaluation.cloud_judge import judge_gpt
                run_custom_gpt_judge_func = judge_gpt.run_custom_gpt_judge
                run_reconverted_fallback_judge_func = getattr(judge_gpt, "run_reconverted_fallback_judge", None)
                custom_judge_available = True
            except ImportError as e2:
                custom_judge_available = False
                run_custom_gpt_judge_func = None
                run_reconverted_fallback_judge_func = None
                import traceback
                print("⚠️ 경고: Custom GPT Judge 모듈 로드 실패")
                print(f"  - cloud_judge 실패: {e1}")
                print(f"  - evaluation.cloud_judge 실패: {e2}")
                print(f"  - cwd: {os.getcwd()}")
                print(f"  - file: {__file__}")
                print("  - sys.path(head 8):")
                for p in sys.path[:8]:
                    print("    ", p)
                here = Path(__file__).resolve().parent
                print("  - exists:", (here / "cloud_judge" / "judge_gpt.py").exists(), str(here / "cloud_judge" / "judge_gpt.py"))
                traceback.print_exc()

        if custom_judge_available and run_custom_gpt_judge_func:
            first_gt_code = next(
                (
                    str(gt.get("code", "")).strip()
                    for gt in gt_json_list
                    if isinstance(gt, dict) and str(gt.get("code", "")).strip()
                ),
                "",
            )
            if first_gt_code:
                try:
                    gpt_judge_result = run_custom_gpt_judge_func(candidate_json.get("code", ""), first_gt_code, command)
                    raw_gpt_similarity = gpt_judge_result.get("score", 0.0)  # 원시 점수
                    gpt_judge_reasoning = gpt_judge_result.get("comment", "")
                    print(f"  - Custom GPT Judge Raw Similarity: {raw_gpt_similarity:.4f}")
                except Exception as e:
                    print(f"  ❌ Custom GPT Judge 실행 중 오류: {e}")
                    gpt_judge_reasoning = f"error ({e})"
            elif run_reconverted_fallback_judge_func:
                gpt_reconverted_reference_sentence = command_kor or command
                try:
                    fallback_result = run_reconverted_fallback_judge_func(
                        candidate_code=candidate_json.get("code", ""),
                        original_sentence=command,
                        original_sentence_kor=command_kor,
                        connected_devices=connected_devices,
                        other_params=other_params,
                    )
                    raw_gpt_similarity = fallback_result.get("score", 0.0)
                    gpt_reconverted_sentence = fallback_result.get("translated_sentence", "")
                    gpt_reconverted_same = fallback_result.get("same", False)
                    gpt_reconverted_score = raw_gpt_similarity
                    gpt_reconverted_reasoning = fallback_result.get("comment", "")
                    translation_comment = fallback_result.get("translation_comment", "")
                    reason_bits = []
                    if gpt_reconverted_reasoning:
                        reason_bits.append(f"fallback_reconverted_match: {gpt_reconverted_reasoning}")
                    if translation_comment:
                        reason_bits.append(f"translation: {translation_comment}")
                    gpt_judge_reasoning = " | ".join(reason_bits) or "fallback_reconverted_match"
                    print(f"  - No valid GT. Fallback reconverted match score: {raw_gpt_similarity:.4f}")
                    if gpt_reconverted_sentence:
                        print(f"  - Reconverted Korean Sentence: {gpt_reconverted_sentence}")
                    print(f"  - Same As Input: {gpt_reconverted_same}")
                except Exception as e:
                    print(f"  ❌ Fallback reconverted judge 실행 중 오류: {e}")
                    gpt_judge_reasoning = f"fallback_error ({e})"
                    gpt_reconverted_reasoning = f"error ({e})"
            else:
                gpt_judge_reasoning = "skipped (no valid GT)"
        else:
            gpt_judge_reasoning = "skipped (module unavailable)"

    # 8. 최종 점수 계산
    #    DET × ( overall_lang(=LS 세부 가중합 or fallback) + overall_gpt(=W * raw_gpt_similarity) )
    final_scores: Dict[str, Any] = {}
    if run_det:
        final_scores.update(det_eval_results["scores"])

    if semantic_intent_ls is not None:
        final_scores["semantic_intent_ls"] = float(semantic_intent_ls)

    # DET 점수
    det_score = float(final_scores.get("overall_deterministic") or 0.0)

    # LS: 세부 항목 가중합 (있으면 세부항목만 사용, 없으면 fallback으로 semantic_intent_ls 사용)
    LS_CRITERIA_WEIGHTS = dict(getattr(config, "LS_CRITERIA_WEIGHTS", {}))
    _W_GPT = getattr(config, "GPT_SCORE_WEIGHT", 0.2)
    import re as _re

    ls_weighted = None
    if ls_multi_scores:
        present = [(k, v) for k, v in ls_multi_scores.items() if k in LS_CRITERIA_WEIGHTS]
        if not present:
            norm_scores  = { _re.sub(r"\s+", "_", k.lower()): v for k, v in ls_multi_scores.items() }
            norm_weights = { _re.sub(r"\s+", "_", k.lower()): w for k, w in LS_CRITERIA_WEIGHTS.items() }
            present = [(k, norm_scores[k]) for k in norm_scores if k in norm_weights]
            if present:
                LS_CRITERIA_WEIGHTS = norm_weights  # 로컬 그림자 변수

        if present:
            wsum = sum(LS_CRITERIA_WEIGHTS[k] for k, _ in present)
            if wsum > 0:
                ls_weighted = sum(LS_CRITERIA_WEIGHTS[k] * float(v or 0.0) for k, v in present) / float(wsum)

    if ls_weighted is None:
        ls_weighted = float(final_scores.get("semantic_intent_ls") or 0.0)

    # --- Lang/GPT 가중 평균 (가중치 합=1) ---
    # config.GPT_SCORE_WEIGHT 를 W_GPT(0..1)로 해석, W_LANG=1-W_GPT
    try:
        W_GPT = float(_W_GPT)
    except Exception:
        W_GPT = 0.5
    W_GPT = max(0.0, min(1.0, W_GPT))
    W_LANG = 1.0 - W_GPT

    lang_raw = max(0.0, min(1.0, float(ls_weighted or 0.0)))
    gpt_raw  = max(0.0, min(1.0, float(raw_gpt_similarity) if raw_gpt_similarity is not None else 0.0))

    # GPT 심사를 안 돌린 경우(점수 없음) 재정규화 옵션
    if raw_gpt_similarity is None and getattr(config, "RENORM_WHEN_GPT_MISSING", True):
        W_LANG, W_GPT = 1.0, 0.0

    overall_lang = W_LANG * lang_raw
    overall_gpt  = W_GPT * gpt_raw

    # ▶ 최종 산식: overall_final = DET × (W_LANG*LANG + W_GPT*GPT)
    overall_final_new = det_score * (overall_lang + overall_gpt)

    final_scores["overall_lang"]  = overall_lang
    final_scores["overall_gpt"]   = overall_gpt
    final_scores["overall_final"] = overall_final_new
    final_status_label = _label_overall_final(final_scores["overall_final"])
    final_status_label = str(final_status_label)  # 안전하게 문자열 보장

    # CSV 데이터 준비
    output_data = {
        "index": original_index,
        "category": ("" if category_for_csv is None else category_for_csv),
        "model_name": full_model_name,
        "command": command,
        "final_status": final_status_label,

        # --- 생성 메타/시간/토큰 ---
        "gen_started_at": gen_started_at_iso,
        "gen_ended_at": gen_finished_at_iso,
        "response_time": f"{response_time:.3f}",
        "elapse_time": elapse_time,
        "report_time": (None if report_time is None else report_time),  # ← 이름 변경
        "llm_prompt_tokens": (None if llm_prompt_tokens is None else llm_prompt_tokens),
        "llm_completion_tokens": (None if llm_completion_tokens is None else llm_completion_tokens),
        "llm_total_tokens": (None if llm_total_tokens is None else llm_total_tokens),

        # --- 점수 ---
        "overall_final": final_scores.get("overall_final"),
        "overall_deterministic": final_scores.get("overall_deterministic") if run_det else "",
        "syntax_schema": final_scores.get("syntax_schema") if run_det else "",
        "logic_rules": final_scores.get("logic_rules") if run_det else "",
        "function_calls": final_scores.get("function_calls") if run_det else "",
        "semantic_intent_z3": final_scores.get("semantic_intent_z3") if run_det else "",
        "overall_lang": final_scores.get("overall_lang") if run_lang else "",   # ← 추가
        "equivalent_z3": det_eval_results["evidence"].get("equivalent_z3") if run_det else "",
        "overall_gpt": final_scores.get("overall_gpt") if run_gpt_j else "",    # ← 추가

        # --- 텍스트/증거 ---
        "generated_candidate_json": _compact_json_for_csv(candidate_json),
        "ground_truth_json_list": _compact_json_for_csv(gt_json_list),
        "syntax_errors": det_eval_results["evidence"].get("syntax_errors") if run_det else "",
        "rule_violations": det_eval_results["evidence"].get("rule_violations") if run_det else "",
        "function_call_issues": det_eval_results["evidence"].get("function_call_issues") if run_det else "",
        "z3_diff": det_eval_results["evidence"].get("similarity_diff") if run_det else "",
        "ls_judge_reasoning": ls_judge_reasoning if run_lang else "",
        "gpt_judge_reasoning": gpt_judge_reasoning if run_gpt_j else "",
        "gpt_reconverted_reference_sentence": gpt_reconverted_reference_sentence if run_gpt_j else "",
        "gpt_reconverted_sentence": gpt_reconverted_sentence if run_gpt_j else "",
        "gpt_reconverted_same": gpt_reconverted_same if run_gpt_j else "",
        "gpt_reconverted_score": gpt_reconverted_score if run_gpt_j else "",
        "gpt_reconverted_reasoning": gpt_reconverted_reasoning if run_gpt_j else "",
    }
    for k, v in (ls_multi_scores or {}).items():
        output_data[f"ls_{k}"] = v
    if isinstance(output_data.get("ls_judge_reasoning"), (dict, list)):
        output_data["ls_judge_reasoning"] = json.dumps(
            output_data["ls_judge_reasoning"],
            ensure_ascii=False,
        )
    if isinstance(output_data.get("gpt_judge_reasoning"), (dict, list)):
        output_data["gpt_judge_reasoning"] = json.dumps(
            output_data["gpt_judge_reasoning"],
            ensure_ascii=False,
        )

    try:
        ordered_columns = [
            "index",
            "category",
            "model_name",
            "command",

            # --- 생성 메타 ---
            "gen_started_at",
            "gen_ended_at",
            "response_time",
            "elapse_time",          # ← 이름 변경
            "report_time",          # ← 이름 변경
            "llm_prompt_tokens",
            "llm_completion_tokens",
            "llm_total_tokens",

            # --- 점수 ---
            "overall_final",
            "final_status", 
            "overall_deterministic",
            "syntax_schema",
            "logic_rules",
            "function_calls",
            "semantic_intent_z3",
            "overall_lang",         # ← 추가
            "equivalent_z3",
            "overall_gpt",          # ← 추가

            # --- 텍스트/증거 ---
            "generated_candidate_json",
            "ground_truth_json_list",
            "syntax_errors",
            "rule_violations",
            "function_call_issues",
            "z3_diff",
            "ls_judge_reasoning",
            "gpt_judge_reasoning",
            "gpt_reconverted_reference_sentence",
            "gpt_reconverted_sentence",
            "gpt_reconverted_same",
            "gpt_reconverted_score",
            "gpt_reconverted_reasoning",
        ]

        numeric_cols = [
            "overall_final",
            "overall_deterministic",
            "syntax_schema",
            "logic_rules",
            "function_calls",
            "semantic_intent_z3",
            "overall_lang",
            "overall_gpt",
            "gpt_reconverted_score",
            "response_time",
            "elapse_time",
            "report_time",
            "llm_prompt_tokens",
            "llm_completion_tokens",
            "llm_total_tokens",
            "category",
        ]

        for col in [
            "ls_semantic_intent",
            "ls_conditions",
            "ls_time_period",
            "ls_device_service",
        ]:
            if col not in ordered_columns:
                ordered_columns.append(col)
            if col not in numeric_cols:
                numeric_cols.append(col)

        for col in output_data.keys():
            if col not in ordered_columns:
                ordered_columns.append(col)

        # (1) 결과 파일 로드 or 빈 DF 생성
        if os.path.exists(output_filename):
            try:
                existing_df = pd.read_csv(output_filename, encoding="utf-8-sig")
            except pd.errors.EmptyDataError:
                existing_df = pd.DataFrame(columns=ordered_columns)
            except Exception as e:
                print(f"Warning: CSV 읽기 실패 ({e}). 새로 생성합니다.")
                existing_df = pd.DataFrame(columns=ordered_columns)
        else:
            existing_df = pd.DataFrame(columns=ordered_columns)
        for col in existing_df.columns:
            if col not in ordered_columns:
                ordered_columns.append(col)
        if "final_status" in existing_df.columns and existing_df["final_status"].dtype != "object":
            try:
                existing_df["final_status"] = existing_df["final_status"].astype("object")
            except Exception:
                pass

        # (2) 필요한 컬럼 보장
        for col in ordered_columns:
            if col not in existing_df.columns:
                existing_df[col] = np.nan if col in numeric_cols else ""

        # (3) x번째(= row_index)까지 빈 행을 패딩
        target_row_idx = int(row_index)  # ⬅️ 입력 받은 인덱스 x
        if len(existing_df) <= target_row_idx:
            pad_rows = target_row_idx + 1 - len(existing_df)
            pad_df = pd.DataFrame(
                [{c: (np.nan if c in numeric_cols else "") for c in ordered_columns}]
                * pad_rows
            )
            existing_df = pd.concat([existing_df, pad_df], ignore_index=True)

        # (4) 값 정리 후 x번째 행에 바로 덮어쓰기(upsert)
        output_data_clean = {
            k: ("" if (v is None or (isinstance(v, float) and pd.isna(v))) else v)
            for k, v in output_data.items()
        }

        for col, value in output_data_clean.items():
            if col not in existing_df.columns:
                existing_df[col] = np.nan if col in numeric_cols else ""
            if col in numeric_cols:
                if value == "":
                    existing_df.loc[target_row_idx, col] = np.nan
                else:
                    existing_df.loc[target_row_idx, col] = pd.to_numeric(value, errors="coerce")
            else:
                if existing_df[col].dtype != "object":
                    try:
                        existing_df[col] = existing_df[col].astype("object")
                    except Exception:
                        pass
                existing_df.loc[target_row_idx, col] = "" if value is None else str(value)

        # (5) ‘index’ 컬럼에는 원본 CSV의 실제 인덱스 번호(original_index) 저장
        existing_df.loc[target_row_idx, "index"] = str(original_index)

        # (6) 컬럼 순서/결측 정리 후 저장
        final_df = existing_df.reindex(columns=ordered_columns)
        obj_cols = [c for c in final_df.columns if c not in numeric_cols]
        if obj_cols:
            final_df[obj_cols] = final_df[obj_cols].fillna("")

        final_df.to_csv(output_filename, mode="w", header=True, index=False, encoding="utf-8-sig")
        print(f"\n--- Row {target_row_idx} upserted (모자라면 패딩 후 저장): {output_filename} ---")

        # 나중에 Parallel View 헤더에 쓰기 위해(표시용)
        index_str = str(target_row_idx)

    except Exception as e:
        print(f"CSV 저장/업데이트 오류: {e}")
        traceback.print_exc()

    # 9. 콘솔 출력 요약
    print(f"\n--- 📊 최종 {mode_str.upper()} 점수 ---")
    if run_det:
        print("\n[결정론적 평가 결과 (DET)]")
        det_keys = ["overall_deterministic", "syntax_schema", "logic_rules", "function_calls", "semantic_intent_z3"]
        det_scores = {k: final_scores.get(k) for k in det_keys}
        print(json.dumps({k: (f"{v:.4f}" if isinstance(v, float) else str(v))
                          for k, v in det_scores.items() if v not in (None, "")}, indent=2, ensure_ascii=False))
        equiv_result = det_eval_results["evidence"].get("equivalent_z3")
        print(f"  - Z3 논리 동등성: {equiv_result}")

    if run_lang:
        print("\n[LangSmith Judge 결과 (LANG)]")
        lang_scores = {"overall_lang": final_scores.get("overall_lang")}
        print(json.dumps({k: (f"{v:.4f}" if isinstance(v, float) else str(v))
                          for k, v in lang_scores.items() if v not in (None, "")}, indent=2, ensure_ascii=False))
        if ls_multi_scores:
            print("  - Per-criterion:")
            print(json.dumps({f"ls_{k}": float(v) for k, v in ls_multi_scores.items()}, indent=2, ensure_ascii=False))
        if isinstance(ls_judge_reasoning, dict):
            print("  - Reasoning:")
            print(json.dumps(ls_judge_reasoning, indent=2, ensure_ascii=False))
        else:
            print(f"  - Reasoning: {ls_judge_reasoning if ls_judge_reasoning else 'N/A'}")

    if run_gpt_j:
        print("\n[Custom GPT Judge 결과 (GPT)]")
        gpt_scores = {"overall_gpt": final_scores.get("overall_gpt")}
        print(json.dumps({k: (f"{v:.4f}" if isinstance(v, float) else str(v))
                          for k, v in gpt_scores.items() if v not in (None, "")}, indent=2, ensure_ascii=False))
        print(f"  - Explanation: {gpt_judge_reasoning if gpt_judge_reasoning else 'N/A'}")
        if gpt_reconverted_sentence:
            print(f"  - Reconverted Korean: {gpt_reconverted_sentence}")
            print(f"  - Compared Against: {gpt_reconverted_reference_sentence if gpt_reconverted_reference_sentence else command}")
            print(f"  - Same As Input: {gpt_reconverted_same}")
            if gpt_reconverted_reasoning:
                print(f"  - Reconverted Reasoning: {gpt_reconverted_reasoning}")

    print("\n[⏱️ 생성 타이밍 / 사용량]")
    timing_payload = {
        "elapse_time": elapse_time,
        "report_time": report_time,
        "llm_prompt_tokens": llm_prompt_tokens,
        "llm_completion_tokens": llm_completion_tokens,
        "llm_total_tokens": llm_total_tokens,
    }
    print(json.dumps({k: (v if v is not None else "") for k, v in timing_payload.items()}, indent=2, ensure_ascii=False))

    print("\n[최종 통합 점수 (Overall)]")
    overall_final_val = final_scores.get("overall_final")
    overall_final_str = f"{overall_final_val:.4f}" if isinstance(overall_final_val, float) else str(overall_final_val)
    used_semantic = f"w_lang*overall_lang + w_gpt*overall_gpt == {W_LANG:.3f}*overall_lang + {W_GPT:.3f}*overall_gpt"
    print(f"  - overall_final: {overall_final_str} (Semantic used: {used_semantic})")
    print(f"  - final_status [PASS/PARTIAL/FAIL]: {final_status_label}")

    # 단일 행일 때만, 멀티라인일 때만, 병렬 덤프
    import os as _os
    if _os.getenv("JOI_BATCH", "0") != "1":
        # 후보 JSON 문자열(원본 또는 pretty) 준비
        cand_src = generated_code_json_str if generated_code_json_str else json.dumps(candidate_json, ensure_ascii=False)
        cand_pretty = _pretty_json(cand_src)

        # 대표 GT: evidence에 저장된 값 우선, 없으면 첫 GT fall-back
        rep_gt_src = ""
        try:
            rep_gt_src = det_eval_results["evidence"].get("best_gt_json", "")
        except Exception:
            rep_gt_src = ""
        if not rep_gt_src and gt_str_list:
            rep_gt_src = gt_str_list[0]
        rep_gt_pretty = _pretty_json(rep_gt_src)

        rep_idx = "—"
        try:
            rep_idx = det_eval_results["evidence"].get("best_gt_index", "—")
        except Exception:
            pass
        # 멀티라인이면 병렬 출력
        if ("\n" in cand_pretty) or ("\n" in rep_gt_pretty):
            _print_side_by_side_json(
                title_left=f"Candidate JSON (model={full_model_name})",
                left_text=cand_pretty,
                title_right=f"Representative GT JSON (idx={index_str})",
                right_text=rep_gt_pretty,
                col_width=90
            )
    return output_data

# --- (E) 배치 실행 및 집계 함수 (새로 추가) ---
def run_batch_evaluation(df: pd.DataFrame, 
                         category_filter: Optional[int] = None, 
                         modes: List[str] = ["det"], 
                         model_version: str = 
                         "version0_9", 
                         family: str = "joi", 
                         out_dir="./artifacts"):
    """
    DataFrame을 받아 조건에 맞는 행들을 일괄 테스트하고, 최종 결과를 집계하여 보여줍니다.
    """
    print(f"\n🚀 Starting Batch Evaluation (Category={category_filter if category_filter else 'ALL'}, Modes={modes})")
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_path = (
        f"{out_dir}/"
        f"result_{family}_{model_version}_{timestamp}.csv"
    )

    results = []
    
    # 1. 필터링
    if category_filter is None or int(category_filter) == 0:
        target_indices = df.index.tolist()
    else:
        target_indices = []
        for idx, row in df.iterrows():
            try:
                cat = float(row.get("category", -1))
                if int(cat) == int(category_filter):
                    target_indices.append(idx)
            except:
                continue

    print(f"📋 Total targets: {len(target_indices)} rows.")

    # 2. 실행 루프
    success_cnt = 0
    fail_cnt = 0
    partial_cnt = 0
    errors = 0

    scores_final = []
    
    # DET 점수 항목별 누적 (추가)
    det_sum = {
        "overall_deterministic": [],
        "syntax_schema": [],
        "logic_rules": [],
        "function_calls": [],
        "semantic_intent_z3": []
    }
    
    pbar = tqdm(target_indices, desc="Evaluating")
    for idx in pbar:
        try:
            # run_local_test 호출 (batch_context=True로 설정하여 개별 로그 최소화)
            res = run_local_test(
                modes=modes,
                row_index=idx,
                model_version_path=model_version,
                family_token=family,
                batch_context=True
            )
            
            if res:
                results.append(res)
                status = res.get("final_status", "fail")
                score = res.get("overall_final", 0.0)
                
                if status == "pass": success_cnt += 1
                elif status == "partial": partial_cnt += 1
                else: fail_cnt += 1
                
                if score is not None and score != "":
                    scores_final.append(float(score))
                
                # DET 점수 누적
                for key in det_sum:
                    val = res.get(key)
                    if val is not None and val != "":
                        det_sum[key].append(float(val))

                # --- [추가됨] 진행 상황 업데이트 (postfix) ---
                pbar.set_postfix({
                    'Pass': success_cnt, 
                    'Partial': partial_cnt, 
                    'Fail': fail_cnt
                })
            else:
                errors += 1
                
        except Exception as e:
            print(f"Error at index {idx}: {e}")
            errors += 1

    # 3. 최종 리포트 출력
    total_run = len(results)
    avg_score = sum(scores_final) / len(scores_final) if scores_final else 0.0
    pass_rate = (success_cnt / total_run * 100) if total_run > 0 else 0.0

    print("\n" + "="*50)
    print(f"📊 Batch Evaluation Summary (Category: {category_filter})")
    print("="*50)
    print(f"Total Rows Processed: {total_run}")
    print(f"Execution Errors    : {errors}")
    print("-" * 30)
    print(f"✅ PASS     : {success_cnt} ({pass_rate:.1f}%)")
    print(f"⚠️ PARTIAL  : {partial_cnt}")
    print(f"❌ FAIL     : {fail_cnt}")
    print("-" * 30)
    print(f"⭐ Avg Score: {avg_score:.4f}")
    
    # DET 점수 통계 출력
    print("\n[Detailed DET Scores Average]")
    for key, vals in det_sum.items():
        avg = sum(vals) / len(vals) if vals else 0.0
        print(f"  - {key:<22}: {avg:.4f} (n={len(vals)})")

    results_df = pd.DataFrame(results)

    if len(results_df) > 0:
        import os
        os.makedirs(out_dir, exist_ok=True)
        results_df.to_csv(result_path, index=False, encoding="utf-8-sig")
        print(f"💾 Results saved to: {result_path}")
    else:
        print("⚠️ No results to save.")        
    print("="*50 + "\n")

    return results_df


# --- (F) 기본 LangSmith 모드용 더미 정의(필요 시 확장) ---
try:
    from langsmith.evaluation import RunEvaluator, EvaluationResult
    from langsmith.schemas import Example, Run
    LANGSMITH_AVAILABLE = True
except ImportError:
    RunEvaluator = object
    EvaluationResult = dict
    Example = dict
    Run = dict
    LANGSMITH_AVAILABLE = False
    pass

class JOIHybridDeterministicEvaluator(RunEvaluator):
    def evaluate_run(self, run: Run, example: Optional[Example] = None) -> List[EvaluationResult]:
        return []

class JOISimilarityEvaluator(RunEvaluator):
    def evaluate_run(self, run: Run, example: Optional[Example] = None) -> EvaluationResult:
        return EvaluationResult()

def load_candidate_from_dataset(inputs: dict) -> Dict[str, Any]:
    return {"output": inputs.get("candidate", {})}

def setup_langsmith_dataset(client: Any, csv_path: str, dataset_name: str) -> str:
    return dataset_name  # 필요 시 실제 구현

def main_langsmith(selected_cats=None, output_dir: str = "."):
    """기본 실행: 데이터셋 전체에 대해 hybrid 수행 (EVAL_LIMIT 로 제한 가능).
       selected_cats: Set[int] | None
    """
    if selected_cats is None:
        selected_cats = set()

    print("--- ☁️ Batch Hybrid Evaluation (DET+LANG+GPT) over dataset ---")
    try:
        data_path = _resolve_project_path(config.DATA_FILE_PATH)
        df = pd.read_csv(str(data_path), encoding="utf-8-sig")
    except Exception as e:
        print(f"데이터 파일 로드 실패: {e}")
        return

    # EVAL_LIMIT (head) 적용
    limit = os.getenv("EVAL_LIMIT")
    if limit and str(limit).isdigit():
        df = df.head(int(limit))
        print(f"  ▶ EVAL_LIMIT={limit} 적용")

    # 카테고리 필터 적용
    df_f, positions = _filter_df_by_categories(df, selected_cats)

    # 선택된 위치 인덱스로 루프
    for pos in tqdm(positions, desc="Batch Hybrid"):
        try:
            # 기본: joi 가족, 기존 기본 버전            
            default_version = getattr(config, "DEFAULT_MODEL_VERSION_PATH", config.DEFAULT_MODEL_VERSION)
            run_local_test(["hybrid"], pos, default_version,
                           family_token="joi", batch_context=True, output_dir=output_dir)
        except Exception as e:
            print(f"[row {pos}] 오류: {e}")

# --- (F) 메인 라우터 ---
if __name__ == "__main__":
    args = sys.argv[1:]
    modes = []
    row_idx_str = None
    model_ver = None
    family_token = "joi"  # 기본 'joi'
    output_dir = os.getenv("JOI_EVAL_OUTPUT_DIR", ".")
    selected_cats = set()  # 선택된 카테고리 (정수)
    valid_modes = {"det", "lang", "gpt", "hybrid"}
    family_tokens = {"joi", "cap", "qwen"}

    other_tokens = []
    i = 0
    while i < len(args):
        arg = args[i]
        low = arg.lower()

        if low in valid_modes:
            modes.append(low)
            i += 1
            continue
        elif low in family_tokens:
            family_token = low
            i += 1
            continue
        elif low == "cat":
            # cat 다음 연속 토큰들 중 숫자/쉼표/하이픈/공백만 모아 파싱
            j = i + 1
            parts = []
            while j < len(args):
                nxt = args[j]
                nxt_low = nxt.lower()
                # 다음 제어 토큰(모드/패밀리) 나오면 종료
                if nxt_low in valid_modes or nxt_low in family_tokens:
                    break
                # 숫자/쉼표/하이픈/공백만 포함되면 계속 수집
                if re.fullmatch(r"[0-9,\-\s]+", nxt):
                    parts.append(nxt)
                    j += 1
                    continue
                # 그 외 토큰을 만나면 종료
                break
            cat_spec = " ".join(parts)
            selected_cats.update(_parse_cat_values(cat_spec))
            i = j
            continue
        elif low == "--out-dir":
            if i + 1 >= len(args):
                print("오류: --out-dir 다음에 출력 디렉터리가 필요합니다.")
                sys.exit(1)
            output_dir = args[i + 1]
            i += 2
            continue
        elif low.startswith("--out-dir="):
            output_dir = arg.split("=", 1)[1] or "."
            i += 1
            continue
        elif arg.isdigit() and row_idx_str is None:
            row_idx_str = arg
            i += 1
            continue
        else:
            other_tokens.append(arg)
            i += 1

    # 환경변수(옵션) JOI_CATS="1,3,5"도 지원 (CLI와 합집합)
    env_cats = os.getenv("JOI_CATS", "").strip()
    if env_cats:
        selected_cats.update(_parse_cat_values(env_cats))

    if other_tokens:
        model_ver = other_tokens[-1]

    if not model_ver:
        if family_token == "cap":
            model_ver = getattr(config, "CAP_DEFAULT_VERSION", "files")
        else:
            model_ver = config.DEFAULT_MODEL_VERSION

    # ✅ 추가: 모드만 주어지고 row_index가 없는 경우 → 전 행 배치 실행 (버전/패밀리 반영)
    if modes and row_idx_str is None:
        print(f"--- ☁️ Batch ({'+'.join(modes).upper()}) with family={family_token}, version={model_ver} ---")
        try:
            data_path = _resolve_project_path(config.DATA_FILE_PATH)
            df = pd.read_csv(str(data_path), encoding="utf-8-sig")
        except Exception as e:
            print(f"데이터 파일 로드 실패: {e}")
            sys.exit(1)

        # ✅ 먼저 카테고리 필터 적용
        df_f, positions = _filter_df_by_categories(df, selected_cats)

        # (선택) EVAL_LIMIT 적용은 필터 후에 하는 것이 직관적입니다.
        limit = os.getenv("EVAL_LIMIT")
        if limit and str(limit).isdigit():
            positions = positions[:int(limit)]
            print(f"  ▶ EVAL_LIMIT={limit} 적용 (after category filter)")

        from tqdm import tqdm
        for pos in tqdm(positions, desc="Batch"):
            try:
                run_local_test(modes, pos, model_ver, family_token=family_token, batch_context=True, output_dir=output_dir)
            except Exception as e:
                print(f"[row {pos}] 오류: {e}")
        sys.exit(0)



    # 기존 단일 행/기본 배치 분기 유지
    if modes and row_idx_str:
        try:
            row_idx = int(row_idx_str)
            # 선택 카테고리와 불일치 시 스킵
            if not _row_matches_selected_cats(row_idx, selected_cats):
                print(f"⚠️ Row {row_idx} is not in selected categories {sorted(selected_cats)}. Skipped.")
                sys.exit(0)
            run_local_test(modes, row_idx, model_ver, family_token=family_token, output_dir=output_dir)
        except Exception as e:
            print(f"❌ 로컬 테스트 오류: {e}")
            import traceback; traceback.print_exc()
    elif not modes and len(args) == 0:
        # 기본 하이브리드 배치 (카테고리 반영)
        main_langsmith(selected_cats, output_dir=output_dir)
    else:
        # Help message
        if not row_idx_str and modes:
            print("오류: 로컬 테스트 모드 지정 시 row_index가 필요합니다.")
        elif row_idx_str and not modes and len(args) > 0:
            print("오류: row_index 지정 시 모드가 필요합니다.")
        print("\n사용법:")
        print("  python main_evaluator.py                            (전체 데이터 hybrid 배치 평가)")
        print("  python main_evaluator.py [모드들] [family] {row_index} [model_ver] [--out-dir DIR]")
        print("    [모드들]: det | lang | gpt | hybrid | det lang | det gpt | lang gpt | det lang gpt")
        print("    [family]: joi | cap | qwen (선택, 기본: joi)")
        print("    {row_index}: CSV의 0-based 행 번호")
        print("    [model_ver]: 모델 버전 (예: version0_6, files; 기본값: family 별 기본)")
        print("    [--out-dir DIR]: result_<model>.csv 저장 디렉터리 (기본: 현재 디렉터리)")
        print("\n예시:")
        print("  python main_evaluator.py hybrid 20")
        print("  python main_evaluator.py hybrid cap 20")
        print("  python main_evaluator.py det lang joi 5 version0_6")
