# JOILang GA Feedback Notebook v2 Final Guide

## 1. 이번 수정의 핵심 결론

기존 notebook에서 확인된 문제는 다음과 같다.

1. A100 모델 경로가 잘못 잡힐 수 있었다.
   - 잘못된 경로: `/root/llm/JOILang-Server/local_models/qwen25_coder_14b`
   - 올바른 경로: `/root/llm/local_models/qwen25_coder_14b`

2. row smoke 결과가 `worker_crash`이면 prompt feedback 실험이 아니다.
   - `candidates=[""]`, `generation_error_type=worker_crash`, `generation_prompt_tokens_total=0`이면 LLM 생성 전 단계에서 실패한 것이다.

3. 수동 feedback은 반드시 baseline evidence를 본 뒤 넣어야 한다.
   - 올바른 순서:
     baseline test
     → feedback / prompt mutation evidence 확인
     → actual prompt 확인
     → manual feedback 설계
     → patched genome/source_file로 prompt에 강제 반영
     → before/after diff
     → same row rerun
     → evaluation 비교
     → actual prompt 재확인

4. `manual_feedback.md`만 쓰는 방식은 `run_ga_search.py` 실험에서 prompt 반영을 보장하지 않는다.
   - v2 notebook은 `best_genome.json`을 직접 patch한다.
   - `block_params["02"]["micro_rules"]`에 rule을 넣고,
   - `blocks/generated/...` source_file을 만들어 최종 prompt에 강제로 보이게 한다.

5. `run_eval_pipeline_check.sh full`은 cloudless DET only가 아니다.
   - local strict DET
   - cloud semantic judge
   - strict/cloud merge
   - `advisor_rich_feedback.json` schema check
   를 수행한다.

6. cloud advisor는 transport와 effectiveness를 분리해서 봐야 한다.
   - transport: API 호출, response file, prompt file 생성
   - effectiveness: parsed proposal, accepted proposal, advisor child, advisor-backed diff

## 2. Notebook 실행 순서

### 01_cloudless_det_feedback_ga_search_v2_final.ipynb

목적:
- Strict DET / cloudless feedback만으로 prompt GA가 좋아지는지 확인한다.

실행 순서:
1. Cell 0 setup
2. Cell 1 worker preflight
3. Cell 2 baseline row 1 test
4. Cell 3 feedback/mutation evidence
5. Cell 4 actual prompt
6. Cell 5 manual feedback design
7. Cell 6 patched genome 생성
8. Cell 7 before/after diff
9. Cell 8 same row rerun
10. Cell 9 evaluation comparison
11. Cell 10 patched prompt 확인
12. Cell 11 category sweep
13. Cell 12 full 280 × 10 generation
14. Cell 13 final plots

### 02_cloud_only_feedback_ga_search_v2_final.ipynb

목적:
- cloud advisor / cloud semantic judge 중심의 mutation 효과를 본다.
- 현재 GA fitness 자체는 Strict DET 기반이므로, cloud-only는 advisor transport/effectiveness 분석으로 분리한다.

핵심 확인:
- `advisor_mutation_summary.csv`
- `cloud_advisor_prompt_generation_*.md`
- `ga_block_diffs.jsonl`
- `advisor_proposals_accepted_applied`
- `advisor_children_scheduled`

### 03_merged_feedback_ga_search_v2_final.ipynb

목적:
- strict DET + cloud judge merge feedback을 생성하고,
- `advisor_rich_feedback.json`을 evidence로 보존한 뒤,
- GA/advisor 결과와 함께 분석한다.

중요:
- `run_eval_pipeline_check.sh full`은 cloudless only가 아니다.
- full eval pipeline은 cloud judge까지 포함한다.

## 3. 서버별 기본 preset

A100:
```python
SERVER_PRESET = "a100"
# repo: /root/llm/JOILang-Server
# model: /root/llm/local_models/qwen25_coder_14b
```

A6000:
```python
SERVER_PRESET = "a6000"
# repo: /home/mgjeong/Desktop/llm/JOILang-Server
# model: /home/mgjeong/Desktop/llm/local_models/qwen25_coder_14b
# default 4bit = true
```

## 4. 정상 실행 판정

row smoke에서 다음이면 정상이다.

```text
candidates != [""]
generation_error_type가 worker_crash가 아님
generation_prompt_tokens_total > 0
generation_completion_tokens_total > 0
```

다음이면 prompt 실험이 아니라 환경 오류다.

```text
worker_crash
Repo id must be in the form ...
generation_prompt_tokens_total = 0
candidates = [""]
```

## 5. Prompt feedback 반영 증거

다음 중 최소 2개 이상을 확인한다.

1. `best_genome.json`
   - `block_params["02"]["micro_rules"]`
   - `block_params["02"]["source_file"]`

2. `ga_block_diffs.jsonl`
   - `feedback_driven`
   - `mutation_type`
   - `failure_type_source`
   - `llm_advised`
   - `advisor_proposal_id`

3. `blocks/generated/*.txt`
   - `NOTEBOOK MANUAL FOCUS RULES`
   - 수동 rule 본문

4. `prompt_log_paths` 내부 JSON
   - `request.user` 안에 수동 rule이 실제로 포함되어야 한다.

## 6. 추천 실험 단계

1. row 1개 baseline
2. row 1개 manual patch rerun
3. category 1 하나만 sweep
4. category 1~8 각각 sweep
5. full 280 × 10 generation
6. cloud advisor notebook
7. merged feedback notebook

## 7. 산출물

- `ga_summary.json`
- `best_genome.json`
- `ga_block_diffs.jsonl`
- `ga_generation_progress.csv`
- `pareto_rows.csv`
- `advisor_mutation_summary.csv`
- `cloud_advisor_prompt_generation_*.md`
- `advisor_rich_feedback.json`
