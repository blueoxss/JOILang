너는 LLM AI agent 정확도 분석 하기 위한 코드 전문가야. 아래와 같이 결정론적 결과가 제대로 나온거 같아. 
이제, 아래의 judge.py인 langsmith도 활용해서 종합적인 정답 스코어를 매기는 코드를 완성하고싶어.
 main_evaluator.py를 포함해서 수정하거나 더 추가할 코드가 있으면 알려줘. 그리고, 종합적으로 분석한 결과는 최종 점수도 당연히 선택한 row index에 저장해야겠지만, 결정론적 점수 score 세분화한것과 langsmith결과 세분화도 저장하도록 해줘. 30번을 선택했으면 30번째 index의 csv로 저장해야겠지?



---

결과 
 python main_evaluator.py det 30 version0_6
⚠️ 경고: 실제 GPT 호출 함수 로드 실패 (No module named 'gpt_mg'). Mock 함수를 사용합니다.
--- 🚀 Running Deterministic Test for Row Index: 30 using Model: gpt_mg.version0_6 ---
   (Results will be saved to: result_det_gpt_mg_version0_6.csv)
[1/4] 명령어 로드 (Original Index: 26): 관개 장치의 급수를 시작해줘.
   Calling get_script_gpt with version_path='version0_6'
[Mock] 'gpt_mg.version0_6'로 코드 생성 중...
[2/4] 후보 JSON 생성 (0.123초):
{"name": "Scenario_Mock", "cron": "* * * * *", "period": 0, "code": "if ((#MockSensor).value > 10) {\n  (#MockLight).on()\n}"}
Warning: GT column 'gt3' JSON 파싱 실패, 건너<0xEB><0x9B><0x84>니다.
[3/4] 2개의 유효한 Ground Truth 로드 완료.
WARNING: /home/mgjeong/Desktop/llm/ModelMagementApp/joi_lang_evaluation/eval_tools/parser.py:285: Function p_error redefined. Previously defined on line 276
WARNING: Token 'ANY' defined, but not used
WARNING: Token 'DELAY' defined, but not used
WARNING: Token 'HASH' defined, but not used
WARNING: There are 3 unused tokens
[4/4] 결정론적 평가 완료.

 result_det_gpt_mg_version0_6.csv 파일이 생성되었습니다.
최종 결정론적 점수 
{
  "syntax_schema": 1.0,
  "logic_rules": 1.0,
  "function_calls": 1.0,
  "semantic_intent_z3": 0.0,
  "overall_deterministic": 0.8
}

Z3 논리 동등성 (모든 GT와 비교): False


--- 수정할 코드


# /joi_lang_evaluation/cloud_judge/judge.py
"""
LangSmith의 내장 LLM-as-a-Judge (`Criteria`)를 설정하고 반환합니다.
(이 파일은 'det' 모드에서 import되지 않습니다.)
"""
# --- LangChain Import ---
try:
    # LangSmith 모드에서만 필요한 import
    from langchain.evaluation import Criteria 
except ImportError:
    # 'det' 모드 등 LangChain이 설치되지 않은 환경에서는 무시
    Criteria = None 
# --- End LangChain Import ---

import config # config.py에서 기준 프롬프트를 가져옴

def get_semantic_intent_evaluator() -> dict:
    """
    config.py에 정의된 SEMANTIC_JUDGE_CRITERIA_PROMPT를 사용하여
    LangSmith의 내장 LLM-as-a-Judge 평가자 객체를 생성하고 반환합니다.
    """
    
    if Criteria is None:
        print("⚠️ 경고: 'langchain' 모듈을 찾을 수 없습니다. LangSmith 모드는 작동하지 않습니다.")
        # 빈 딕셔너리를 반환하여 LangSmith 모드 실행 시 에러 방지
        return {} 
        
    print("✅ LangSmith 내장 LLM-as-a-Judge (Criteria) 로드됨")
    
    # 여기서 Criteria 객체를 동적으로 생성
    return {
        "semantic_intent": Criteria(config.SEMANTIC_JUDGE_CRITERIA_PROMPT)
    }


--- 추가로,

그냥 아래를 추가해서 langsmith 결과만 나오는 걸 코드를 만들어줘. 그리고, python main_evaluator.py det  lang {row_index} [model_version_path] 하면 단일행에 대해서 로컬 결정론적 평가 + 로컬 LangSmith Judge 평가 결과를 저장하고, python main_evaluator.py det  gpt {row_index} [model_version_path] 하면 단일행에 대해 로컬 결정론적 평가 +gpt 이고, python main_evaluator.py hybrid {row_index} [model_version_path] 는 모든 단일 행에 대해 GPT 호출 + 로컬 결정론적 평가 + 로컬 LangSmith Judge 평가가 맞아.


python main_evaluator.py는 전체 데이터셋 대상  GPT 호출 + 로컬 결정론적 평가 + 로컬 LangSmith Judge 평가 가 맞고, python main_evaluator.py lang {row_index} [model_version_path]


스코어 매긴 결과는 result_lang_{model_name}.csv에 추가가 아니고, result_{model_name}.csv 파일에 새로운 column에 추가해서 작성하면되는거야. langsmith의 세부 결과들을 포함해서, 두 개를 종합한 스코어에 대한 컬럼도 추가해.