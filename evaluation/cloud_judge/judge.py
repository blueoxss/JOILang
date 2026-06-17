# /joi_lang_evaluation/cloud_judge/judge.py
"""
LangSmith의 LLM-as-a-Judge (Criteria) 빌더 모듈.
- 단일 기준 Judge (단일 점수)
- 다중 기준 Judge (여러 스코어 + 사유)

[중요 보강]
- 'conditions'는 구조적 적합성(STRUCTURAL FIT)만 평가: VALUE-only, 타입/연산자 정합, 매핑 정확성.
  최종 상태 보장은 여기서 감점하지 않는다.

- 'semantic_intent'는 최종/미래 상태 보장(GUARANTEE)을 평가: 지연 후 재확인, 상태 전이, 강제 설정/재시도 등.
  보장이 약하면 이 축에서만 감점.

구조=검증(conditions), 보증=의도(semantic_intent)를 명확히 분리하고
LLM이 혼동해도 후처리 가드레일로 conditions=1.0을 고정한다(구조 합격 시).
"""

from typing import Dict, Optional, Union

try:
    from . import config
except ImportError:
    import config

LS_JUDGE_MODEL = getattr(config, "LS_JUDGE_MODEL", "gpt-4o")

# ===== Default multi-criteria & global guidance =====
DEFAULT_CRITERIA: Dict[str, str] = {
    # ── 보증 전용 축: "최종/미래 상태 달성 보장(Guarantee)"만 평가 ─────────────────────────────
    "semantic_intent": (
        "Goal: Judge whether the PREDICTION guarantees the final desired state implied by the INPUT. "
        "Measure FUTURE-STATE handling quality: delay-then-recheck, state-transition correctness, "
        "forced setting (idempotent ON/OFF), retry/backoff strategies, and race/ambiguity handling. "
        "Do NOT evaluate structural form here (that belongs to 'conditions').\n\n"
        "What to consider (guarantee strength):\n"
        "  • Re-check after delay or event (e.g., wait-until) to confirm target state.\n"
        "  • Correct sign of post-delay condition (e.g., still OFF → turn_on). "
        "    If the sign makes the guarantee weaker/uncertain, deduct here (not in 'conditions').\n"
        "  • Idempotent control: using set-on/off or equivalent patterns that avoid redundant toggles.\n"
        "  • Handling external interference/races (e.g., re-verify, fallback action, limited retries).\n"
        "  • Event-driven patterns preferred over blind polling when applicable.\n\n"
        "What NOT to consider:\n"
        "  • VALUE-only usage in conditions, operator/type shape, catalog mapping → scored in 'conditions'.\n"
        "  • Syntax/grammar-specific details → handled by the deterministic checker.\n\n"
        "Scoring rubric (guideline, continuous in [0,1]):\n"
        "  • Strong guarantee (0.90–1.00): Future-state is reliably achieved with correct re-check "
        "    and appropriate control (e.g., delay→if still OFF then set ON; or wait-until OFF → ON).\n"
        "  • Moderate/weak guarantee (0.60–0.89): Some future handling exists but has flaws or ambiguity "
        "    (e.g., delay→if ON then ON; or missing re-check; or ambiguous toggle that may not ensure end-state).\n"
        "  • No guarantee (0.00–0.59): Future-state is not ensured at all (single read, no re-check, "
        "    misdirected action, or irrelevant condition).\n"
    ),

    # ── 구조 전용 축: "조건식의 구조적 적합성(Structural Fit)"만 평가 ───────────────────────────
    "conditions": (
        "Goal: Evaluate ONLY structural correctness of condition expressions. "
        "This is a PRESENT-STATE structural check, independent of final-state guarantee.\n\n"
        "Must-checks:\n"
        "  • VALUE-only usage in conditions (no FUNCTION calls in predicates).\n"
        "  • Operator/type compatibility (ENUM equality, numeric ranges/units, BOOLEAN tests).\n"
        "  • Device/service mapping correctness (no hallucinations; correct value service; tag/scope valid).\n"
        "  • Proper alias/enum usage (allowed set respected; unit normalization OK).\n"
        "Do NOT deduct here for guarantee weaknesses (e.g., post-delay sign for ON/OFF). "
        "Such issues are scored in 'semantic_intent'.\n\n"
        "Scoring hints:\n"
        "  • 1.0 if structure is sound and types/services are valid (even if future guarantee is debatable).\n"
        "  • Minor structural lapses (e.g., non-fatal alias misuse) → small deduction.\n"
        "  • Using FUNCTION in conditions, clear type mismatch, or invalid service → large deduction.\n"
    ),

    # ── 시간/주기 정확성: delay/period/cron/wait-until 구현의 정합성 ─────────────────────────────
    "time_period": (
        "Evaluate correctness of temporal constructs: delay/period/cron/wait-until.\n\n"
        "Check:\n"
        "  • Delay values and placement (pre/post condition as instructed).\n"
        "  • period semantics: -1 (once), 0 (infinite), >0 ms (interval); penalize busy spin patterns "
        "    (e.g., period(0) + tight loop) unless explicitly requested.\n"
        "  • cron expression equivalence (semantic equality acceptable), and appropriate use of wait-until "
        "    for event-driven cases.\n"
        "  • Avoid excessively aggressive polling (e.g., fixed 100ms) when not required.\n"
        "Rubric:\n"
        "  • 1.0 when temporal intent is implemented faithfully (delay/cron/period/wait-until correct).\n"
        "  • Deduct for misplaced delay, wrong repetition model, or harmful spin/polling.\n"
    ),

    # ── 디바이스/서비스 정확성: 선택/시그니처/타입/단위/에일리어스 ──────────────────────────────
    "device_service": (
        "Evaluate correctness of device/service selection and signatures.\n\n"
        "Check:\n"
        "  • No hallucinated devices/services; service exists in the catalog.\n"
        "  • Correct function name and arity; argument types and units within allowed ranges.\n"
        "  • ENUM values come from the allowed set; synonyms/aliases map to valid entries.\n"
        "  • VALUE vs FUNCTION role respected; execution-side effects only via FUNCTION.\n"
        "Rubric:\n"
        "  • 1.0 when mapping is exact and signatures/units/enums are valid.\n"
        "  • Deduct for wrong service, arity/type mismatch, or off-catalog usage.\n"
    ),
}

# 1) conditions: GT 구조 일치 시 1.0 고정(치명 구조오류 없으면), 모순/불필요코드 감점 금지
DEFAULT_CRITERIA["conditions"] += (
    "\n\nGT MATCH RULE:\n"
    "- If the predicate structure in PREDICTION matches the REFERENCE (GT) predicates "
    "(same device/value services and operators; alias/unit normalization allowed), "
    "assign conditions=1.0 unless a hard structural error exists "
    "(FUNCTION used in predicate, clear type mismatch, or unknown service).\n"
    "- Do NOT deduct here for contradictory wording or unnecessary extra checks; "
    "such penalties belong ONLY to 'semantic_intent'."
)

# 2) semantic_intent: 실행이 맞더라도 모순/불필요코드가 있으면 여기서만 소폭 감점(≤0.5)
DEFAULT_CRITERIA["semantic_intent"] += (
    "\n\nMUST-APPLY DEDUCTION ANCHORS:\n"
    "• Contradictory post-delay guard (e.g., instruction wants final ON after delay/recheck, "
    "  but PREDICTION uses 'if ON then turn_on' after the delay): "
    "  set semantic_intent = 0.5 (exact), even if execution may still succeed.\n"
    "• Recheck explicitly required but omitted: set semantic_intent ≤ 0.7 (default 0.6).\n"
    "• Redundant/bloated steps that do not strengthen the guarantee: subtract 0.1–0.2 only from semantic_intent.\n"
    "• Do NOT move these deductions to 'conditions'. Conditions is structural-only.\n"
    "\nANALYSIS CHECKLIST (write reasons accordingly):\n"
    "1) Does the code perform a future-state recheck (delay/wait-until) as instructed?\n"
    "2) Is the post-delay sign correct for the desired end-state? (still OFF → turn_on)\n"
    "3) Is the action idempotent and robust to races? (avoid useless toggles)\n"
    "4) Are there unnecessary steps that do not increase guarantee strength?\n"
)

DEFAULT_CRITERIA["semantic_intent"] += (
    "\n\nBROAD CONTRADICTION TAXONOMY (small-impact; deduct ONLY here):\n"
    "• Post-delay sign drift (e.g., after 10s, checking 'ON' then turn_on instead of 'still OFF') → -0.10\n"
    "• Ambiguous toggle that does not guarantee final state (no idempotent set) → -0.10\n"
    "• Missing default/else path that may leave end-state unmet in one branch → -0.05 ~ -0.10\n"
    "• Branch asymmetry that weakens guarantee (one branch enforces, the other is no-op) → -0.05 ~ -0.10\n"
    "• Redundant reads/variables that add no guarantee strength (bloat) → -0.05\n"
    "• Recheck scope drift (rechecking a different property/device than the initial gate) → -0.10 ~ -0.15\n"
    "• Race window left unmitigated when instruction implies reliability (no brief re-verify or idempotent set) → -0.05 ~ -0.10\n"
    "• Trigger/goal conflation (treating the trigger condition as the success condition) → -0.10 ~ -0.15\n"
    "• Negation slip (double-negatives making the end-state ambiguous) → -0.05 ~ -0.10\n"
    "• Unit/threshold semantic drift that likely preserves structure but weakens the intended end-state → -0.05 ~ -0.10\n"
    "\nSOFT IMPACT CAP (non-severe):\n"
    "• For the above generic contradictions, keep the total deduction small. The cumulative deduction for semantic_intent SHOULD NOT exceed 0.20.\n"
    "• Maintain semantic_intent ≥ 0.80 unless a severe anchor applies (e.g., explicitly contradictory post-delay sign).\n"
    "• Severe anchor example (‘contradictory post-delay sign’) may drop to 0.50 as specified above.\n"
    "\nREASONING TEMPLATE (be concise but specific):\n"
    "• Recheck: present/absent and where placed; Post-delay sign: correct/ambiguous; Idempotency: set vs toggle.\n"
    "• Note any contradiction category (from the taxonomy) that applies; explain why it weakens GUARANTEE (not structure).\n"
)


DEFAULT_GLOBAL_GUIDANCE: str = """
You are evaluating code for a domain-specific IoT DSL (JoI-Lang).
Return STRICT JSON only.

SEPARATION PRINCIPLE (very important):
- 'conditions' is STRUCTURAL ONLY (present-state). It checks:
  VALUE-only predicates, operator/type compatibility, valid device/service mapping,
  and correct enum/unit usage. Do NOT deduct here for whether the final state is guaranteed.
- 'semantic_intent' is GUARANTEE of the FUTURE desired state:
  delay-then-recheck, correct post-delay sign, idempotent forcing (set on/off),
  retry/backoff, and race/ambiguity handling.

PRESENT vs FUTURE:
- Present-state reading (e.g., current switch status) → 'conditions'.
- Achieving/guaranteeing the future end-state (after some delay/trigger) → 'semantic_intent'.

TEMPORAL (time_period):
- Verify that delay/period/cron/wait-until matches the instruction. Prefer event-driven
  wait-until over blind busy loops. Penalize harmful spin unless requested.

DEVICE/SERVICE:
- Verify that devices/services exist, signatures/arity are correct, and arguments/types/units/enums are valid.

EXAMPLE (Korean input summarized in English):
Input: "만약 TV가 꺼져 있으면 10초 대기 후 다시 확인하여 켜져 있으면 TV를 켜 줘."
- Candidate A: if OFF → delay(10s) → if still OFF then turn_on()
  scores ≈ conditions=1.0, time_period=1.0, device_service=1.0, semantic_intent≈0.95–1.0 (strong guarantee)
- Candidate B: if OFF → delay(10s) → if ON then turn_on()
  scores ≈ conditions=1.0 (structural fit OK), time_period=1.0, device_service=1.0,
           semantic_intent≈0.75–0.85 (weak/moderate guarantee due to ambiguous final-state logic)
- Candidate C: if OFF then turn_on() (no re-check or delay required by input)
  scores ≈ conditions=1.0, time_period≈0.0–0.3 (temporal mismatch),
           device_service=1.0, semantic_intent≈0.5–0.7 (partial guarantee)

CALIBRATION GUIDANCE:
- Use continuous scoring in [0,1]. Later evaluation may threshold overall metrics (e.g., Exec@1 PASS at 0.85).
- Prefer to keep 'conditions' high if the structure is valid, and reflect future-state doubts in 'semantic_intent'.
- Be concise but explicit in 'rationales' so users can fix either structure or guarantee accordingly.

OUTPUT FORMAT (STRICT JSON only):
{
  "scores": {
    "semantic_intent": <float 0..1>,
    "conditions": <float 0..1>,
    "time_period": <float 0..1>,
    "device_service": <float 0..1>
  },
  "rationales": {
    "semantic_intent": "<short reason>",
    "conditions": "<short reason>",
    "time_period": "<short reason>",
    "device_service": "<short reason>"
  }
}
""".strip()

# 3) 글로벌 가이던스: 최소 정책 요약을 맨 끝에 덧붙임(클램프 원칙 명문화)
DEFAULT_GLOBAL_GUIDANCE += (
    "\n\nSCORING ANCHORS (MUST APPLY):\n"
    "• Contradictory post-delay sign → semantic_intent = 0.5.\n"
    "• Recheck required but missing → semantic_intent ≤ 0.7 (default 0.6).\n"
    "• Pure redundancy/bloat → subtract 0.1–0.2 from semantic_intent only.\n"
    "\nREASONING REQUIREMENT:\n"
    "Return concise but specific rationales per criterion, explicitly citing:\n"
    "  - whether a recheck exists and where,\n"
    "  - the post-delay sign used and why it weakens/strengthens the guarantee,\n"
    "  - any redundancy and why it does/does not improve guarantee.\n"
)

DEFAULT_GLOBAL_GUIDANCE += (
    "\n\nSOFT-IMPACT POLICY (apply to semantic_intent only):\n"
    "• For broad, non-severe contradictions, the TOTAL deduction SHOULD be ≤ 0.20 and the final semantic_intent SHOULD remain ≥ 0.80.\n"
    "• Keep conditions unaffected (structural-only). Do NOT shift these deductions to 'conditions'.\n"
    "\nCONTRADICTION CHECKLIST (for semantic_intent rationales):\n"
    "1) Future recheck present & correctly placed?\n"
    "2) Post-delay sign matches the desired end-state?\n"
    "3) Idempotent action vs ambiguous toggle?\n"
    "4) Any branch asymmetry / missing else that weakens the guarantee?\n"
    "5) Scope/target drift (property/device) in the recheck?\n"
    "6) Unnecessary steps that add no guarantee strength?\n"
)

def get_single_criteria_judge(criteria_prompt: Union[str, Dict[str, str]]):
    """단일 점수 산출 Judge 빌더 (criteria_prompt가 dict면 텍스트로 정규화)."""
    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:
        print(f"⚠️ LLM Judge 초기화 실패 (langchain_openai 미설치): {e}")
        return None

    # dict → text
    if isinstance(criteria_prompt, dict):
        crit_text = "\n".join([f"- {k}: {v}" for k, v in criteria_prompt.items()])
    elif isinstance(criteria_prompt, str) and criteria_prompt.strip():
        crit_text = criteria_prompt.strip()
    else:
        crit_text = (
            "Judge whether the PREDICTION's code fulfills the INPUT instruction. "
            "Use the REFERENCE code as guidance if provided. Return JSON with 'score' in [0,1] and 'reasoning'."
        )

    llm = ChatOpenAI(model=LS_JUDGE_MODEL, temperature=0)

    class _Judge:
        def __init__(self, llm, crit_text):
            self.llm = llm
            self.crit_text = crit_text

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json, re as _re
            sys_prompt = (
                "You are a strict evaluator for a DSL (JoI-Lang). "
                "Only evaluate intent alignment, not syntax correctness. Return STRICT JSON."
            )
            user_prompt = f"""
## CRITERIA
{self.crit_text}

## INPUT
{input}

## REFERENCE
{reference}

## PREDICTION
{prediction}

Respond ONLY with a JSON object:
{{
  "score": <float between 0 and 1>,
  "reasoning": "<short explanation>"
}}
""".strip()
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res))
            except Exception as e:
                return {"score": 0.0, "reasoning": f"invoke_error: {e}", "raw": ""}

            # JSON 추출
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


def get_multi_criteria_judge(criteria: Dict[str, str], guidance_prompt: str = ""):
    """다중 기준 Judge (여러 스코어 + 근거). guidance_prompt는 'Optional Global Guidance'로 주입."""
    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:
        print(f"⚠️ LLM Multi Judge 초기화 실패: {e}")
        return None
    if not isinstance(criteria, dict) or not criteria:
        return None

    llm = ChatOpenAI(model=LS_JUDGE_MODEL, temperature=0)

    class _MultiJudge:
        def __init__(self, llm, criteria, guidance):
            self.llm = llm
            self.criteria = criteria
            self.guidance = guidance or ""

        def evaluate_strings(self, prediction: str, input: str, reference: str = ""):
            import json as _json
            crit_text = "\n".join([f"- {k}: {v}" for k, v in self.criteria.items()])
            sys_prompt = (
                "You are a strict evaluator for a DSL (JoI-Lang). "
                "Return STRICT JSON with per-criterion scores in [0,1] and short rationales. "
                "Follow the separation principle in the guidance."
            )
            user_prompt = f"""
## CRITERIA
{crit_text}

## (Optional Global Guidance)
{(self.guidance or "").strip()}

## INPUT
{input}

## REFERENCE
{reference}

## PREDICTION
{prediction}

Respond ONLY with a JSON object:
{{
  "scores": {{
    "semantic_intent": <float 0..1>,
    "conditions": <float 0..1>,
    "time_period": <float 0..1>,
    "device_service": <float 0..1>
  }},
  "rationales": {{
    "semantic_intent": "<short reason>",
    "conditions": "<short reason>",
    "time_period": "<short reason>",
    "device_service": "<short reason>"
  }}
}}
""".strip()
            try:
                res = self.llm.invoke([{"role": "system", "content": sys_prompt},
                                       {"role": "user", "content": user_prompt}])
                text = getattr(res, "content", str(res)).strip()
            except Exception as e:
                return {"scores": {}, "rationales": {"_error": f"invoke_error: {e}"}, "raw": ""}

            try:
                start = text.find("{"); end = text.rfind("}")
                js = text[start:end+1] if start != -1 and end != -1 else "{}"
                obj = _json.loads(js)
            except Exception:
                obj = {}
            scores = obj.get("scores", {})
            rats = obj.get("rationales", {})

            # 점수 클램프 및 누락 키 보정
            clean_scores = {}
            for k in ["semantic_intent", "conditions", "time_period", "device_service"]:
                v = scores.get(k, 0.0)
                try:
                    v = float(v)
                except Exception:
                    v = 0.0
                clean_scores[k] = max(0.0, min(1.0, v))

            # 합성 결과
            return {"scores": clean_scores, "rationales": rats, "raw": text}

    return _MultiJudge(llm, criteria, guidance_prompt)


# 편의 함수: 디폴트 분리 규칙과 가이던스를 적용한 Judge 빌더
def get_default_multi_criteria_judge():
    """
    DEFAULT_CRITERIA와 DEFAULT_GLOBAL_GUIDANCE를 사용해 다중 기준 Judge를 생성.
    main_evaluator 등에서 곧바로 호출 가능.
    """
    return get_multi_criteria_judge(DEFAULT_CRITERIA, DEFAULT_GLOBAL_GUIDANCE)
