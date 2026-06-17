Markdown# 🚀 JOI Lang 평가 프레임워크 (JOI Lang Evaluation)

이 프로젝트는 자연어(NL) 명령을 IoT 제어 DSL인 **JoI-Lang** 코드로 변환하는 모델의 성능을 평가하기 위한 하이브리드 평가 파이프라인입니다.

논문의 공신력을 확보하기 위해, 이 프레임워크는 두 가지 핵심 평가 축을 결합합니다:

1.  **결정론적 검증 (Deterministic Analysis):** `eval_tools`에 포함된 파서(`ply` 기반)와 정적 분석기, 그리고 `z3-solver`를 사용한 논리적 동등성 검사를 통해 코드의 구문, 규칙, 의미론적 구조를 로컬에서 정밀하게 채점합니다.
2.  **클라우드 의미론적 검증 (Cloud Semantic Judging):** **LangSmith**의 `run_on_dataset` 기능과 내장 `Criteria` 평가자(LLM-as-a-Judge)를 활용하여, 재현 가능하고 공신력 있는 방식으로 생성된 코드의 의도(Intent)를 평가합니다.

---

## 📊 사용법 (실행 모드)

이 스크립트는 두 가지 모드로 실행할 수 있습니다.

### 1. (테스트) 결정론적 로컬 테스트 모드 ('det')

이 모드는 LangSmith나 클라우드 LLM-as-a-Judge를 호출하지 않습니다. 단일 `index_no`를 지정하면, 해당 명령어(command)로 **(Mock) GPT 모델을 1회 실행**하고, 그 결과를 **오직 `eval_tools` (Python/Z3)만으로 평가**합니다.

로컬 파서(`parser.py`)나 Z3 비교기(`similarity_checker.py`)의 성능을 빠르게 디버깅하는 데 유용합니다.

**실행 명령어:**
```bash
python main_evaluator.py det {index_no}
예시 (index 66번 테스트):
python main_evaluator.py det 66
```

**실행 절차:**
- det 66 명령을 감지합니다.
- data/output_merged_250710.csv에서 index 열이 '66'인 행을 찾습니다.
- 해당 행의 'command'를 가져옵니다.
- (Mock) generate_joi_code_mock 함수를 호출하여 (가상의) candidate_json을 생성합니다.
  - (참고: main_evaluator.py의 이 함수를 실제 gpt_mg.run.generate_joi_code 임포트로 교체하면 실제 GPT 모델을 호출할 수 있습니다.)
- run_deterministic_evaluation 함수가 실행됩니다.
- 후보(Candidate) JSON과 해당 행의 모든 GT JSON (gt1, gt2...)을 eval_tools로 전달합니다.
- semantic_intent 점수는 similarity_checker.py의 Z3/AST 비교 점수(code 유사도)로 대체됩니다.

**결과:**
- 최종 결정론적 점수가 터미널에 출력됩니다.
- 평가 결과의 상세 내용이 result_{MODEL_NAME}.csv (예: result_gpt-4o_test_model.csv) 파일에 한 줄 추가됩니다.

### 2. (기본) LangSmith 하이브리드 평가 모드

논문의 최종 결과를 재현 가능하게 생성하기 위한 메인 모드입니다. data/의 전체 CSV 파일을 LangSmith에 업로드하고, **(A)결정론적 eval_tools**와 (B)LangSmith 내장 LLM-as-a-Judge를 모두 실행하여 하이브리드 점수를 매깁니다.

**실행 명령어:**
```bash
python main_evaluator.py
```

**실행 절차:**
- config.DATA_FILE_PATH에서 CSV 파일을 로드합니다.
- setup_langsmith_dataset 함수가 gt로 시작하는 모든 열(gt1, gt2, ...)을 동적으로 찾아 ground_truths 리스트로 묶어 LangSmith에 새 데이터셋을 생성합니다.
- client.run_on_dataset이 실행됩니다.
- LangSmith는 데이터셋의 각 항목에 대해 다음 평가자(Evaluator)들을 병렬로 실행합니다:
  - JOIHybridDeterministicEvaluator: eval_tools를 호출하여 syntax_schema, logic_rules, function_calls 점수를 계산합니다.
  - JOISimilarityEvaluator: eval_tools의 비교기를 호출하여 max_jaccard_similarity (가장 유사한 GT 기준) 점수를 계산합니다.
  - semantic_intent_judge: cloud_judge/judge.py에 설정된 Criteria를 기반으로, LangSmith의 내장 LLM-as-a-Judge가 semantic_intent 점수를 계산합니다.

**결과:**
- 모든 점수는 config.LANGSMITH_PROJECT_NAME으로 지정된 LangSmith 프로젝트 대시보드에서 실시간으로 집계 및 확인할 수 있습니다.

## 📈 'det' 모드 예상 결과 (result_{model_name}.csv)

`python main_evaluator.py det {index_no}` 실행 시, 다음과 같은 CSV 파일이 생성되거나 업데이트됩니다.

```
index,command,generated_candidate_json,ground_truth_json_list,syntax_schema,logic_rules,function_calls,semantic_intent_z3,overall_deterministic,equivalent_z3,syntax_errors,rule_violations,function_call_issues,z3_diff
66,"10초마다 관개기를...",{"name": "Scenario1", "period": 10000, "code": "lux = (#LightSensor)...if (lux > 500)..."},"[""{"name": "Scenario1", "period": 10000, "code": "...if (lux >= 500.0)..."}""]",1.0,1.0,1.0,0.833,0.958,False,[],[],[],""- if (lux >= 500.0)
+ if (lux > 500)"
16,"10을 3으로 나눈...",{"name": "Scenario1", "period": -1, "code": "(#Calculator).calculator_mod(10, 3.0)"},"[""{"name": "Scenario1", "period": -1, "code": "(#Calculator).calculator_mod(10,3)"}""]",1.0,1.0,1.0,0.667,0.908,False,[],[],[],""- ...mod(10,3)
+ ...mod(10, 3.0)"
99,"(파싱 실패)...",{"code": "INVALID JSON: if (temp > { 25 )"},"[""{"name": "Scenario1", ...}"]",0.0,0.0,0.0,0.0,0.0,False,"[""parser_exception...""]",""Parse failed""
```

> 참고: `semantic_intent_z3` 점수는 similarity_checker.py의 AST/구조 비교 점수이며, `equivalent_z3`는 Z3 솔버를 통한 논리적 동등성 비교 결과를 의미합니다.

---

## 🛠️ 설치 및 설정

**필수 라이브러리 설치:**
이 프로젝트는 pandas, ply (파싱), z3-solver (논리 비교), langsmith (클라우드 평가)가 필요합니다.
```bash
pip install pandas ply z3-solver langsmith langchain langchain-openai
```

**데이터 준비:**
- `output_merged_250710.csv`와 같은 평가용 CSV 파일을 `data/` 폴더 내에 위치시킵니다.

**환경 설정 (`config.py`):**
- `config.py` 파일을 열어 본인의 환경에 맞게 주요 변수들을 설정합니다.
- API Keys (필수): `LANGSMITH_API_KEY`와 `OPENAI_API_KEY`는 `os.environ.get(...)`을 통해 환경 변수에서 읽어옵니다. 스크립트 실행 전에 이 환경 변수들을 설정해야 합니다.
- `LANGSMITH_PROJECT_NAME`: LangSmith UI에 표시될 프로젝트 이름입니다.
- `DATA_FILE_PATH`: `data/` 폴더에 있는 CSV 파일의 정확한 경로입니다.
- `MODEL_NAME`: 'det' 모드에서 사용할 모델의 이름입니다. (결과 파일명에 사용됨)
- `CANDIDATE_CODE_COLUMN`: **'LangSmith 모드'**에서 평가할 후보 코드가 포함된 CSV 열 이름입니다. (예: `"gt1"` 또는 `"output_gpt4o"`)
- `COMMAND_COLUMN`: 명령어(command)가 포함된 열 이름입니다.

---

**종합 점수 컬럼**:
**overall_final**가 “종합 점수"

계산식: 실행된 모드에 한해, config.WEIGHTS에 정의된 가중치로 정규화 가중합.

의미: DET(문법/규칙/함수호출) + Semantic(의도 일치) 점수를 한 번에 본 최종 스코어.

관련 컬럼 역할
overall_deterministic: DET 전용 종합(= syntax_schema, logic_rules, function_calls, 그리고 사용했다면 semantic_intent_z3를 config.WEIGHTS로 합산).
syntax_schema: 파싱·스키마 통과 여부 점수.
logic_rules: 정적 규칙 위반 감점 반영 점수.
function_calls: 허상 호출/정책 위반 감점 반영 점수.

Semantic 계열 (의도 일치 대표값 1개만 채택)
우선순위: semantic_intent_ls > semantic_intent_gpt > semantic_intent_z3
선택된 하나가 Semantic으로 간주되어 overall_final에 반영.

ls_*: LangSmith 다중 기준(예: ls_semantic_intent, ls_time_period, ls_device_service, ls_conditions) 세부 점수.

---

## ⚙️ 프로젝트 구조

```
/joi_lang_evaluation/
├── README.md               # (✅ 0. 이 파일)
├── main_evaluator.py       # (✅ 1. 메인 파이프라인 실행기 - 듀얼 모드 지원)
├── config.py               # (✅ 2. 설정 파일: API 키, 경로, 모델명)
│
├── eval_tools/             # (✅ 3. 결정론적 검증 도구 (Python))
│   ├── __init__.py
│   ├── parser.py           # (PLY 기반 JoI-Lang 파서 - soplang_parser_full.py 기반)
│   ├── syntax_checker.py   # (문법/정적 규칙 검사)
│   ├── similarity_checker.py # (Z3 기반 논리/구조 비교 - compare_soplang_ir.py 기반)
│   └── policy_checker.py   # (함수 호출 정책 검사)
│
├── cloud_judge/            # (✅ 4. LangSmith Judge 래퍼)
│   ├── __init__.py
│   └── judge.py            # (LangSmith `Criteria` 설정)
│
└── data/                   # (✅ 5. 평가 데이터)
    └── output_merged_250710.csv   # (예시 데이터 파일)
```
