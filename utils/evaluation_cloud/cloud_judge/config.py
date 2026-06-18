# /joi_lang_evaluation/config.py
import os

"""
Cloud semantic judge configuration.

This module intentionally reads API credentials only from the runtime
environment. It does not enable LangSmith/LangChain tracing by default and
does not provide placeholder or fallback secrets.
"""


def get_openai_api_key():
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("JOI_EVAL_OPENAI_API_KEY")
        or os.environ.get("JOI_V15_OPENAI_API_KEY")
    )


def get_optional_langsmith_api_key():
    return (
        os.environ.get("LANGSMITH_API_KEY")
        or os.environ.get("LANGCHAIN_API_KEY")
    )


def get_openai_base_url():
    return os.environ.get("OPENAI_BASE_URL")


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def langsmith_tracing_enabled() -> bool:
    return _env_truthy("LANGSMITH_TRACING") or _env_truthy("LANGCHAIN_TRACING_V2")


def configure_optional_langsmith_environment() -> None:
    os.environ.setdefault("LANGSMITH_TRACING", "false")
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
    if langsmith_tracing_enabled():
        key = get_optional_langsmith_api_key()
        if key and not os.environ.get("LANGCHAIN_API_KEY"):
            os.environ["LANGCHAIN_API_KEY"] = key


def require_openai_api_key(context: str = "OpenAI judge") -> str:
    key = get_openai_api_key()
    if not key:
        raise RuntimeError(
            f"{context} requires OPENAI_API_KEY, JOI_EVAL_OPENAI_API_KEY, "
            "or JOI_V15_OPENAI_API_KEY in the environment."
        )
    return key


def build_chat_openai(model: str, temperature: float = 0.0, context: str = "OpenAI judge"):
    from langchain_openai import ChatOpenAI

    configure_optional_langsmith_environment()
    api_key = require_openai_api_key(context)
    base_url = get_openai_base_url()
    kwargs = {"model": model, "temperature": temperature, "api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    try:
        return ChatOpenAI(**kwargs)
    except TypeError:
        legacy_kwargs = {
            "model": model,
            "temperature": temperature,
            "openai_api_key": api_key,
        }
        if base_url:
            legacy_kwargs["openai_api_base"] = base_url
        return ChatOpenAI(**legacy_kwargs)


configure_optional_langsmith_environment()

# --- 2. Project Configuration ---
LANGSMITH_PROJECT_NAME = "JOI-Lang-Hybrid-Evaluation-v5-DynamicGT"
LANGSMITH_DATASET_NAME = "JOI-Lang-Dataset-v1-DynamicGT"
DATA_FILE_PATH = "../../datasets/JOICommands-280.csv"

# --- 3. Model Families (NEW) ---
# family => module + default version
MODEL_FAMILIES = {
    # 기존 JOI 생성기(gpt_mg)
    "joi": {
        "module": "gpt_mg",
        # 기존 파이프라인 기본 버전 (원래 DEFAULT_MODEL_VERSION_PATH 사용)
        "default_version": "version0_9"
    },
    # CAP 생성기(gpt_cap)
    "cap": {
        "module": "gpt_cap",
        # gpt_cap/run.py가 stage_2.config_loader를 내부에서 사용하므로 stage_2를 기본 버전으로 둠
        "default_version": "stage_2"
    },
    "qwen": {
        "module": "qwen",
        # gpt_cap/run.py가 stage_2.config_loader를 내부에서 사용하므로 stage_2를 기본 버전으로 둠
        "default_version": "version0_2"
    },
}

# === Final scoring weights (LS sub-criteria + GPT) ===
# 'ls_<key>'에서 <key> 이름과 아래 weight 키가 일치해야 함.
LS_CRITERIA_WEIGHTS = dict(
    semantic_intent=0.5,
    time_period=0.15,
    device_service=0.15,
    conditions=0.1,
    side_effects=0.1,
)

# GPT Judge 단일 점수에 곱할 스칼라 가중치 :# config.GPT_SCORE_WEIGHT 를 W_GPT(0..1)로 해석, W_LANG=1-W_GPT
GPT_SCORE_WEIGHT = 0.2


# 기본 family 및 버전 (하위호환 유지)
DEFAULT_FAMILY = "joi"
DEFAULT_MODEL_PATH = MODEL_FAMILIES[DEFAULT_FAMILY]["module"]
DEFAULT_MODEL_VERSION = MODEL_FAMILIES[DEFAULT_FAMILY]["default_version"]

# CSV 컬럼
CANDIDATE_CODE_COLUMN = "gt1"
COMMAND_COLUMN = "command_eng"

# LangSmith-like LLM-as-a-Judge에 사용할 모델
LS_JUDGE_MODEL = "gpt-4o"
CUSTOM_GPT_JUDGE_MODEL = "gpt-4o"

# --- 4. Scoring Rubric (결정론적 점수 포함) ---
# 출처: meta_prompt_system.md
WEIGHTS = {
    "syntax_schema": 0.30,
    "logic_rules": 0.25,
    "function_calls": 0.25,
    "semantic_intent": 0.20 # 'det' 모드에서는 이 키를 Z3/AST 점수에 매핑
}


# --- 5. Semantic Intent (LLM-as-a-Judge) 기준 프롬프트 문자열 ---
# 다중 기준 세분화
SEMANTIC_JUDGE_CRITERIA = {
    "semantic_intent": "명령 의도를 충실히 반영했는가?",
    "time_period": "cron/period가 의도와 일치하는가?",
    "device_service": "대상 디바이스/서비스가 정확한가?",
    "conditions": "조건/분기 로직이 정확한가?"
}
# 전역 가이드 프롬프트(문자열): 단일 Judge에도 쓰이고,
# 다중 기준 Judge에선 'Optional Global Guidance'로 주입되어 공통 가이드로 활용됨
SEMANTIC_JUDGE_CRITERIA_PROMPT = """
**JOI Lang 의미론적 정확성 평가 기준:**

당신은 JOI Lang DSL 전문가입니다. 'command'(명령어)의 의도와 'output'(후보 코드)의 실제 동작을 비교하여 0.0(완전 불일치)에서 1.0(완전 일치) 사이의 점수를 매기십시오.

1.  **의도 일치(Intent Fulfillment):**
    * 'command'에서 요청한 모든 핵심 기능(예: "10초마다", "비가 오면")이 'output' 코드에 정확히 구현되었는가?

2.  **스케줄링 정확성(Scheduling Correctness):**
    * `cron` 표현식이 'command'의 시간 조건과 일치하는가?
    * `period` 값이 'command'의 주기(예: -1=1회, 0=무한, 10000=10초)와 일치하는가?
    * 'command'의 의도(예: '카운터')에 맞게 `:=`(1회 초기화)와 `=`(매번 초기화)가 올바르게 사용되었는가? (출처: input_eval_agent.md)

3.  **조건부 로직(Conditional Logic, 조건/분기 및 'wait until'의 의미):**
    * `if` 또는 `spinning` 조건문이 'command'의 제약 조건(예: "온도가 25도 이상이면")을 올바르게 반영하는가?
    * `spinning`이 `period == -1` 제약과 함께 올바르게 사용되었는가? (출처: input_eval_agent.md)

4.  **완전성(Completeness & No Hallucination) 및 환각 방지(불필요 동작, 존재하지 않는 서비스 금지):**
    * 'command'에서 요청하지 않은 불필요한 동작이나, 존재하지 않는 장치/서비스를 호출(환각)하지 않았는가?
    * for/while 절대 금지: `for` 또는 `while` 루프를 사용하지 않았는가? (출처: input_eval_agent.md)
    
"""


# --- 6. Semantic Intent (Custom GPT Judge) 기준 프롬프트 ---

# (A) BATCH 모드 프롬프트 — cloud_similarity.py의 system_prompt를 그대로 사용
CUSTOM_GPT_JUDGE_BATCH_PROMPT = """
# JOI Lang Semantic Similarity Evaluator (Batch Mode)

You are an advanced AI model specialized in evaluating the semantic similarity between pairs of "JOI lang" code snippets: a "Generated Code" and a "Ground Truth Code". Your evaluation must focus on the *intended execution meaning, core logic, and overall behavior*, not just superficial syntactic similarity. You will analyze a batch of up to 50 code pairs provided in a single input string.

## Context and Knowledge:
You should leverage your understanding of Domain Specific Languages (DSLs) for IoT/automation. The previously provided detailed descriptions of "SoP-lang" (including its syntax, grammar, keywords like `action_behavior`, `if_statement`, `wait_statement`, `condition_list`, `tag_list`, `action_input`, `period_time`, etc.) should be considered highly analogous to JOI lang. Assume JOI lang shares similar structural and semantic constructs unless the code itself clearly indicates otherwise.

## Core Evaluation Aspects (Inspired by compare_soplang_ir.py logic):

Your similarity assessment for each pair should be a holistic judgment based on the following, weighted conceptually:

1.  **Overall Program Structure & Core Logic (Weight: approx. 40%):**
    *   **Sequence & Type of Statements:** Similarity in the order and types of main statements used (e.g., actions, conditionals, loops, wait constructs).
    *   **Control Flow Equivalence:** How well the structure of control flow constructs matches.
        *   Are `if-else` blocks logically equivalent?
        *   Are loop structures (if any) performing similar iterations or targeting similar conditions?
    *   **Nesting & Ordering:** Correctness of logical block nesting and overall statement order if critical for the script's logic.
    *   Significant structural deviations (e.g., a missing `if` block in the generated code that exists in ground truth, or a fundamentally different sequence of critical actions) should heavily penalize the score for this aspect.

2.  **Action Equivalence (e.g., `action_behavior` in SoP-lang) (Weight: approx. 30%):**
    *   **Target Specification:** Similarity of the targeted services/devices (e.g., based on tags, identifiers).
    *   **Action/Method Name:** The core function/method being called on the target.
    *   **Action Inputs/Parameters:** Similarity of values and types passed as arguments to the action.

3.  **Conditional Logic & Expressions (e.g., `condition_list` in SoP-lang) (Weight: approx. 20%):**
    *   Applicable for `if` statements and conditional `wait until` constructs.
    *   **Semantic Equivalence:** Do the conditions, when evaluated, lead to the same logical outcomes? Consider:
        *   Operands involved in comparisons.
        *   Comparison operators (`==`, `!=`, `>=`, `<=`, `>`, `<`).
        *   Logical connectives (`AND`, `OR`, `NOT`) and grouping.
    *   Conceptually, think if these conditions would be deemed equivalent by a solver like Z3 (as in `are_equivalent` from the Python example).

4.  **Time-based Logic & `wait until` Constructs (Weight: approx. 10%, with special rule):**
    *   **Direct `wait until <period_time>` matches:** Similarity of delay durations and units (e.g., `wait until 10 SEC`).
    *   **Conditional `wait until <condition>` matches:** Assessed under "Conditional Logic".
    *   **SPECIAL RULE for `wait until` vs. `if` for delays:**
        *   If the Ground Truth Code uses a `wait until <period_time>` construct (e.g., `wait until 5 MINUTE`) specifically for creating a delay.
        *   AND the Generated Code implements a *semantically equivalent delay logic* using an `if` statement (or a loop with an `if` checking elapsed time) that achieves the *same delay duration and triggering outcome*.
        *   THEN, for this specific aspect of implementing the delay, the similarity contribution should be considered **80% (0.8)**. The overall score will then be influenced by this 0.8 factored with this aspect's weight and other aspects.
        *   If the `if` construct in the generated code is for a different logical purpose, or doesn't achieve the same delay effect, this special rule does not apply, and it should be evaluated normally under "Conditional Logic" or "Program Structure."

## Scoring Guidelines:
*   For each code pair, derive a single `similarity_score` float between 0.0 and 1.0.
    *   **1.0:** Semantically identical. Minor, non-functional differences like comments or whitespace are acceptable for 1.0.
    *   **0.8 - 0.99:** Highly similar. Minor semantic differences that don't fundamentally change the core outcome or intent. The "wait until vs. if for delay" special rule (if applicable and positive) might lead to scores in this range if other parts are perfect.
    *   **0.5 - 0.79:** Moderately similar. Some key semantic aspects match, but others differ significantly, or a major component is missing/incorrect.
    *   **0.0 - 0.49:** Low similarity. Fundamental differences in logic, core actions, targets, or overall intent.
    *   **0.0** If the Generated Code is completely empty or missing.
*   Provide a `brief_explanation` string if the `similarity_score` is less than 1.0. This explanation should concisely highlight the *most significant semantic differences* that led to the score. If the score is 1.0, the explanation should be an empty string.
*   The explanation should be clear and focused on the core logic, actions, or conditions that differ, without going into excessive detail.Do not penalize the code for using single quotes instead of double quotes for string literals, as this is a stylistic and non-functional difference.

## Special Tolerance Rules:
- **Numeric Representation Tolerance**:
  - Minor differences in numeric formatting (e.g., `30` vs `30.0`) **must be ignored** as long as they are semantically equivalent in the execution context (e.g., temperature thresholds, timer durations).
  - Do **not deduct points** for this difference.

- **Language Consistency in Action Inputs**:
  - If the **action argument text** (e.g., timer name or speech content) is written in a language that **does not match** the language of the user’s command, deduct **0.1** from the final score.
    - For Korean commands, Korean arguments are expected.
    - For English commands, English arguments are expected.
    - Mismatches like `"테스트 타이머"` in an English command or `"Test Timer"` in a Korean command incur a 0.1 penalty.

## Input Format:
You will receive a single string `user_content`. This string contains up to 50 JOI lang code pairs.
Each pair is formatted as:
`Generated Code {generated_code_snippet}`
`Ground Truth Code {ground_truth_code_snippet}`
These pairs are separated by the delimiter "---".

Example snippet of `user_content` with two pairs:
Generated Code IF (#TempSensor.get() > 25) { ALL (#Fan).on(); }
Ground Truth Code IF (#TempSensor.get() > 25) { ALL (#Fan).on(); }
---
Generated Code ALL (#Light).set("OFF"); WAIT_UNTIL(5 SEC); ALL (#Light).set("ON");
Ground Truth Code ALL (#Light).set("OFF"); // Implement 5 sec delay using if
IF (Time.elapsedSinceLastAction() >= 5 SEC) { ALL (#Light).set("ON"); }

## Output Format:
You MUST return a single, valid JSON string that can be directly parsed by json.loads() in Python. This string must represent a LIST of JSON objects. Each object in the list corresponds to one input code pair and must have the following exact structure and keys:

[
  {
    "generated_code": "The exact generated code string from the input pair",
    "ground_truth_code": "The exact ground truth code string from the input pair",
    "cloud_similarity_gpt4o": <float_between_0.0_and_1.0>,
    "explanation": "<string_explanation_if_score_is_less_than_1.0_else_empty_string>"
  }
  // ... more objects for other pairs
]
"""


# (B) SINGLE-PAIR 모드 프롬프트 — fallback (필요 시만 사용)
CUSTOM_GPT_JUDGE_SYSTEM_PROMPT = """
# JOI Lang Semantic Similarity Evaluator (Single Pair Mode)
You are an advanced AI model specialized in evaluating the semantic similarity between one pair of "JOI lang" code snippets: a "Generated Code" and a "Ground Truth Code". Focus on intended meaning, core logic, and behavior.
Return a JSON object:
{
  "cloud_similarity_gpt4o": <0..1>,
  "explanation": "<string>"
}
"""


# --- 7. Final Result Thresholds (overall_final) ---
# 기준:
#   - overall_final < 0.5        -> "fail"
#   - 0.5 <= overall_final < 0.85 -> "partial"
#   - overall_final >= 0.85       -> "pass"
OVERALL_FINAL_FAIL_LT = 0.5
OVERALL_FINAL_PARTIAL_LT = 0.85
