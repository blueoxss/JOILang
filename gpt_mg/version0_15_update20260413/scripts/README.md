# Scripts Guide

가독성이 더 좋은 시각화 문서는 아래에서 바로 볼 수 있습니다.

- [README.html](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/README.html)
- [README.pdf](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/README.pdf)
- 재생성 스크립트: [render_scripts_guide.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/render_scripts_guide.py)

`version0_15_update20260413/scripts/`는 이 워크스페이스의 실험 실행 진입점, 후처리 리포트 생성기, 디버깅 도구가 같이 모여 있는 폴더입니다.

이 문서는 아래 목적에 맞춰 씁니다.

- 어떤 스크립트를 직접 실행해야 하는지
- 어떤 스크립트는 내부용인지
- benchmark가 끝난 뒤 어떤 결과가 자동으로 생성되는지
- `DET`가 무엇을 보고 점수를 주는지
- `failure_reasons`를 어떻게 읽어야 하는지

중요:

- 가장 먼저 기억할 파일은 `run_benchmark.py` 하나면 됩니다.
- 나머지는 `비교`, `리포트`, `DET audit`, `figure export` 용도입니다.
- 긴 기존 파일명은 호환용으로 유지되고 있고, 새 짧은 파일명이 권장 entrypoint입니다.

---

## 1. 가장 중요한 진입점

### 권장 main entrypoint

- [run_benchmark.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py)

이 스크립트가 현재 benchmark의 메인 실행기입니다.

역할:

- dataset row 선택
- 모델 실행
- candidate generation
- rerank / DET 평가
- `suite_summary.csv`, `row_comparison.csv` 등 주요 결과 생성
- 옵션에 따라 자동 후처리 수행
  - row report export
  - benchmark A/B compare
  - DET audit
  - paper figures

### 호환용 legacy entrypoint

- [run_model_suite_benchmark.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py)

기능은 `run_benchmark.py`와 같습니다. 기존 명령을 깨지 않기 위해 남겨둔 alias에 가깝습니다.

---

## 2. 스크립트 분류

### A. 직접 실행하는 상위 스크립트

- [run_benchmark.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py)
  - 메인 benchmark 실행기
- [compare_benchmarks.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/compare_benchmarks.py)
  - 두 결과 디렉터리를 비교
- [export_row_report.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/export_row_report.py)
  - `GT JOICode` vs `Generated JOICode` 좌우 비교 HTML/PDF 리포트 생성
- [audit_det.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/audit_det.py)
  - legacy vs strict DET 점수 차이 분석
- [export_paper_figures.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/export_paper_figures.py)
  - scatter/bar/category figure 생성
- [export_paper_study.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/export_paper_study.py)
  - baseline vs retrieval 전체 실험 결과를 논문용 표/그래프/HTML 보고서로 집계
- [run_paper_context_study.sh](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_paper_context_study.sh)
  - qwen7/qwen14 baseline/retrieval full study를 한 번에 돌리고 `paper/` 결과까지 생성하는 재현용 스크립트
- [prepare_local_models.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/prepare_local_models.py)
  - local model cache / readiness 준비
- [inspect_service_context.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/inspect_service_context.py)
  - schema fallback vs retrieval fallback prompt context 길이 검사

### B. 상위 스크립트가 내부적으로 사용하는 저수준 스크립트

- [run_generate.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_generate.py)
  - candidate generation
- [run_rerank.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_rerank.py)
  - DET rerank / repair
- [run_ga_search.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_ga_search.py)
  - GA prompt search
- [run_category_sweep.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_category_sweep.py)
  - category sweep
- [run_admin_feedback_update.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_admin_feedback_update.py)
  - admin feedback 업데이트 파이프라인

권장:

- 일반 사용자는 `run_generate.py`, `run_rerank.py`를 직접 치기보다 `run_benchmark.py`를 먼저 쓰는 편이 안전합니다.

---

## 3. 가장 자주 쓰는 실행 순서

### 3-1. 환경 준비

```bash
cd /home/mgjeong/Desktop/llm/JOILang-Server

export JOI_V15_WORKER_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
export JOI_V15_LOCAL_DEVICE=cuda:0
```

### 3-2. 모델 준비 상태 확인

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --preflight-only \
  --print-worker-info
```

### 3-3. 가장 기본적인 단일 모델 smoke test

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --det-profile strict \
  --print-mode summary \
  --strict-availability
```

이 경우 기본적으로 다음이 자동으로 붙습니다.

- benchmark result directory 생성
- single-model row report HTML/PDF 생성

### 3-4. 단일 모델 + row report 자동 생성 + DET audit

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --det-profile strict \
  --analyze-det \
  --print-mode summary \
  --strict-availability
```

### 3-5. 두 실험을 자동 비교하고 싶을 때

예: baseline run이 이미 있고, retrieval premapping run을 새로 돌리면서 자동 비교까지 하고 싶을 때

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --enable-retrieval-premapping \
  --retrieval-topk 10 \
  --retrieval-device cpu \
  --compare-to /abs/path/to/older/results_dir \
  --print-mode summary \
  --strict-availability
```

### 3-6. multi-model run인데 row report도 같이 만들고 싶을 때

기본적으로 auto row report는 single-model run에만 붙습니다.

multi-model run에서 보고 싶으면:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --category 1 \
  --category 2 \
  --limit-per-category 10 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --export-row-report \
  --print-mode summary \
  --strict-availability
```

### 3-6a. `version0_13` 스타일의 하나의 큰 prompt로 돌리고 싶을 때

기본값은 현재 v15의 `blocks` 모드입니다.  
하지만 `version0_13`의 `caution_prompt_8.md`, `grammar_ver1.5.10.md`, `service_prompt_10.md`, `tempo_prompt_9.md` 같은 자산을 합쳐 **monolithic prompt**로도 실행할 수 있습니다.

지원 모드:

- `--prompt-render-mode blocks`
  - 기본값
  - genome이 참조하는 block들을 렌더링
- `--prompt-render-mode legacy_v13_monolith`
  - `version0_13` prompt 자산을 합쳐 하나의 큰 prompt 사용

중요:

- 이 옵션은 generation과 repair에 **같이 적용**됩니다.
- service context는 계속 현재 v15 runtime을 따릅니다.
  - `connected_devices`
  - retrieval premapping
  - full schema fallback

local smoke:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --det-profile strict \
  --prompt-render-mode legacy_v13_monolith \
  --prompt-assets-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13 \
  --print-mode compare \
  --strict-availability
```

cloud + retrieval smoke:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_with_cloud_ref \
  --model-key gpt41_mini \
  --llm-mode openai \
  --llm-endpoint "$JOI_V15_OPENAI_ENDPOINT" \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --det-profile strict \
  --prompt-render-mode legacy_v13_monolith \
  --prompt-assets-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13 \
  --enable-retrieval-premapping \
  --retrieval-topk 10 \
  --retrieval-mode hybrid \
  --retrieval-device cpu \
  --print-mode compare \
  --strict-availability
```

특정 모델만 리포트:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --category 1 \
  --category 2 \
  --limit-per-category 10 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --export-row-report \
  --row-report-model-key qwen25_coder_14b \
  --print-mode summary \
  --strict-availability
```

---

## 3-7. full paper study를 한 번에 재현하고 싶을 때

아래 스크립트는 현재 실제로 돌릴 수 있는 `qwen25_coder_7b`, `qwen25_coder_14b`를 기준으로

- baseline full-schema run
- retrieval premapping run
- paper 집계/그래프/HTML 보고서

를 한 번에 만듭니다.

```bash
cd /home/mgjeong/Desktop/llm/JOILang-Server

export JOI_V15_WORKER_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
export JOI_V15_GPU_QWEN7=cuda:0
export JOI_V15_GPU_QWEN14=cuda:1
export JOI_V15_RETRIEVAL_DEVICE=cpu

gpt_mg/version0_15_update20260413/scripts/run_paper_context_study.sh
```

결과는 기본적으로 아래에 생성됩니다.

- `results/paper_study_<timestamp>/benchmarks/`
- `results/paper_study_<timestamp>/paper/`

---

## 3-8. 이미 생성한 여러 benchmark result를 paper용으로 다시 묶고 싶을 때

```bash
python gpt_mg/version0_15_update20260413/scripts/export_paper_study.py \
  --baseline-dir /abs/path/to/baseline_qwen25_coder_7b \
  --baseline-dir /abs/path/to/baseline_qwen25_coder_14b \
  --retrieval-dir /abs/path/to/retrieval_qwen25_coder_7b \
  --retrieval-dir /abs/path/to/retrieval_qwen25_coder_14b \
  --blocked-model 'phi35_mini=blocked|CUDA_OOM_with_current_prompt_length' \
  --blocked-model 'llama31_8b=blocked|incomplete_cache' \
  --blocked-model 'gemma2_9b_it=blocked|incomplete_cache' \
  --out-dir /abs/path/to/paper_output_dir
```

대표 산출물:

- `combined_suite_condition.csv`
- `condition_delta_by_model.csv`
- `condition_delta_by_category.csv`
- `condition_delta_by_row.csv`
- `availability_summary.csv`
- `paper_findings.md`
- `paper_findings.html`
- `figures/*.png`

---

## 4. 자동 후처리 규칙

`run_benchmark.py`는 benchmark가 끝난 뒤 아래 후처리를 조건부로 자동 실행합니다.

### 자동 row report

- single-model run이면 기본적으로 자동 실행
- 끄려면 `--skip-row-report`
- multi-model run에서 켜려면 `--export-row-report`

### 자동 benchmark compare

- `--compare-to /abs/path/to/older/results_dir` 를 주면 실행
- 내부적으로 [compare_benchmarks.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/compare_benchmarks.py) 를 호출하는 것과 같은 결과를 만듭니다.

### 자동 DET audit

- `--analyze-det` 를 주면 실행
- 내부적으로 [audit_det.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/audit_det.py) 를 호출하는 것과 같은 결과를 만듭니다.

### paper figure export

- `--export-paper-artifacts`
- 또는 `--paper-fair-mode`

---

## 5. 결과 디렉터리 구조

benchmark 결과는 보통 아래에 생깁니다.

- `results/model_suite_<timestamp>/`

대표 파일:

- `suite_manifest.json`
- `suite_summary.csv`
- `row_comparison.csv`
- `failure_reason_summary.csv`
- `category_summary.csv`
- `main_model_comparison.csv`
- `tradeoff_summary.csv`
- `paper_metrics_summary.json`

자동 후처리가 붙으면 추가로:

- `side_by_side_report_<model_key>/report.html`
- `side_by_side_report_<model_key>/report.pdf`
- `side_by_side_report_<model_key>/report_summary.json`
- `side_by_side_report_<model_key>/prompt_context_rows.json`
- `det_audit/analysis_summary.json`
- `context_compare_<baseline>__vs__<experiment>/context_comparison_summary.json`

---

## 6. 어떤 파일명을 기억하면 되나

실제로는 아래 4개만 기억해도 대부분 충분합니다.

- `run_benchmark.py`
- `compare_benchmarks.py`
- `export_row_report.py`
- `audit_det.py`

기존 긴 이름은 아래처럼 대응됩니다.

- `run_model_suite_benchmark.py` = `run_benchmark.py`
- `compare_service_context_results.py` = `compare_benchmarks.py`
- `export_joi_code_side_by_side_report.py` = `export_row_report.py`
- `analyze_det_profiles.py` = `audit_det.py`

---

## 7. DET란 무엇인가

DET는 이 워크스페이스에서 candidate JOICode를 정량 평가하는 내부 점수입니다.

중요:

- `DET = 모델이 맞는 코드를 얼마나 잘 썼는지`를 여러 축으로 분해해서 합산한 점수입니다.
- 그냥 string exact match만 보는 것이 아닙니다.
- `legacy`와 `strict` 두 프로파일이 있습니다.

### 7-1. legacy vs strict

#### `legacy`

특징:

- 기존 실험과 호환되는 점수
- 상대적으로 관대한 편
- 빠르게 후보를 정렬하는 용도에 적합

#### `strict`

특징:

- GT service coverage
- receiver coverage
- dataflow
- numeric grounding
- enum grounding

을 더 엄격하게 반영합니다.

즉 `strict`는 다음과 같은 과대평가를 더 잘 잡습니다.

- 값 읽기와 전달이 끊긴 코드
- 그룹 receiver 일부만 처리한 코드
- 숫자/시간/채널 값이 틀린 코드
- enum mode가 틀린 코드

권장:

- historical/GA 비교는 `legacy`
- 실제 품질 검증과 리포트는 `strict`

---

## 8. DET가 보는 주요 세부 지표

리포트나 `row_comparison.csv`에서 보이는 주요 필드는 아래 의미입니다.

### `det_score`

- 최종 DET 점수
- 0~100

### `det_gt_exact`

- GT와 exact match 여부

### `det_gt_similarity`

- GT와의 전체 유사도
- exact가 아니더라도 구조/서비스/스케줄이 비슷하면 어느 정도 점수를 받음

### `det_service_match`

- 생성 코드의 service들이 현재 schema에서 얼마나 잘 resolve되는지

### `det_arg_type_ok`

- 각 service의 인자 타입이 schema expectation과 얼마나 잘 맞는지

### `det_precondition_ok`

- power guard 같은 전제조건이 필요한 경우 그것이 반영됐는지

### `det_semantic_ok`

- command 의미 토큰과 생성된 service/action이 얼마나 맞는지

### `det_min_extraneous`

- 명령에 없는 불필요한 service/action이 섞였는지

### `det_gt_service_coverage`

- GT에 필요한 service를 생성 코드가 모두 포함했는지

### `det_gt_receiver_coverage`

- GT의 receiver scope와 instance coverage를 얼마나 잘 덮었는지

### `det_dataflow_score`

- sensor/value를 읽은 뒤 실제로 downstream 함수에 전달했는지

### `det_numeric_grounding`

- command/GT의 숫자 정보가 코드에 정확히 반영됐는지

### `det_enum_grounding`

- enum 값이 GT와 맞는지

---

## 9. failure_reasons 읽는 법

`failure_reasons`는 왜 감점됐는지를 설명하는 태그입니다.

### 9-1. 형식/파싱 실패

#### `invalid_json`

의미:

- 출력이 JSON으로 파싱되지 않음

대표 상황:

- explanation이 같이 나옴
- braces가 안 맞음
- raw text만 출력함

해석:

- 가장 앞단 실패
- 이 경우 나머지 세부 평가가 거의 의미가 없어집니다

#### `schema_missing_keys`

의미:

- JSON은 맞지만 `name`, `cron`, `period`, `code` 중 필수 키가 누락됨

대표 상황:

- `code` 없이 `script`만 넣음
- `period`를 빼먹음

#### `no_parseable_member_access`

의미:

- `code`는 있지만 `(#Device).Service(...)` 형식으로 parse 가능한 member access가 없음

대표 상황:

- JOILang이 아니라 자연어/의사코드를 반환

### 9-2. 서비스/인자 실패

#### `unknown_service:<member>`

의미:

- 생성 코드 안의 service/member를 schema에 매핑하지 못함

예:

- `unknown_service:set`
- `unknown_service:temperature_sensor`

대표 상황:

- snake_case/camelCase가 심하게 깨짐
- 없는 helper 이름을 invent함

#### `service_match`

의미:

- 전체 호출 중 일부가 schema에 맞는 service로 resolve되지 않음

대표 상황:

- 맞는 서비스와 틀린 서비스가 섞임
- unknown service가 포함됨

#### `arg_type`

의미:

- 서비스는 맞지만 인자 타입이 기대와 다름

대표 상황:

- 숫자여야 하는데 string
- enum이어야 하는데 자유 텍스트
- arg 개수/순서가 틀림

실제 synthetic 예:

- row 3 `wrong_unit_ms_expr`
  - legacy `93.9479`
  - strict `69.9`
  - strict failures: `["arg_type", "gt_mismatch", "numeric_grounding"]`

해석:

- 얼핏 비슷해 보여도 단위/형태가 틀리면 strict가 강하게 깎습니다.

### 9-3. 의미/구조 실패

#### `precondition`

의미:

- 필요한 전제조건이나 guard가 부족하다고 판단

대표 상황:

- switch/power 전제가 필요한 명령에서 바로 action만 수행

#### `semantic`

의미:

- command 의미와 생성된 action/service의 의미 정렬이 약함

대표 상황:

- close/open, increase/decrease, lock/unlock 같은 방향이 어긋남

#### `extraneous`

의미:

- 명령에 없는 service/action이 추가됨

대표 상황:

- speaker가 필요 없는데 speaker까지 씀
- value read와 unrelated action을 같이 넣음

### 9-4. GT 정합성 실패

#### `gt_mismatch`

의미:

- GT와 exact match는 아님

중요:

- 이건 가장 넓은 요약 플래그라서, 이것만 보고 원인을 해석하면 부족합니다.
- 반드시 아래 항목과 같이 봐야 합니다.

#### `gt_service_coverage`

의미:

- GT에 필요한 service가 전부 들어오지 않음

예:

- GT가 `HumiditySensor + Speaker`인데 `HumiditySensor`만 쓰고 `Speaker`를 안 씀

실제 synthetic 예:

- row 10 `sensor_only`
  - legacy `87.7078`
  - strict `67.5942`
  - strict failures:
    - `dataflow`
    - `gt_mismatch`
    - `gt_receiver_coverage`
    - `gt_service_coverage`

#### `gt_receiver_coverage`

의미:

- GT가 요구한 receiver scope/instance를 다 처리하지 않음

예:

- `all(#Front #Back #DoorLock)` 이어야 하는데 `Back`만 잠금

실제 synthetic 예:

- row 37 `only_back`
  - legacy `96.7727`
  - strict `69.9`
  - strict failures:
    - `gt_mismatch`
    - `gt_receiver_coverage`

### 9-5. strict 전용 핵심 실패

#### `dataflow`

의미:

- 읽은 값이 실제 downstream 함수에 전달되지 않음

대표 상황:

- sensor value를 읽었지만 speaker/sink 함수가 그 값을 안 씀

실제 synthetic 예:

- row 10 `malformed_chain`
  - legacy `96.1031`
  - strict `69.9`
  - strict failures:
    - `dataflow`
    - `gt_mismatch`

해석:

- legacy는 “두 서비스가 둘 다 등장했다”는 이유로 후하게 줄 수 있지만,
- strict는 “값 전달이 실제로 일어났는지”를 더 봅니다.

#### `numeric_grounding`

의미:

- 숫자/시간/채널/온도 등 numeric content가 GT와 다름

대표 상황:

- `30 minutes`를 잘못된 단위로 사용
- channel number가 다름

실제 synthetic 예:

- row 3 `wrong_unit_ms_expr`
  - legacy `93.9479`
  - strict `69.9`

#### `enum_grounding`

의미:

- enum 값 자체가 다름

대표 상황:

- GT는 `"dry"`인데 `"warm"`을 씀
- mode/type string이 다름

---

## 10. failure_reasons를 조합해서 읽는 법

### `gt_mismatch + dataflow`

해석:

- 대략 맞는 service는 썼지만 값 전달 구조가 틀렸음

### `gt_mismatch + gt_service_coverage`

해석:

- 필요한 service 중 일부가 빠졌음

### `gt_mismatch + gt_receiver_coverage`

해석:

- 대상 장치 그룹/instance를 덜 처리했음

### `gt_mismatch + numeric_grounding`

해석:

- 숫자나 단위가 틀렸음

### `arg_type + enum_grounding`

해석:

- enum 자리 값이 타입/값 둘 다 애매하거나 틀렸을 가능성이 큼

### `service_match + unknown_service:*`

해석:

- 모델이 schema 밖 service명을 invent하고 있음

---

## 11. 실제 DET 해석에서 주의할 점

### legacy가 후하게 줄 수 있는 경우

예:

- service는 얼추 맞는데
- dataflow가 비어 있거나
- receiver coverage가 부족한 경우

이때 legacy는 높은 점수를 줄 수 있습니다.

### strict가 과하게 깎을 수 있는 경우

대표 예:

- service family는 다르지만 의미적으로 거의 같은 동작

예:

- GT: `ColorControl_SetColor("255,255,0")`
- generated: `light_movetorgb(255, 255, 0)`

이 경우 strict는 `gt_service_coverage` 쪽에서 보수적으로 볼 수 있습니다.

즉:

- `legacy`는 false positive가 있고
- `strict`는 일부 false negative가 있습니다.

권장:

- 실험 리포트에는 둘 다 기록
- 운영 판단은 strict를 더 신뢰

---

## 12. 자주 보는 후처리 도구

### benchmark 두 개 비교

```bash
python gpt_mg/version0_15_update20260413/scripts/compare_benchmarks.py \
  --baseline-dir /abs/path/to/baseline_results \
  --retrieval-dir /abs/path/to/experiment_results
```

### 특정 모델 row report 다시 생성

```bash
python gpt_mg/version0_15_update20260413/scripts/export_row_report.py \
  --results-dir /abs/path/to/results_dir \
  --model-key qwen25_coder_14b \
  --category 1 \
  --category 2
```

참고:

- `results_dir` 안에 모델이 하나만 있으면 `--model-key`는 생략 가능합니다.
- 모델이 여러 개 있는 결과 디렉터리면 `--model-key`를 명시해야 합니다.
- 어떤 모델 키가 들어 있는지 먼저 보고 싶으면 아래처럼 확인할 수 있습니다.

```bash
python gpt_mg/version0_15_update20260413/scripts/export_row_report.py \
  --results-dir /abs/path/to/results_dir \
  --list-model-keys \
  --print-json
```

### failure row만 리포트

```bash
python gpt_mg/version0_15_update20260413/scripts/export_row_report.py \
  --results-dir /abs/path/to/results_dir \
  --model-key qwen25_coder_14b \
  --failures-only
```

### DET audit 다시 실행

```bash
python gpt_mg/version0_15_update20260413/scripts/audit_det.py \
  --results-dir /abs/path/to/results_dir \
  --out-dir /abs/path/to/det_audit_dir
```

---

## 13. Local Prompt GA Study

논문용 local 모델 실험에서 `version0_13` prompt를 `version0_15` block 구조로 쪼갠 뒤, 각 block variant를 DNA gene처럼 crossover/mutation 하려면 아래 스크립트를 씁니다.

- [run_local_prompt_ga_study.py](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_local_prompt_ga_study.py)
- [run_local_prompt_ga_study.sh](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/run_local_prompt_ga_study.sh)

### 빠른 smoke test

```bash
python gpt_mg/version0_15_update20260413/scripts/run_local_prompt_ga_study.py \
  --llm-mode mock \
  --model-key qwen25_coder_7b \
  --category 1 \
  --limit-per-category 1 \
  --population 2 \
  --gens 1 \
  --sample-size 1 \
  --validation-size 1 \
  --skip-final-eval
```

### 실제 local 모델 단일 카테고리

```bash
python gpt_mg/version0_15_update20260413/scripts/run_local_prompt_ga_study.py \
  --model-key qwen25_coder_7b \
  --category 1 \
  --population 4 \
  --gens 3 \
  --sample-size 4 \
  --validation-size 4 \
  --candidate-k 1 \
  --det-profile strict \
  --service-context-mode retrieval_fallback \
  --retrieval-topk 10 \
  --retrieval-mode hybrid \
  --retrieval-device cpu
```

### 여러 local 모델과 여러 카테고리

```bash
bash gpt_mg/version0_15_update20260413/scripts/run_local_prompt_ga_study.sh \
  --model-key phi35_mini \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --category 1 \
  --category 2 \
  --category 3 \
  --population 4 \
  --gens 4 \
  --sample-size 4 \
  --validation-size 4 \
  --candidate-k 1 \
  --det-profile strict \
  --service-context-mode retrieval_fallback \
  --retrieval-topk 10 \
  --retrieval-mode hybrid \
  --retrieval-device cpu
```

생성되는 대표 결과:

- `results/local_prompt_ga_study_<timestamp>/ga_progress_all.csv`: generation별 best genome의 DET, pass rate, token, latency, failure summary
- `results/local_prompt_ga_study_<timestamp>/ga_best_by_model_category.csv`: 모델/category별 최종 요약 표
- `results/local_prompt_ga_study_<timestamp>/ga_failure_feedback_summary.csv`: DET failure reason과 다음 generation에 주입 가능한 feedback rule
- `results/local_prompt_ga_study_<timestamp>/gene_pool_manifest.json`: `version0_13` prompt가 어떤 block gene variant로 변환됐는지
- `results/local_prompt_ga_study_<timestamp>/figures/*.png`: generation별 DET/pass 그래프, best DET heatmap, improvement bar, failure reason count
- `results/local_prompt_ga_study_<timestamp>/index.html`: 표와 그래프를 한 번에 보는 paper-oriented report

해석 기준:

- `best_validation_det`가 generation이 지날수록 오르면 prompt gene search가 category-specific 성능을 개선한 것입니다.
- `improvement_vs_generation1`는 첫 generation 대비 가장 좋은 generation의 validation DET 증가량입니다.
- `final_all_avg_det`는 선택 category 전체 row에 best genome을 다시 적용한 값입니다.
- `ga_failure_feedback_summary.csv`에서 failure reason이 줄거나 바뀌는 흐름은 DET 피드백이 mutation rule로 반영되는지를 보여줍니다.

### 13-3. GA core: block-structured prompt artifact search

`run_ga_search.py`는 prompt block을 genotype으로 다루는 가장 작은 GA core runner입니다.

Core blocks:

- `01`
- `02`

Optional guidance blocks:

- `03`
- `05`
- `06`

중요:

- Core blocks는 항상 포함됩니다.
- Optional guidance blocks만 activation/deactivation/replacement 됩니다.
- `block_replacement`는 가능하면 같은 block ID family 안에서 `blocks/generated/`의 대체 artifact로 `source_file`을 교체합니다.
- `blocks=[...]`는 candidate prompt를 렌더링한 active block IDs입니다.
- 이 표기는 cloud prompt의 임의 fragment를 사용한다는 뜻이 아닙니다.
- Retrieval pre-mapping과 top-k service context는 runtime fixed path이며 GA mutation target이 아닙니다.
- `utils/prompt_surgery_rules.py`는 `version0_13` prompt repair 지식을 DET failure reason -> block family -> mutation type -> micro-rule로 정리합니다.

Feedback-to-mutation examples:

- `invalid_json` -> `Output_Schema` -> JSON-only rule 강화
- `unknown_service` -> `Service_Mapping` -> canonical service name rule 추가
- `enum_grounding` -> `Enum_Grounding` -> enum/type rule 강화
- `temporal_error` -> `Temporal_Rule` -> elapsed-time rule 강화
- `dataflow` -> `Dataflow` -> sensor-to-action flow rule 추가
- `extraneous` -> `Minimality` -> no-unrelated-action rule 강화

LLM mutation advisor:

- `--llm-mutation-advisor`는 generation 끝에서 top/bottom genomes, category diagnostics, failure histogram을 요약해 prompt-block mutation proposal만 받습니다.
- Advisor는 JOILang code generator가 아닙니다.
- Advisor proposal은 best prompt를 직접 덮어쓰지 않고 다음 세대 child genome으로 들어가 경쟁합니다.
- Unsafe proposal은 reject됩니다: retrieval 변경, core block 제거, unknown block target, JOILang code 생성.

Advisor options:

- `--advisor-model-key`: advisor backend model key. Default `gpt41_mini`
- `--advisor-top-k`: advisor prompt에 넣을 상위 genome 수. Default `3`
- `--advisor-bottom-k`: advisor prompt에 넣을 하위 genome 수. Default `3`
- `--advisor-max-examples`: representative failure row 수. Default `5`
- `--advisor-temperature`: advisor sampling temperature. Default `0.0`

빠른 smoke:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_ga_search.py \
  --profile version0_15_update20260413 \
  --smoke \
  --llm-mode mock \
  --progress minimal
```

Staged execution:

- No stage flag + no `--full-run`: safe dry-run only
- `--dry-run`: no model calls, validates setup and writes empty artifacts
- `--smoke`: one-row smoke, capped `population<=4`, `gens<=2`, `candidate_k=1`
- `--small-category-smoke`: categories `1,2`, `limit_per_category<=2`
- `--small-ga-advisor-smoke`: advisor-enabled smoke, mock advisor fallback if no endpoint is configured
- `--full-run`: required for uncapped long runs
- `--resume`: reuse an existing output directory as a resumable run
- `--force`: allow writing into a non-empty output directory

진짜 local smoke:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_ga_search.py \
  --profile version0_15_update20260413 \
  --model-key qwen25_coder_7b \
  --limit 1 \
  --population 1 \
  --gens 1 \
  --sample-size 1 \
  --validation-size 1 \
  --cheap-eval-limit 1 \
  --candidate-k 1 \
  --feedback-guided-mutation \
  --progress quiet
```

GA progress output:

- `--progress quiet`: 최종 요약만 출력
- `--progress minimal`: generation summary, top-k genomes, feedback summary, population transition
- `--progress verbose`: row-level failure summary까지 확장 가능

Full prompt는 `--print-prompts`를 명시하지 않으면 출력하지 않습니다.

주요 artifact:

- `ga_generation_progress.csv`
- `ga_generation_progress.jsonl`
- `ga_topk_genomes.csv`
- `ga_block_diffs.jsonl`
- `ga_population_diagnostics.csv`
- `ga_population_diagnostics.jsonl`
- `advisor_prompt_generation_<gen>.txt`
- `advisor_response_generation_<gen>.json`
- `advisor_mutation_proposals.jsonl`
- `advisor_mutation_summary.csv`
- `structured_feedback.jsonl`
- `structured_feedback_summary.csv`
- `population_transitions.csv`
- `promotion_decisions.csv`
- `best_genome.json`
- `best_prompt_metadata.json`
- `ga_summary.json`

---

## 14. 권장 워크플로우

### 실험 전

1. `run_benchmark.py --preflight-only`
2. `prepare_local_models.py`

### 실험 중

1. benchmark 실행
2. 필요하면 `--export-paper-artifacts`
3. single-model이면 row report 자동 생성 확인
4. A/B 실험이면 `--compare-to`

### 실험 후

1. `report.pdf`로 GT vs generated 확인
2. `failure_reason_summary.csv`로 실패 분포 확인
3. `audit_det.py`로 legacy/strict 차이 확인
4. `paper_figures/`로 논문용 figure 확인

---

## 15. 디버깅할 때 먼저 볼 것

### prompt가 너무 길다

- `inspect_service_context.py`
- `row_comparison.csv`의 `__prompt_tokens`
- `service_list_snippet_source`

### DET가 예상보다 높거나 낮다

- `failure_reasons`
- `det_gt_service_coverage`
- `det_gt_receiver_coverage`
- `det_dataflow_score`
- `det_numeric_grounding`
- `det_enum_grounding`
- 필요하면 `audit_det.py`

### 모델은 돌았는데 코드가 빈다

- `generation_error_type`
- `oom_flag`
- `failure_reason_summary.csv`
- row report PDF에서 빈 코드 row 확인

### premapping 영향이 궁금하다

- baseline run
- retrieval run
- `compare_benchmarks.py`

---

## 16. 요약

가장 중요한 포인트만 다시 적으면:

- 실행은 `run_benchmark.py`
- single-model은 row report 자동 생성
- A/B 비교는 `--compare-to`
- DET 내부 점수 감사는 `--analyze-det` 또는 `audit_det.py`
- failure_reasons는 “왜 감점됐는지”를 설명하는 태그
- `gt_mismatch` 하나만 보지 말고 coverage/dataflow/numeric/enum을 같이 봐야 함

이 문서 하나만 보고도 benchmark 실행, 결과 비교, row-level 분석, DET 해석까지 이어질 수 있도록 정리한 것이 목적입니다.


Advisor options (GA prompt search):
- `--llm-mutation-advisor`: Enable an LLM mutation advisor that analyzes population diagnostics and proposes prompt-block mutations for next generation candidates.
- `--advisor-model-key`: Advisor model key (typically `gpt41_mini`). Advisor is a critic/proposer, not a JOILang generator.
- `--advisor-top-k`: Number of best genomes included in advisor context.
- `--advisor-bottom-k`: Number of worst genomes included in advisor context.
- `--advisor-max-examples`: Maximum failed-row examples shown to advisor.
- `--advisor-temperature`: Advisor temperature (default `0.0` for deterministic JSON proposals).

The advisor does not replace GA selection. It only proposes mutation candidates; GA still evaluates all children and performs normal selection.

### 13-4. Redesigned GA mode: archive, Pareto, cloudless mutation, active controller

The redesigned GA core is opt-in so legacy experiments remain reproducible.

Recommended smoke:

```bash
python -u gpt_mg/version0_15_update20260413/scripts/run_ga_search.py \
  --profile version0_15 \
  --model-key qwen25_coder_7b \
  --population 5 \
  --gens 3 \
  --sample-size 4 \
  --validation-size 4 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --selection-mode redesign \
  --fitness-mode phase_aware \
  --mutation-mode cloudless_decompiler \
  --enable-compression-mutation \
  --enable-rendered-prompt-dedupe \
  --stop-controller-mode active \
  --enable-pareto-archive \
  --category-balance-mode guard \
  --token-penalty-mode hybrid \
  --category 1 \
  --category 2 \
  --limit-per-category 2 \
  --full-run
```

What changes in redesigned mode:

- `ga_generation_progress.csv` separates `raw_generation_best_DETPass` from `best_so_far_DETPass`.
- Selection can use phase-aware `score_main` with DETPass primary, AvgDET secondary, and conservative token/regression penalties.
- `population_transitions.csv` records archive survival and child origin: crossover, mutation, compression, diversity, specialist, disruptive.
- `mutation_proposals.jsonl` is the shared proposal table for cloudless and advisor-guided mutation.
- `pareto_archive.csv` records DETPass/token non-dominated candidates.
- `generation_phase`, `plateau_type`, and `next_action` explain whether the controller stayed in accuracy search, switched to robustness, switched to compression, increased diversity, or finalized.

Retrieval pre-mapping remains fixed runtime context. The redesigned GA mutates prompt artifacts only: optional blocks, block params, few-shot count, micro-rules, layout/reasoning hints, candidate strategies, and compression/output-budget settings.

Progress modes:
- `--progress quiet`: final summary only
- `--progress minimal`: compact stage/generation progress
- `--progress verbose`: extended diagnostics
