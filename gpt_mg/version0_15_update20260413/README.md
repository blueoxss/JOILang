# version0_15

`version0_15_update20260413`는 `connected_devices`를 category/tag/location binding으로 prompt에 넣고, 필요할 때 retrieval pre-mapping으로 top-k category만 추려 `service_list_snippet`에 넣을 수 있는 PromptGA 워크스페이스입니다. 기본값은 연구 비교를 위해 기존과 같은 full schema fallback입니다.

## 핵심 동작

- `connected_devices`가 있으면 각 device group별로 `category + 전체 서비스 목록 + 사용자 태그 + location`을 prompt에 넣습니다.
- `connected_devices == {}` 이면 기본값은 `service_schema_fallback`이고, `service_list_ver2.0.1.json` 전체 category/service 목록이 prompt에 들어갑니다.
- retrieval pre-mapping을 명시적으로 켜면 학습된 retrieval bundle이 뽑은 top-k category만 `service_retrieval_fallback`으로 prompt에 들어갑니다.
- retrieval asset이 없거나 retrieval worker가 실패하면 자동으로 `service_schema_fallback`으로 내려갑니다.
- 따라서 같은 row subset에 대해 baseline full schema와 retrieval top-k prompt를 연구용으로 직접 비교할 수 있습니다.
- `admin_logs`가 없어도 benchmark + GA search만 단독으로 돌릴 수 있습니다.
- `admin_logs`가 있으면 실패 명령을 replay해서 manual feedback rule로 흡수하고, benchmark non-regression을 확인한 뒤 `version0_15_updateYYYYMMDD*` 폴더로 승격할 수 있습니다.

## 먼저 볼 문서

- 실행 흐름, 스크립트 역할, 자동 후처리, DET 점수 체계, `failure_reasons` 해설은 [scripts/README.md](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/README.md) 에 정리돼 있습니다.
- 더 읽기 쉬운 시각화 버전은 [scripts/README.html](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/README.html) 과 [scripts/README.pdf](/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/scripts/README.pdf) 에 있습니다.
- 특히 어떤 스크립트를 직접 실행해야 하는지 헷갈릴 때는 `scripts/README.md`를 먼저 보는 것이 가장 빠릅니다.

## 자주 쓰는 환경 변수

`demo.py` 또는 `gpt_mg/run.py gpt_mg.version0_15 ...` 경로:

```env
JOI_VERSION015_PYTHON=/abs/path/to/python
JOI_VERSION015_WORKER=/abs/path/to/gpt_mg/version0_13/qwen_local_worker.py
JOI_VERSION015_GENOME=/abs/path/to/gpt_mg/version0_15/results/best_genome_after_feedback.json
```

`gpt_mg/version0_15/scripts/*` 경로:

```env
JOI_V15_LLM_MODE=worker
JOI_V15_WORKER_PATH=/abs/path/to/gpt_mg/version0_13/qwen_local_worker.py
JOI_V15_PYTHON=/abs/path/to/python
JOI_V15_LOCAL_DEVICE=cuda:0
JOI_V15_OPENAI_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions
```

`version0_15/utils/local_llm_client.py`는 `JOI_V15_*`를 먼저 보고, 없으면 `JOI_V14_*`를 fallback으로 사용합니다.

## Retrieval Pre-mapping

`service_list_snippet`은 이제 prompt block 안에서 직접 진화시키는 텍스트가 아니라, runtime에서 강제로 채워 넣는 capability scope입니다.

- GA가 바꿀 수 있는 것은 block 본문뿐이고, retrieval shortlist 생성은 `utils/pipeline_common.py`의 runtime path에서 고정됩니다.
- 즉 prompt search를 돌려도 retrieval pre-mapping 자체를 제거하거나 다른 구조로 바꾸지 못합니다.
- 기본 service context mode는 `schema_fallback`입니다.
  - `connected_devices` 있음: 항상 `connected_devices_only`
  - `connected_devices` 비어 있음 + 명시적으로 retrieval 사용: `service_retrieval_fallback`
  - 그 외: `service_schema_fallback`

기본 retrieval asset 탐색 순서:

- `gpt_mg/version0_15_update20260413/retrieval_assets/...`
- 없으면 sibling repo인 `../ModelMagementApp/...`

즉 학습된 retrieval model/bundle을 굳이 `JOILang-Server` 안으로 복사하지 않아도 됩니다. 그대로 sibling `ModelMagementApp` 경로를 참조합니다. 원하면 `JOI_V15_RETRIEVAL_JSON`, `JOI_V15_RETRIEVAL_BUNDLE_DIR`, `JOI_V15_RETRIEVAL_MODEL_DIR`로 override할 수 있습니다.

추가 환경 변수:

```env
JOI_V15_SERVICE_CONTEXT_MODE=schema_fallback
JOI_V15_RETRIEVAL_TOPK=10
JOI_V15_RETRIEVAL_MODE=hybrid
JOI_V15_RETRIEVAL_DEVICE=cpu
JOI_V15_RETRIEVAL_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
JOI_V15_RETRIEVAL_JSON=/abs/path/to/service_list_ver2.0.1_retrieval_eng.json
JOI_V15_RETRIEVAL_BUNDLE_DIR=/abs/path/to/embedding_result_v5_ver2.0.1
JOI_V15_RETRIEVAL_MODEL_DIR=/abs/path/to/BAAI_bge-m3__service_list_ver2.0.1_retrieval_eng
```

빠르게 snippet source와 prompt 길이를 비교하려면:

```bash
python gpt_mg/version0_15_update20260413/scripts/inspect_service_context.py \
  --row-no 1 \
  --mode schema_fallback \
  --mode retrieval_fallback \
  --retrieval-topk 10 \
  --retrieval-device cpu
```

이 스크립트는 다음을 기록합니다.

- `service_list_snippet_source`
- `service_list_device_count`
- `service_list_retrieval_status`
- `service_list_retrieval_categories`
- `service_list_snippet_chars`
- `rendered_prompt_chars`

출력 파일:

- `results/service_context_inspection/service_context_summary.json`
- `results/service_context_inspection/service_context_rows.csv`

## Prompt Render Mode

`version0_15_update20260413`는 기본적으로 현재 v15 방식의 `genome + blocks` prompt를 씁니다.  
하지만 `version0_13`처럼 여러 prompt 파일을 합쳐 **하나의 큰 monolithic prompt**로도 돌릴 수 있습니다.

지원 모드:

- `blocks`
  - 기본값
  - `best_genome.json` 또는 지정한 genome의 `blocks`를 렌더링해서 prompt를 구성
- `legacy_v13_monolith`
  - `version0_13`의 prompt 자산을 읽어서 하나의 큰 prompt로 구성
  - generation과 repair 모두 같은 모드로 동작

중요:

- 이 옵션은 **prompt의 모양**을 바꾸는 것입니다.
- service schema 자체를 `version0_13`으로 되돌리는 것이 아닙니다.
- 실제 service context는 여전히 현재 v15 runtime을 따라갑니다.
  - `connected_devices`가 있으면 그 subset
  - retrieval premapping을 켜면 top-k category shortlist
  - 아니면 full schema fallback

기본 prompt asset 경로:

- `/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13`

명시적으로 주고 싶으면:

```bash
--prompt-render-mode legacy_v13_monolith \
--prompt-assets-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13
```

local smoke 예시:

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

cloud smoke 예시:

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

## Final Paper Study Pipeline

최종 논문 “Genetic Prompt Search for JOILang Code Generation under Deterministic Validation and Operational Feedback”의 산출물은 아래 entrypoint를 기준으로 생성합니다.

```bash
python gpt_mg/version0_15_update20260413/scripts/run_paper_full_study.py \
  --suite paper_local5 \
  --include-cloud-ref \
  --models phi35_mini,qwen25_coder_7b,llama31_8b,gemma2_9b_it,qwen25_coder_14b \
  --categories 1,2,3,4,5,6,7,8 \
  --paper-fair-mode \
  --resume \
  --quiet-final-summary \
  --full-run
```

가벼운 검증만 할 때:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_paper_full_study.py \
  --dry-run \
  --smoke \
  --include-cloud-ref \
  --models qwen25_coder_7b \
  --categories 1 \
  --limit-per-category 1 \
  --quiet-final-summary
```

### B0-B6 Definitions

- `B0`: local hand-crafted baseline. 구현/실행 결과가 없으면 숫자를 만들지 않고 `N/A`로 표시합니다.
- `B1`: GPT-4.1-mini cloud reference. local deployment point가 아니라 cloud upper reference입니다.
- `B2`: direct cloud-to-local transfer. B1 prompt를 local model에 그대로 적용하며 model-specific GA adaptation은 없습니다.
- `B3`: fixed block. block prompt를 쓰지만 GA search를 끕니다.
- `B4`: random search. 같은 block search space를 쓰되 guided GA 대신 unguided random search를 비교 축으로 둡니다.
- `B5`: GA + benchmark only. replay feedback을 search/acceptance에 쓰지 않는 GA 조건입니다.
- `B6`: full GPS / PromptOps. block-structured GA search, benchmark supervision, replay cases, deterministic validation, regression-aware acceptance를 함께 사용합니다.

### Cloud-to-Block Equivalence

cloud reference prompt를 block으로 쪼개는 것 자체가 성능을 떨어뜨리지 않는지 먼저 확인합니다.

```bash
python gpt_mg/version0_15_update20260413/scripts/run_cloud_blocks_equivalence.py \
  --category 1 \
  --limit-per-category 1 \
  --det-profile strict \
  --quiet-final-summary
```

출력:

- `results/cloud_to_blocks_equivalence_<timestamp>/summary.json`
- `results/cloud_to_blocks_equivalence_<timestamp>/monolith_vs_blocks.csv`
- `results/cloud_to_blocks_equivalence_<timestamp>/command.txt`
- `results/cloud_to_blocks_equivalence_<timestamp>/README.md`

`README.md`에는 “This verifies that prompt block decomposition itself does not degrade the cloud reference behavior.” 문장이 포함됩니다.

### Retrieval and GA Boundary

Retrieval pre-mapping은 고정 runtime context construction입니다.

- `service_list_snippet` / service context injection은 runtime capability-scope injection path입니다.
- GA가 mutation 대상으로 삼을 수 있는 것은 prompt block 활성화, micro-rule wording, few-shot count, candidate strategy, compression/max-token setting, repair clause입니다.
- GA는 retrieval top-k 생성 방식, retrieval model, service shortlist construction 자체를 mutation하지 않습니다.

### Deterministic Feedback and Acceptance

DET failure는 structured feedback으로 저장되어 이후 prompt mutation 또는 repair clause injection의 근거가 됩니다.

출력:

- `results/paper_study_<timestamp>/structured_feedback.jsonl`
- `results/paper_study_<timestamp>/structured_feedback_summary.csv`

대표 mapping:

- schema violation -> `output_schema` / `output_format`
- invalid JSON -> `output_format`
- temporal or numeric error -> `temporal_rule` / unit grounding
- owner/device mismatch -> `owner_device_rule`
- enum/type mismatch -> `schema_enum_grounding`
- service coverage/mapping miss -> `service_mapping`

Replay cases는 main leaderboard metric이 아니라 operational feedback 및 acceptance gate입니다. 즉 candidate prompt는 생성되고 평가되지만, replay/regression gate를 통과하지 못하면 promoted prompt가 되지 않습니다. 이전 accepted prompt는 그대로 유지되고 rejection reason이 저장됩니다.

Promotion output:

- `results/paper_study_<timestamp>/paper/promotion/promotion_decisions.csv`
- `results/paper_study_<timestamp>/paper/promotion/promotion_decisions.json`
- `results/paper_study_<timestamp>/PROMOTION.md`

### Required Paper Artifacts

Full or dry-run study는 다음 위치를 고정으로 만듭니다. 실제 측정이 없으면 값을 지어내지 않고 `pending` 또는 `N/A`로 표시합니다.

- Figure 1: `results/paper_study_<timestamp>/paper/figures/figure1_prompt_search_dynamics_across_model_scales.png`
- Figure 1 data: `results/paper_study_<timestamp>/paper/figure_data/figure1_generation_dynamics.csv`
- Figure 2: `results/paper_study_<timestamp>/paper/figures/figure2_deployment_aware_pareto_frontier_final.png`
- Figure 2 data: `results/paper_study_<timestamp>/paper/figure_data/figure2_pareto_points.csv`
- Table 3: `results/paper_study_<timestamp>/paper/tables/table3_main_results.csv`
- Table 4: `results/paper_study_<timestamp>/paper/tables/table4_ablation_qwen14.csv`
- Final manifest: `results/paper_study_<timestamp>/paper/final_artifacts_manifest.json`

Model availability is always recorded:

- `results/paper_study_<timestamp>/availability_summary.csv`
- `results/paper_study_<timestamp>/availability_summary.json`

## GA Prompt-Block Search Core

`run_ga_search.py`는 prompt를 arbitrary text fragment가 아니라 block-structured artifact genotype으로 다룹니다.

Core blocks:

- `01`: system/base JOILang constraints
- `02`: service grounding, output schema foundation, basic JSON rules

Optional guidance blocks:

- `03`: postprocessor / JSON-only / minimality guidance
- `05`: repair clause guidance
- `06`: deterministic validation helper, temporal/dataflow/skeleton guidance

`blocks=[...]`는 candidate prompt를 렌더링하는 active prompt-block IDs를 뜻합니다. 원본 cloud prompt 조각을 임의로 잘라 붙인다는 의미가 아닙니다. Core blocks는 항상 포함되고, optional guidance blocks만 GA가 켜고 끄거나 block parameter/micro-rule을 바꿉니다.

GA가 바꿀 수 있는 것:

- optional block activation/deactivation/replacement
- same block family 안에서 `blocks/generated/`의 대체 block artifact로 source_file replacement
- few-shot count
- max tokens / candidate strategies / compression-style prompt parameters
- micro-rules and repair clauses
- deterministic validation feedback에서 유도된 targeted rule
- optional LLM mutation advisor가 제안한 prompt-block micro-rule

GA가 바꾸면 안 되는 것:

- retrieval pre-mapping mechanism
- retrieval top-k policy
- service context construction path

## GA/Search Improvements

이 워크스페이스에서 최근 대화로 반영된 GA와 search space의 핵심 개선은 아래와 같습니다.

### 1. Prompt를 텍스트 조각이 아니라 genotype으로 취급

이전에는 prompt를 길게 붙여넣는 방식에 가까웠지만, 이제는 `blocks=[...]`로 렌더링되는 block-structured artifact genotype으로 다룹니다.

- `01`, `02`는 core blocks라서 항상 포함됩니다.
- `03`, `05`, `06`은 optional guidance blocks라서 GA가 켜고 끄거나 바꿀 수 있습니다.
- `blocks=[...]`는 임의 fragment가 아니라 active block ID 집합입니다.

### 2. Search space를 넓히되, 바꾸면 안 되는 경계는 고정

GA가 실제로 탐색하는 축은 다음과 같습니다.

- optional block activation/deactivation/replacement
- same-family block artifact replacement
- few-shot count
- max token / candidate strategy
- micro-rules
- repair clauses
- deterministic feedback에서 유도된 targeted rule
- LLM mutation advisor가 제안한 prompt-block micro-rule

대신 아래는 고정입니다.

- retrieval pre-mapping
- retrieval top-k
- service context construction

즉, search space는 커졌지만 retrieval runtime path는 mutation 대상이 아닙니다.

### 3. version0_13의 prompt surgery 지식을 v15 GA에 재사용

이전 히스토리에서 반복해서 다뤘던 DET failure 유형을 `utils/prompt_surgery_rules.py`에 옮겨서 재사용합니다.

대표적으로:

- `invalid_json` -> JSON-only output 강화
- `unknown_service` -> canonical service name 강화
- `enum_grounding` -> enum/type grounding 강화
- `temporal_error` -> elapsed-time / temporal rule 강화
- `owner_device_mismatch` -> owner/device binding 강화
- `dataflow` -> sensor-to-action flow 강화
- `extraneous` -> no-unrelated-action / minimality 강화

이제 deterministic validation 결과가 단순 로그가 아니라, 다음 세대 mutation 방향을 고르는 구조화된 feedback source가 됩니다.

### 4. LLM mutation advisor를 별도 critic으로 분리

Advisor는 JOILang 코드를 쓰는 모델이 아니라, prompt-block mutation만 제안하는 critic입니다.

- generation 끝에 population diagnostics를 요약합니다.
- top/bottom genomes, category별 failure histogram, 대표 failure rows를 보고 제안합니다.
- proposal은 다음 세대 child genome으로 들어가고, 일반 GA 평가를 거쳐야 합니다.
- advisor는 core block 제거, retrieval 변경, code 생성은 할 수 없습니다.

### 5. 실행이 stage-safe해짐

GA와 paper pipeline은 이제 무작정 full run을 시작하지 않습니다.

- `--dry-run`: 모델 호출 없이 설정만 검증
- `--smoke`: one-row smoke
- `--small-category-smoke`: categories 1,2
- `--small-ga-advisor-smoke`: advisor mock/schema smoke
- `--full-run`: 긴 실험을 명시적으로 허용

### 6. 결과물과 추적성이 좋아짐

각 run은 다음을 남깁니다.

- `ga_generation_progress.csv/jsonl`
- `ga_topk_genomes.csv`
- `ga_block_diffs.jsonl`
- `ga_population_diagnostics.csv/jsonl`
- `structured_feedback.jsonl`
- `advisor_prompt_generation_<gen>.txt`
- `advisor_response_generation_<gen>.json`
- `advisor_mutation_proposals.jsonl`
- `advisor_mutation_summary.csv`
- `population_transitions.csv`
- `promotion_decisions.csv`
- `best_genome.json`
- `best_prompt_metadata.json`
- `ga_summary.json`

이렇게 해서 “무엇이 바뀌었고, 왜 바뀌었고, 다음 세대에 어떻게 반영됐는지”를 artifact 기준으로 추적할 수 있게 만들었습니다.

### Deterministic Feedback To Prompt Surgery

`utils/prompt_surgery_rules.py`는 `version0_13`에서 수동으로 축적했던 DET 기반 prompt repair 지식을 v15 GA가 재사용할 수 있는 작은 registry로 정리합니다.

대표 mapping:

- `invalid_json` -> `Output_Schema` / `strengthen_json_only_rule`
- `unknown_service` -> `Service_Mapping` / `add_canonical_service_name_rule`
- `arg_type`, `enum_grounding` -> `Enum_Grounding` / `strengthen_enum_type_rule`
- `numeric_grounding`, `temporal_error` -> `Temporal_Rule` / `strengthen_temporal_rule`
- `gt_receiver_coverage` -> `Owner_Device_Rule` / `strengthen_owner_device_rule`
- `dataflow` -> `Dataflow` / `add_sensor_to_action_flow_rule`
- `extraneous` -> `Minimality` / `strengthen_no_unrelated_action_rule`

이 mapping은 row 하나에 대한 hard-code가 아니라 failure reason family를 prompt block family와 mutation type으로 연결하는 공통 feedback source입니다.

### LLM Mutation Advisor

`--llm-mutation-advisor`를 켜면 generation 끝에서 population-level diagnostics를 요약해 별도 LLM advisor에게 prompt-block mutation 제안만 요청합니다.

Advisor의 역할:

- top/bottom genome, category diagnostics, failure histogram을 보고 mutation proposal 생성
- target block, mutation type, proposed micro-rule 제안
- advisor 제안 child는 다음 세대 population에 들어가고 일반 GA 평가를 통과해야 함

Advisor가 하면 안 되는 것:

- JOILang code 생성
- core block 제거
- retrieval pre-mapping, retrieval top-k, service context construction 변경
- best prompt를 직접 overwrite

Advisor artifact:

- `advisor_prompt_generation_<gen>.txt`
- `advisor_response_generation_<gen>.json`
- `advisor_mutation_proposals.jsonl`
- `advisor_mutation_summary.csv`

현재 fitness는 명시적으로 아래 식을 사용합니다.

```text
fitness = AvgDET - alpha * VarDET
```

Legacy GA에서는 token/latency가 selection fitness의 직접 항이 아니며 deployment comparison artifact에서 별도로 평가됩니다.

Redesigned GA mode에서는 `--fitness-mode phase_aware`와 `--token-penalty-mode budget|accepted|hybrid`를 켜면 DETPass를 1차 목표로 두고 AvgDET, category guard, token penalty, compression gain, regression penalty를 함께 기록/사용합니다. 이 모드는 기존 artifact를 덮어쓰지 않고 `score_main`, `best_so_far_DETPass`, `generation_phase`, `pareto_archive_size`, `mutation_proposals.jsonl`, `pareto_archive.csv` 같은 새 필드를 추가합니다.

Redesign preset:

```bash
python -u gpt_mg/version0_15_update20260413/scripts/run_ga_search.py \
  --profile version0_15 \
  --model-key qwen25_coder_7b \
  --selection-mode redesign \
  --fitness-mode phase_aware \
  --mutation-mode cloudless_decompiler \
  --enable-compression-mutation \
  --enable-rendered-prompt-dedupe \
  --stop-controller-mode active \
  --enable-pareto-archive \
  --category-balance-mode guard \
  --token-penalty-mode hybrid \
  --population 10 \
  --gens 20 \
  --full-run
```

Important boundaries:

- Retrieval pre-mapping, retrieval top-k/mode, and service-context construction remain fixed runtime paths and are not GA mutation targets.
- Core blocks remain active; optional guidance blocks and block params are the prompt artifact search space.
- Cloudless mutation and advisor mutation both write canonical proposal rows to `mutation_proposals.jsonl`.
- `raw_generation_best_DETPass` and `best_so_far_DETPass` are separate so raw generation oscillation is not mistaken for loss of the archive best.

빠른 GA smoke:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_ga_search.py \
  --profile version0_15_update20260413 \
  --smoke \
  --llm-mode mock \
  --progress minimal
```

Staged GA execution:

- default with no stage flag: safe `dry-run`
- `--dry-run`: validate CLI, dataset selection, genome loading, core/optional block split, and artifact paths without model calls
- `--smoke`: one-row smoke with capped population/generations and `candidate_k=1`
- `--small-category-smoke`: categories `1,2` with `limit_per_category<=2`
- `--small-ga-advisor-smoke`: advisor-enabled tiny smoke; uses mock advisor if no endpoint/mode is configured
- `--full-run`: required for uncapped long runs
- `--resume`: allow writing into an existing run directory for continuation
- `--force`: explicitly allow writing into a non-empty output directory

대표 출력 artifact:

- `ga_generation_progress.csv`
- `ga_generation_progress.jsonl`
- `ga_topk_genomes.csv`
- `ga_block_diffs.jsonl`
- `ga_population_diagnostics.csv`
- `ga_population_diagnostics.jsonl`
- `advisor_mutation_proposals.jsonl`
- `advisor_mutation_summary.csv`
- `structured_feedback.jsonl`
- `structured_feedback_summary.csv`
- `population_transitions.csv`
- `promotion_decisions.csv`
- `promotion_decisions.json`
- `best_genome.json`
- `best_prompt_metadata.json`
- `ga_summary.json`

## 빠른 benchmark + GA

`admin_logs`와 상관없이 benchmark/GA만 확인하려면:

```bash
cd /home/andrew/joi-llm/gpt_mg/version0_15

bash scripts/run_full_pipeline.sh \
  --mode quick \
  --llm-mode worker \
  --seed 31
```

좀 더 직접적으로 보고 싶으면:

```bash
python scripts/run_ga_search.py \
  --profile version0_15 \
  --genome-json genomes/example_genome.json \
  --population 4 \
  --gens 3 \
  --sample-size 5 \
  --validation-size 5 \
  --limit 5 \
  --candidate-k 2 \
  --llm-mode worker \
  --seed 31
```

## `admin_logs`가 없어도 되는 통합 업데이트

아래 스크립트는 `admin_logs`가 없으면 benchmark + GA만 수행합니다.

```bash
cd /home/andrew/joi-llm

python gpt_mg/version0_15/scripts/run_admin_feedback_update.py \
  --admin-log-root /tmp/no-admin-logs \
  --benchmark-limit 20 \
  --llm-mode worker \
  --seed 31
```

빠른 smoke 용도:

```bash
python gpt_mg/version0_15/scripts/run_admin_feedback_update.py \
  --admin-log-root /tmp/no-admin-logs \
  --benchmark-limit 1 \
  --ga-population 2 \
  --ga-gens 1 \
  --ga-sample-size 1 \
  --ga-validation-size 1 \
  --benchmark-candidate-k 1 \
  --skip-category-sweep \
  --llm-mode worker \
  --seed 31
```

## `admin_logs`를 반영한 업데이트

Slack JSONL이나 직접 만든 JSON/JSONL/TXT/MD를 `admin_logs` 아래에 두고 실행하면 됩니다.

```bash
python gpt_mg/version0_15/scripts/run_admin_feedback_update.py \
  --admin-log-root admin_logs \
  --benchmark-limit 20 \
  --llm-mode worker \
  --seed 31
```

지원하는 입력 형태:

- `admin_logs/slack/*.jsonl` 같은 Slack DM 로그
- `command_eng`, `command_kor`, `gt`, `connected_devices`, `manual_rules`가 들어 있는 `.json`
- 자유 텍스트 `.txt` 또는 `.md`

구조화된 케이스일수록 replay와 prompt patch 품질이 좋아집니다.

## `demo.py`에서 실행

서버를 켠 뒤:

```bash
curl -s -X POST http://localhost:8000/run_admin_feedback_update \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt_mg.version0_15",
    "admin_log_root": "/tmp/no-admin-logs",
    "benchmark_limit": 20,
    "llm_mode": "worker",
    "seed": 31
  }'
```

promotion이 성공하면 `demo.py`는 `gpt_mg/version0_15_update*` 폴더를 자동으로 `/get_model_list` 결과에 추가합니다.

## 결과 파일

- `results/admin_feedback_update_<timestamp>/summary.json`
- `results/admin_feedback_update_<timestamp>/report.md`
- `results/admin_feedback_update_<timestamp>/admin_cases.csv`
- `results/best_genome_from_ga.json`
- `results/best_genome_after_feedback.json`
- `logs/admin_feedback/manual_feedback.json`
- promotion 성공 시 `gpt_mg/version0_15_updateYYYYMMDD*/results/admin_feedback_update_summary.json`

## 같은 prompt로 논문 모델군 비교하기

현재 `results/best_genome.json` 또는 지정한 genome을 그대로 유지한 채, 모델만 바꿔서 같은 prompt를 비교하려면 `scripts/run_model_suite_benchmark.py`를 사용하면 됩니다.

기본 suite:

- `paper_local5`: `Phi-3.5-mini-instruct`, `Qwen2.5-Coder-7B-Instruct`, `Llama-3.1-8B-Instruct`, `Gemma-2-9B-it`, `Qwen2.5-Coder-14B-Instruct`
- `paper_with_cloud_ref`: 위 5개 + `GPT-4.1-mini`

현재 readiness snapshot은 아래 문서를 기준으로 보는 것이 가장 정확합니다.

- `MODEL_SETUP.md`
- `EXPERIMENT_SETUP.md`

현재 이 워크스페이스에서 바로 same-prompt compare까지 확인된 모델:

- `qwen25_coder_7b`
- `qwen25_coder_14b`

현재 막혀 있는 모델:

- `phi35_mini`
  - cache는 있음
  - row 1 schema-fallback prompt에서 GPU OOM으로 smoke 실패
- `llama31_8b`
  - Hugging Face gated repo
- `gemma2_9b_it`
  - Hugging Face gated repo

기본 실행 환경:

```bash
cd /home/mgjeong/Desktop/llm/JOILang-Server

export JOI_V15_WORKER_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
export JOI_V15_LOCAL_DEVICE=cuda:0
```

먼저 worker runtime과 cache 상태부터 확인:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --preflight-only \
  --print-worker-info
```

모델 준비와 one-row smoke를 다시 돌리려면:

```bash
python gpt_mg/version0_15_update20260413/scripts/prepare_local_models.py \
  --suite paper_local5 \
  --download-missing
```

## 공정한 비교 원칙

- 정확도만 보지 말고 `DET`, `warm latency`, `cold load time`, `prompt tokens`, `peak VRAM`, `OOM/failure rate`를 함께 봅니다.
- 여러 모델을 동시에 VRAM에 상주시킨 상태의 latency 비교는 권장하지 않습니다.
- 공정한 latency 비교는 `--paper-fair-mode` 또는 `--latency-isolation-mode fresh_worker`로 모델별 fresh worker를 띄운 뒤 warmup 후 측정합니다.
- `cold_load_sec`는 fresh worker에서 warmup 첫 요청에 걸린 시간을 사용합니다.
- `warm_latency_*`는 warmup 이후 evaluation row들만 기준으로 계산합니다.
- `prompt_tokens`는 모델별 tokenizer 기준으로 측정되므로 같은 문자열 prompt여도 모델마다 달라질 수 있습니다.

## 가장 많이 쓰는 명령

single row compare:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode compare \
  --strict-availability
```

single row compare with stricter DET profile:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 10 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --det-profile strict \
  --disable-retrieval-premapping \
  --print-mode compare \
  --strict-availability
```

single row compare with retrieval pre-mapping:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --enable-retrieval-premapping \
  --retrieval-topk 10 \
  --retrieval-device cpu \
  --print-mode compare \
  --strict-availability
```

force old full-schema behavior for ablation:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --disable-retrieval-premapping \
  --print-mode compare \
  --strict-availability
```

row range compare:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --start-row 1 \
  --end-row 20 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

single category:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --category 1 \
  --limit 5 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

multiple categories:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --category 1 \
  --category 2 \
  --limit-per-category 10 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

category file:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --category-file /tmp/joi_categories.txt \
  --limit-per-category 10 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

available categories:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --list-categories
```

full dataset:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

paper-fair mode:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --paper-fair-mode \
  --export-paper-artifacts \
  --print-mode summary \
  --strict-availability
```

explicit warmup row:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --start-row 1 \
  --end-row 20 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --measure-latency \
  --latency-isolation-mode fresh_worker \
  --warmup-row-no 1 \
  --print-mode summary
```

wall-clock oriented parallel mode:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --start-row 1 \
  --end-row 20 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --max-workers 2 \
  --print-mode summary
```

이 parallel 모드는 전체 실험 시간을 줄이기 위한 것이고, latency 공정 비교용 숫자로 해석하면 안 됩니다.

paper figure export only:

```bash
python gpt_mg/version0_15_update20260413/scripts/export_paper_figures.py \
  --results-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/results/model_suite_20260421_121042
```

GT code와 생성된 JOICode를 좌우 비교하는 HTML/PDF 리포트:

```bash
python gpt_mg/version0_15_update20260413/scripts/export_row_report.py \
  --results-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/results/model_suite_20260423_222827 \
  --model-key qwen25_coder_14b \
  --category 1 \
  --category 2
```

이 리포트는 아래를 함께 보여줍니다.

- row별 `GT JOICode` vs `Generated JOICode` 좌우 배치
- `DET`, `GT similarity`, `GT service coverage`, `receiver coverage`, `dataflow`, `numeric grounding`, `enum grounding`
- `prompt_tokens`, `completion_tokens`, `llm_latency_sec`, `total_pipeline_sec`, `tokens_per_sec`, `peak_vram_gb`
- `failure_reasons`, retrieval snippet source, retrieval top-k category
- summary 카드와 선택 row CSV

기본 출력:

- `results/model_suite_<timestamp>/side_by_side_report_<model_key>/report.html`
- `results/model_suite_<timestamp>/side_by_side_report_<model_key>/report.pdf`
- `results/model_suite_<timestamp>/side_by_side_report_<model_key>/report_summary.json`
- `results/model_suite_<timestamp>/side_by_side_report_<model_key>/selected_rows.csv`

자동 후처리:

- `run_benchmark.py`는 single-model run이면 기본적으로 row report를 자동 export합니다.
- `--skip-row-report`를 주면 이 자동 동작을 끌 수 있습니다.
- multi-model run에서 row report를 자동으로 만들고 싶으면 `--export-row-report` 또는 `--row-report-model-key ...`를 사용합니다.
- 이전 run과 자동 비교하려면 `--compare-to /abs/path/to/older/results_dir`
- 현재 run에 대한 DET audit을 자동으로 돌리려면 `--analyze-det`
- 긴 기존 이름의 `run_model_suite_benchmark.py`, `compare_service_context_results.py`, `export_joi_code_side_by_side_report.py`, `analyze_det_profiles.py`도 호환용으로 계속 동작합니다.

## 주요 산출물

- `results/model_suite_<timestamp>/suite_manifest.json`
- `results/model_suite_<timestamp>/suite_summary.csv`
- `results/model_suite_<timestamp>/row_comparison.csv`
- `results/model_suite_<timestamp>/latency_breakdown.csv`
- `results/model_suite_<timestamp>/failure_reason_summary.csv`
- `results/model_suite_<timestamp>/generation_error_summary.csv`
- `results/model_suite_<timestamp>/category_summary.csv`
- `results/model_suite_<timestamp>/category_model_comparison.csv`
- `results/model_suite_<timestamp>/main_model_comparison.csv`
- `results/model_suite_<timestamp>/tradeoff_summary.csv`
- `results/model_suite_<timestamp>/latency_summary.csv`
- `results/model_suite_<timestamp>/vram_summary.csv`
- `results/model_suite_<timestamp>/tokenizer_summary.csv`
- `results/model_suite_<timestamp>/paper_metrics_summary.json`
- `results/model_suite_<timestamp>/paper_figures/det_vs_warm_latency.png`
- `results/model_suite_<timestamp>/paper_figures/det_vs_prompt_tokens.png`
- `results/model_suite_<timestamp>/paper_figures/category_det_vs_warm_latency.png`
- `results/model_suite_<timestamp>/paper_figures/category_det_vs_prompt_tokens.png`
- `results/model_suite_<timestamp>/paper_figures/category_metric_panels.png`

참고:

- `--repair-attempts 0`이면 raw same-prompt transfer 비교에 가깝습니다.
- `--strict-availability`를 함께 주면 선택한 모델 중 현재 runtime에서 쓸 수 없는 모델이 있을 때 benchmark를 시작하지 않습니다.
- 현재 기본 `worker` 경로는 `ollama`가 아니라 Hugging Face cache를 사용합니다.
- `--print-mode compare`는 row별 `GT code`, `Generated code`, `det_score`, `failure_reasons`, `prompt_tokens`, `llm_latency_sec`, `peak_vram_gb`, `diff summary`를 같이 보여줍니다.
- `--det-profile strict`를 주면 기존 legacy 점수는 그대로 보존한 채, GT service coverage, receiver coverage, dataflow, numeric grounding을 더 엄격하게 반영한 strict scoring으로 rerank와 summary를 계산합니다.
- strict benchmark 결과의 `row_comparison.csv`에는 `__det_profile`, `__det_gt_service_coverage`, `__det_gt_receiver_coverage`, `__det_dataflow_score`, `__det_numeric_grounding`, `__det_enum_grounding` 컬럼이 추가됩니다.

DET legacy/strict 비교 분석:

```bash
python gpt_mg/version0_15_update20260413/scripts/audit_det.py \
  --results-dir gpt_mg/version0_15_update20260413/results/model_suite_20260423_142658 \
  --results-dir gpt_mg/version0_15_update20260413/results/model_suite_20260423_143911 \
  --out-dir gpt_mg/version0_15_update20260413/results/det_profile_analysis_current \
  --print-json
```
- `--llm-mode mock`을 주면 실제 모델 로딩 없이 결과 파일 구조나 category filter 동작을 smoke test할 수 있습니다.
- `paper_with_cloud_ref`에서 `GPT-4.1-mini`를 쓰려면 `--llm-mode openai`와 `--llm-endpoint` 또는 관련 env 설정이 필요합니다.
- `local_model_name`을 직접 줄 때는 placeholder가 아니라 실제 snapshot 절대경로를 써야 합니다.
- `export_paper_figures.py`는 `category_summary.csv`가 있으면 category별 `DET vs warm latency`, `DET vs prompt tokens`, category metric panel figure까지 함께 생성합니다.
- `--limit`은 전체 selected rows에 대한 global cap이고, `--limit-per-category`는 category별 cap입니다.

## 주의할 점

- `demo.py`에서는 `connected_devices == {}` 요청이 마지막 요청 재사용으로 동작합니다.
- 반대로 `version0_15/scripts/*`에서는 `connected_devices == {}` 가 기본적으로 schema fallback이고, retrieval pre-mapping을 명시적으로 켰을 때만 retrieval shortlist가 우선됩니다.
- 즉 API 테스트와 benchmark/GA 스크립트는 빈 `connected_devices`의 의미가 다릅니다.
