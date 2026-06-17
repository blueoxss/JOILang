# 🚀 프롬프트: LangSmith 네이티브 JOI Lang 하이브리드 평가 파이프라인 생성

**To (Code Generation AI):**

당신은 LangChain과 LangSmith 프레임워크에 정통한 선임 소프트웨어 아키텍트(Senior Software Architect)입니다.

핵심 요구사항인 **(A)결정론적 Python 검증기**와 **(B)LangSmith 내장 LLM-as-a-Judge**를 결합한 하이브리드 루브릭을 구현하며, **(C)동적 Ground Truth 열 처리** 로직을 포함합니다.

당신의 임무는 `joi_lang_evaluation`라는 이름의 Python 프로젝트를 위한 전체 코드를 **하나의 응답**으로 생성하는 것입니다. 이 프로젝트의 목적은 **LangSmith의 네이티브 평가 프레임워크(`run_on_dataset`)**를 사용하여, **"하이브리드 루브릭(Hybrid Rubric)"**을 구현하는, 논문에 인용 가능한(publicly reliable) 평가 파이프라인을 구축하는 것입니다.

## 🎯 핵심 요구사항 (엄격히 준수)

1.  **하이브리드 루브릭:** 평가는 반드시 두 가지 유형의 검증기를 결합해야 합니다.
    * **[A] 결정론적 검증 (Python):** `eval_tools/`의 (Mock) Python 함수들을 래핑하는 LangSmith **`CustomEvaluator`** 클래스를 구현해야 합니다. 이는 `syntax_schema`, `logic_rules`, `function_calls` 점수를 채점합니다.
    * **[B] 의미론적 검증 (LLM-as-a-Judge):** **LangSmith의 내장 `Criteria` 평가자**를 사용해야 합니다. 이 평가자는 `cloud_judge/judge.py` 모듈에서 설정(configure)하고, `main_evaluator.py`가 이를 임포트하여 `semantic_intent` 점수를 채점합니다. **절대로 `cloud_judge`에서 `ChatOpenAI` 등을 직접 호출하지 마십시오.**

2.  **동적 Ground Truth (GT) 처리:**
    * `data/output_250710.csv` 파일은 `gt1`, `gt2`, `gt3`, ... `gtN`과 같이 **알 수 없는 개수의 Ground Truth 열**을 포함합니다.
    * `main_evaluator.py`의 `setup_langsmith_dataset` 함수는 **`gt`로 시작하는 모든 열을 동적으로 찾아** 해당 내용을 JSON으로 파싱하고, 이들을 **하나의 리스트**(`List[dict]`)로 묶어 `Example.outputs['ground_truths']` 필드에 저장해야 합니다.

3.  **데이터셋 로직:**
    * `main_evaluator.py`는 `run_on_dataset`을 사용하여 *기존에 생성된 코드*를 평가해야 합니다.
    * `setup_langsmith_dataset` 함수는 CSV의 'candidate' 코드 열(예: `config.CANDIDATE_CODE_COLUMN`)을 `Example.inputs['candidate']`에 저장해야 합니다.
    * 평가 대상 "모델"(`llm_or_chain_factory`)은 LLM을 호출하는 대신, `Example.inputs['candidate']`를 그대로 `{"output": ...}`으로 반환하는 간단한 함수여야 합니다.

4.  **파일 구조 준수:**
    * 제시된 파일 구조를 정확히 따르고, 각 파일의 내용을 생성해 주십시오.

---

## 프로젝트 파일 구조
제시된 파일 구조에 따라 각 파일의 내용을 생성해 주십시오.
### Project file structre
/joi_lang_evaluation/
├── main_evaluator.py       # (✅ 1. 메인 파이프라인 실행기)
├── config.py               # (✅ 2. 설정 파일: API 키, 가중치)
|
├── eval_tools/             # (✅ 3. 사용자의 기존 Python 도구)
│   ├── __init__.py
│   ├── syntax_checker.py   # (문법/로직 검증)
│   ├── similarity_checker.py # (유사도/정규화)
│   └── policy_checker.py   # (함수 호출 검증)
|
├── cloud_judge/            # (✅ 4. 사용자의 Cloud "GPT" 코드)
│   ├── __init__.py
│   └── judge.py            # (Langsmith LLM-as-a-judge API 호출)
│   └── judge_gpt.py        # (GPT LLM-as-a-judge API 호출)
|
└── data/                   # (✅ 5. 평가 데이터)
    └── output_250710.csv   # (사용자가 업로드한 CSV)


---

아래 1~5번에 대한 내용은 각 파일의 역할과 코드 예시를 설명한거야. 너가 더 정확하고 훌륭하게 코드를 작성해줘.

## 1. `config.py` 생성

모든 설정, API 키, 프로젝트 이름, 가중치, 그리고 LLM-as-a-Judge를 위한 핵심 프롬프트(기준)를 관리합니다.

``` python
"""
joi_lang_evaluation 프로젝트의 모든 설정을 관리합니다.
API 키, 프로젝트 이름, 평가 가중치, 데이터 경로, LLM-as-a-Judge 기준.
"""
import os
from langchain.evaluation import Criteria

# --- 1. LangSmith & LLM API Keys ---
# (스크립트 실행 시 환경 변수에서 읽어옵니다)
# LangSmith 추적을 활성화합니다.
os.environ["LANGCHAIN_TRACING_V2"] = "true" 
# LangSmith API 키 설정 (필수)
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGSMITH_API_KEY", "YOUR_LANGSMITH_API_KEY")
# LangSmith 내장 Judge가 사용할 LLM의 API 키 (예: OpenAI)
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")

# --- 2. Project Configuration ---
# LangSmith UI에 표시될 프로젝트 및 데이터셋 이름
LANGSMITH_PROJECT_NAME = "JOI-Lang-Hybrid-Evaluation-v5-DynamicGT"
LANGSMITH_DATASET_NAME = "JOI-Lang-Dataset-v1-DynamicGT"

# 평가할 데이터 CSV 파일 경로
DATA_FILE_PATH = "data/output_250710.csv"
# CSV에서 'candidate' 코드를 가져올 열 이름 (중요: 사용자의 실제 열 이름으로 수정)
CANDIDATE_CODE_COLUMN = "gt1" # 예시: 'output_gpt4o' 또는 'gt1' 등
# CSV에서 'command'를 가져올 열 이름
COMMAND_COLUMN = "command"

# --- 3. Scoring Rubric (참고용) ---
# (이 가중치는 LangSmith 대시보드에서 수동으로 적용하거나, 
#  별도 집계 스크립트에서 사용)
# 출처: meta_prompt_system.md
WEIGHTS = {
    "syntax_schema": 0.30,
    "logic_rules": 0.25,
    "function_calls": 0.25,
    "semantic_intent": 0.20
}

# --- 4. Semantic Intent (LLM-as-a-Judge) 기준 ---
# LangSmith의 내장 `Criteria` 평가자에게 전달될 핵심 프롬프트
# 출처: input_eval_agent.md, meta_prompt_system.md
SEMANTIC_JUDGE_CRITERIA = {
    # 이 키가 LangSmith 대시보드의 'semantic_intent' 점수가 됨
    "semantic_intent": Criteria(
"""
**JOI Lang 의미론적 정확성 평가 기준:**

당신은 JOI Lang DSL 전문가입니다. 'command'(명령어)의 의도와 'output'(후보 코드)의 실제 동작을 비교하여 0.0(완전 불일치)에서 1.0(완전 일치) 사이의 점수를 매기십시오.

1.  **의도 일치(Intent Fulfillment):**
    * 'command'에서 요청한 모든 핵심 기능(예: "10초마다", "비가 오면")이 'output' 코드에 정확히 구현되었는가?

2.  **스케줄링 정확성(Scheduling Correctness):**
    * `cron` 표현식이 'command'의 시간 조건과 일치하는가?
    * `period` 값이 'command'의 주기(예: -1=1회, 0=무한, 10000=10초)와 일치하는가?
    * 'command'의 의도(예: '카운터')에 맞게 `:=`(1회 초기화)와 `=`(매번 초기화)가 올바르게 사용되었는가? (출처: input_eval_agent.md)

3.  **조건부 로직(Conditional Logic):**
    * `if` 또는 `spinning` 조건문이 'command'의 제약 조건(예: "온도가 25도 이상이면")을 올바르게 반영하는가?
    * `spinning`이 `period == -1` 제약과 함께 올바르게 사용되었는가? (출처: input_eval_agent.md)

4.  **완전성(Completeness & No Hallucination):**
    * 'command'에서 요청하지 않은 불필요한 동작이나, 존재하지 않는 장치/서비스를 호출(환각)하지 않았는가?
    * `for` 또는 `while` 루프를 사용하지 않았는가? (출처: input_eval_agent.md)
"""
    )
}
```

---

## 2. eval_tools/ (커스텀 도구 Mock)
main_evaluator.py에서 임포트할 수 있도록, 사용자의 기존 Python 도구를 단순화된 Mock 함수로 구현합니다.

### eval_tools/syntax_checker.py
```python
"""
(Mock) JOI Lang 문법 및 정적 규칙 검증기
- parse_validate: 코드 파싱 및 기본 문법 검사
- static_rules: AST 기반 정적 로직 규칙 검사
"""
import re

def parse_validate(code: str) -> dict:
    """ (Mock) 코드 파싱 및 기본 문법 검사 (input_eval_agent.md 규칙) """
    errors = []
    if not isinstance(code, str):
        return {"ok": False, "errors": ["invalid_code_type"], "ast": None}
    
    # 규칙: 'for', 'while' 루프 금지
    if "for" in code or "while" in code:
        errors.append("forbidden_loop_keyword")
    
    # 성공 시 Mock AST 반환
    ast = {"type": "Program", "body": code} 
    return {"ok": not errors, "errors": errors, "ast": ast if not errors else None}

def static_rules(ast: dict) -> dict:
    """ (Mock) AST 기반 정적 로직 규칙 검사 (input_eval_agent.md 규칙) """
    if not ast:
        return {"violations": ["parse_failed"]}
    
    violations = []
    code = ast.get("body", "")
    
    # 규칙: 'spinning'은 'period == -1'과만 사용
    if "spinning" in code and "period == -1" not in code:
        violations.append("spinning_misuse")
    
    # 규칙: cron 당 period는 1개 (단순화된 검사)
    if code.count("cron") == 1 and code.count("period") > 1:
        violations.append("multiple_periods_per_cron")
        
    return {"ok": not violations, "violations": violations}
```

### eval_tools/similarity_checker.py
``` python
"""
(Mock) JOI Lang 코드 정규화 및 유사도 계산기
"""
import re

def normalize(code: str) -> str:
    """ (Mock) 공백, 주석 제거 """
    if not isinstance(code, str): return ""
    code = re.sub(r'#.*', '', code) # 주석 제거
    code = re.sub(r'\s+', ' ', code).strip() # 다중 공백 -> 단일 공백
    return code

def calculate_jaccard(norm_a: str, norm_b: str) -> float:
    """ (Mock) Jaccard 유사도 계산 """
    set_a = set(norm_a.split())
    set_b = set(norm_b.split())
    if not set_a and not set_b: return 1.0
    if not set_a or not set_b: return 0.0
    
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return intersection / union
```

### eval_tools/policy_checker.py
``` python
"""
(Mock) JOI Lang 함수 호출 및 정책 검증기
"""

def check_function_calls(ast: dict, policy_hints: dict) -> dict:
    """ (Mock) 금지된 함수 호출 및 환각 검사 """
    if not ast:
        return {"issues": ["parse_failed"]}
        
    issues = []
    forbidden = policy_hints.get("forbidden_actions", []) # 예: ["(#Heater).turn_on"]
    code = ast.get("body", "")
    
    for action in forbidden:
        if action in code:
            issues.append(f"forbidden_action: {action}")
            
    # 규칙: 환각(Hallucinated) 서비스 금지
    if "delete_file" in code or "send_email" in code:
        issues.append("hallucinated_service")
            
    return {"issues": issues}
```

---

## 3. cloud_judge/judge.py (LLM-as-a-Judge 래퍼)
이 파일은 main_evaluator.py가 사용할 LangSmith 내장 평가자를 설정하고 반환합니다. config.py에 정의된 기준(Criteria) 프롬프트를 사용합니다.

``` python

"""
LangSmith의 내장 LLM-as-a-Judge (`Criteria`)를 설정하고 반환합니다.
`main_evaluator.py`가 이 모듈을 임포트하여 평가자 세트에 추가합니다.
"""
from langchain.evaluation import EvaluatorType
from langsmith.evaluation import RunEvaluator

import config # config.py에서 기준(Criteria) 프롬프트를 가져옴

def get_semantic_intent_evaluator() -> dict:
    """
    config.py에 정의된 SEMANTIC_JUDGE_CRITERIA를 사용하여
    LangSmith의 내장 LLM-as-a-Judge 평가자를 반환합니다.
    
    반환값은 `client.run_on_dataset`의 `evaluation` 매개변수에
    바로 전달될 수 있는 딕셔너리 형태입니다.
    """
    
    # config.SEMANTIC_JUDGE_CRITERIA는 이미 
    # {"semantic_intent": Criteria(...)} 형태의 딕셔너리입니다.
    # LangSmith는 이 Criteria 객체를 보고 내장 LLM-as-a-Judge를
    # 자동으로 호출하여 'semantic_intent' 키로 점수를 매깁니다.
    
    print("✅ LangSmith 내장 LLM-as-a-Judge (Criteria) 로드됨")
    return config.SEMANTIC_JUDGE_CRITERIA
```

---

## 4. main_evaluator.py (핵심 파이프라인)
이 파일이 LangSmith 네이티브 평가의 핵심입니다. run_on_dataset을 사용하여 전체 파이프라인을 오케스트레이션합니다.
### 
``` python
"""
JOI Lang 하이브리드 평가 파이프라인 (LangSmith 네이티브)

1. CSV 데이터 -> LangSmith Dataset으로 업로드 (멱등성 보장)
2. Custom Evaluator (Python 규칙) 정의 (eval_tools 래핑)
3. LangSmith 내장 Evaluator (LLM-as-a-Judge) 로드 (cloud_judge 임포트)
4. `run_on_dataset`으로 평가 실행 및 자동 집계
"""
import config # 모든 설정을 config.py에서 가져옴
import pandas as pd
import json
from tqdm import tqdm

from langsmith import Client
from langsmith.evaluation import EvaluationResult, RunEvaluator
from langsmith.schemas import Example, Run
from typing import Any, Dict, Optional, List

# --- (A) 커스텀 Python 검증기 (Custom Evaluators) 정의 ---
# `eval_tools/`의 Python 함수들을 LangSmith 평가 프레임워크에 맞게 래핑합니다.

from eval_tools import syntax_checker, policy_checker, similarity_checker

class JOIHybridDeterministicEvaluator(RunEvaluator):
    """
    [커스텀 검증기 1] 결정론적 점수 (syntax, logic, policy)
    
    여러 Python 검사를 하나의 Evaluator에서 실행하여 효율성을 높입니다.
    (네트워크 호출이 아닌 로컬 함수들이므로)
    """
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        
        # '모델'이 반환한 코드를 가져옴
        candidate_obj = run.outputs.get("output", {})
        candidate_code = candidate_obj.get("code", "")
        
        if not candidate_code:
            return [
                EvaluationResult(key="syntax_schema", score=0.0, comment="No code output"),
                EvaluationResult(key="logic_rules", score=0.0, comment="No code output"),
                EvaluationResult(key="function_calls", score=0.0, comment="No code output"),
            ]

        # --- 1. 구문/로직 검사 (syntax_checker) ---
        pv = syntax_checker.parse_validate(candidate_code)
        syntax_score = 1.0 if pv["ok"] else max(0.0, 1 - 0.15 * len(pv["errors"]))
        
        sr = syntax_checker.static_rules(pv.get("ast"))
        logic_score = 1.0
        # 'meta_prompt_system.md' 규칙 적용
        if any("loop_keyword" in v for v in sr["violations"]): logic_score -= 0.4
        if any("spinning_misuse" in v for v in sr["violations"]): logic_score -= 0.2
        if any("multiple_periods_per_cron" in v for v in sr["violations"]): logic_score -= 0.5
        
        # --- 2. 함수 호출/정책 검사 (policy_checker) ---
        policy_hints = example.inputs.get("policy_hints", {})
        pc = policy_checker.check_function_calls(pv.get("ast"), policy_hints)
        # 'meta_prompt_system.md' 규칙 적용 (이슈당 감점)
        func_score = max(0.0, 1.0 - 0.25 * len(pc["issues"]))
        if any("hallucinated_service" in i for i in pc["issues"]): func_score -= 0.6
        
        # LangSmith에 3개의 개별 점수를 리스트로 반환
        return [
            EvaluationResult(key="syntax_schema", score=syntax_score, comment=str(pv["errors"] or "OK")),
            EvaluationResult(key="logic_rules", score=max(0.0, logic_score), comment=str(sr["violations"] or "OK")),
            EvaluationResult(key="function_calls", score=max(0.0, func_score), comment=str(pc["issues"] or "OK"))
        ]

class JOISimilarityEvaluator(RunEvaluator):
    """
    [커스텀 검증기 2] 정답(GT)과의 Jaccard 유사도
    """
    def evaluate_run(
        self, run: Run, example: Optional[Example] = None
    ) -> EvaluationResult:
        candidate_obj = run.outputs.get("output", {})
        candidate_code = candidate_obj.get("code", "")
        norm_candidate = similarity_checker.normalize(candidate_code)
        
        # 데이터셋(Example)에서 정답(GT) 목록을 가져옴
        gts = example.outputs.get("ground_truths", [])
        if not gts:
            return EvaluationResult(key="max_jaccard_similarity", score=0.0, comment="No GTs")

        max_sim = 0.0
        for gt_obj in gts:
            gt_code = gt_obj.get("code", "")
            norm_gt = similarity_checker.normalize(gt_code)
            jaccard = similarity_checker.calculate_jaccard(norm_candidate, norm_gt)
            max_sim = max(max_sim, jaccard)
            
        return EvaluationResult(key="max_jaccard_similarity", score=max_sim)


# --- (B) 평가 대상 모델(Chain) 정의 ---

def load_candidate_from_dataset(run: Run, example: Example) -> Dict[str, Any]:
    """
    '모델' 역할을 하는 함수.
    실제 LLM을 호출하는 대신, 데이터셋(Example)에 이미 생성되어 있는
    'candidate' 코드를 가져와 'output'으로 반환합니다.
    
    (LangSmith는 `run_on_dataset` 실행 시 이 함수를 호출합니다.)
    """
    # example.inputs['candidate']에 후보 코드가 저장되어 있음
    candidate_output = example.inputs.get("candidate", {})
    return {"output": candidate_output}


# --- (C) 메인 실행 함수 ---

def setup_langsmith_dataset(
    client: Client, 
    csv_path: str, 
    dataset_name: str
) -> str:
    """
    CSV 파일을 읽어 LangSmith Dataset으로 생성(또는 업데이트)합니다.
    멱등성을 보장하기 위해 기존 데이터셋을 확인하고 삭제합니다.
    """
    print(f"데이터셋 로드 중: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"오류: 데이터 파일 '{csv_path}'를 찾을 수 없습니다.")
        return ""
    
    # 1. 기존 데이터셋 삭제 (멱등성 보장)
    if client.has_dataset(dataset_name=dataset_name):
        print(f"경고: 기존 데이터셋 '{dataset_name}'을(를) 삭제합니다.")
        client.delete_dataset(dataset_name=dataset_name)

    print(f"새 데이터셋 '{dataset_name}' 생성 중...")
    dataset = client.create_dataset(dataset_name=dataset_name, description="JOI Lang Evaluation Dataset (Hybrid Rubric)")

    # 2. CSV 행을 LangSmith Example (입/출력)으로 변환
    print(f"데이터셋에 {len(df)}개 예제 업로드 중...")
    examples = []
    for _, row in tqdm(df.iterrows(), total=df.shape[0], desc="데이터 변환 중"):
        try:
            # 정답(GT) 파싱
            gts = []
            if pd.notna(row.get('gt1')): gts.append(json.loads(row['gt1']))
            if pd.notna(row.get('gt2')): gts.append(json.loads(row['gt2']))
            if pd.notna(row.get('gt3')): gts.append(json.loads(row['gt3']))
            
            # (중요) 'candidate' 코드를 로드
            # config.py에 정의된 열 이름을 사용
            if pd.isna(row.get(config.CANDIDATE_CODE_COLUMN)):
                continue # 평가할 코드가 없으면 스킵
            candidate_code_obj = json.loads(row[config.CANDIDATE_CODE_COLUMN])
            
            # 'command' 로드
            command = row[config.COMMAND_COLUMN]

            examples.append(
                Example(
                    inputs={
                        "command": command,
                        "candidate": candidate_code_obj, # 평가 대상 (모델의 입력)
                        "policy_hints": {"forbidden_actions": []} # 정책
                    },
                    outputs={
                        "ground_truths": gts # 유사도 및 의미론 평가용 정답
                    }
                )
            )
        except Exception as e:
            print(f"데이터 파싱 오류 (index {row.get('index')}, 무시): {e}")

    # 3. 데이터셋에 예제 일괄 추가
    client.create_examples(
        inputs=[e.inputs for e in examples], 
        outputs=[e.outputs for e in examples], 
        dataset_id=dataset.id
    )
    print(f"✅ 데이터셋 '{dataset_name}'에 {len(examples)}개 예제 업로드 완료.")
    return dataset_name

def main():
    client = Client()
    
    # 1. 데이터셋 준비 (CSV -> LangSmith Dataset)
    dataset_name = setup_langsmith_dataset(
        client=client,
        csv_path=config.DATA_FILE_PATH,
        dataset_name=config.LANGSMITH_DATASET_NAME
    )
    if not dataset_name:
        return

    # 2. 하이브리드 평가자 세트 구성
    
    # (A) 커스텀 Python 검증기 (결정론적)
    deterministic_evaluators = JOIHybridDeterministicEvaluator()
    similarity_evaluator = JOISimilarityEvaluator()
    
    # (B) LangSmith 내장 LLM-as-a-Judge (의미론적)
    # cloud_judge/judge.py에서 설정된 평가자를 가져옴
    from cloud_judge import judge
    semantic_evaluator = judge.get_semantic_intent_evaluator()
    
    # 평가자 세트 통합
    hybrid_evaluator_set = {
        "deterministic_checks": deterministic_evaluators,
        "similarity_checks": similarity_evaluator,
        **semantic_evaluator # {"semantic_intent": Criteria(...)}
    }
    
    print("\n--- 🚀 LangSmith 평가 실행 ---")
    print(f"  프로젝트: {config.LANGSMITH_PROJECT_NAME}")
    print(f"  데이터셋: {dataset_name}")
    print(f"  평가자 키: {list(hybrid_evaluator_set.keys())}")
    
    # 3. 평가 실행!
    # LangSmith가 'dataset_name'의 모든 예제를 순회하며,
    # 'load_candidate_from_dataset' 모델을 실행하고,
    # 'hybrid_evaluator_set'의 모든 검증기로 채점합니다.
    evaluation_run = client.run_on_dataset(
        dataset_name=dataset_name,
        llm_or_chain_factory=load_candidate_from_dataset,
        evaluation=hybrid_evaluator_set,
        project_name=config.LANGSMITH_PROJECT_NAME,
        concurrency_level=5, # 5개 병렬 실행으로 속도 향상
    )
    
    print("\n--- ✅ 평가 완료 ---")
    print(f"LangSmith 대시보드에서 '{config.LANGSMITH_PROJECT_NAME}' 프로젝트를 확인하세요.")
    
    # (선택적) 결과 요약 출력
    results_df = client.get_run_results_dataframe(project_name=config.LANGSMITH_PROJECT_NAME)
    if not results_df.empty:
        print("\n--- 📊 평가 점수 요약 (평균) ---")
        avg_scores = results_df.filter(regex=r"feedback\.(syntax_schema|logic_rules|function_calls|semantic_intent|max_jaccard_similarity)").mean()
        print(avg_scores)
    
if __name__ == "__main__":
    main()
```

