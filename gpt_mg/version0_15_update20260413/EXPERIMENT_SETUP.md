# EXPERIMENT_SETUP

`version0_15_update20260413`에서 같은 prompt를 유지한 채 paper local suite를 공정하게 비교하는 실험 절차를 정리합니다.

## 1. 핵심 원칙

- runtime은 기본적으로 `Ollama`가 아니라 Hugging Face cache + local worker입니다.
- same-prompt benchmarking이 중심입니다.
- latency 공정 비교는 여러 모델을 동시에 VRAM에 올린 상태로 하지 않습니다.
- 권장 비교 축:
  - `DET`
  - `warm latency`
  - `cold load time`
  - `prompt tokens`
  - `peak VRAM`
  - `OOM/failure rate`

## 1-A. Final Paper Study Stages

최종 논문용 실행은 `scripts/run_paper_full_study.py`가 stage 단위로 orchestration합니다.

1. unit-level validation
2. dry-run validation
3. one-row smoke test
4. small category subset test
5. small GA generation smoke test
6. two-model Qwen 7B/14B reproducible subset
7. full five-model long run
8. artifact export

각 stage는 `results/paper_study_<timestamp>/stage_status/*.json`에 상태를 남깁니다. `--resume`을 사용하면 완료된 stage를 건너뛰고, 기본적으로 timestamped result directory를 새로 만들기 때문에 이전 실험을 덮어쓰지 않습니다.

### Paper Variants

- `B0`: manually designed local baseline. 없으면 `N/A`이며 숫자를 만들지 않습니다.
- `B1`: GPT-4.1-mini cloud reference.
- `B2`: direct cloud-to-local transfer.
- `B3`: fixed block without GA.
- `B4`: random search over the same block space.
- `B5`: GA + benchmark supervision only.
- `B6`: full GPS / PromptOps with deterministic validation, replay feedback, and regression-aware acceptance.

### Fixed Retrieval Scope

Retrieval pre-mapping은 실험 조건의 fixed runtime context입니다. GA는 retrieval mechanism을 mutation하지 않습니다. 비교 공정성을 위해 B2/B3/B4/B5/B6 모두 같은 retrieval policy를 사용해야 합니다.

### GA Fitness and Feedback

Legacy GA selection signal은 `fitness = AvgDET - alpha * VarDET`입니다. token/latency는 legacy fitness에 직접 들어가지 않으며, 최종 deployment comparison에서 별도로 보고합니다.

Redesigned GA selection is opt-in and is enabled with:

- `--selection-mode redesign`
- `--fitness-mode phase_aware`
- `--mutation-mode cloudless_decompiler`
- `--stop-controller-mode active`
- `--enable-pareto-archive`
- `--token-penalty-mode budget|accepted|hybrid`

In redesigned mode, DETPass is the primary objective. AvgDET/SDET is a secondary tie-breaker, and token penalty/compression gain are used conservatively so one validation-row DETPass loss is not outweighed by small token savings. The run records both raw generation best and best-so-far DETPass.

New redesign artifacts:

- `mutation_proposals.jsonl` and `mutation_proposals.csv`
- `cloudless_prompt_units.jsonl`
- `mutation_operator_credit.csv`
- `pareto_archive.csv` and `pareto_archive.jsonl`
- extended `ga_generation_progress.csv`
- extended `ga_topk_genomes.csv`
- extended `population_transitions.csv`

The active stop controller records `generation_phase`, `plateau_type`, `next_action`, and `stop_reason`. Plateau is treated as a signal for robustness, compression, diversity, or finalization rather than only as passive early stopping.

Prompt artifact genotype은 core block과 optional guidance block으로 나뉩니다.

- Core blocks: `01`, `02`
- Optional guidance blocks: `03`, `05`, `06`

Core blocks는 항상 포함됩니다. Optional guidance blocks는 GA가 activation/deactivation/replacement 대상으로 삼을 수 있습니다. `blocks=[...]`는 active prompt-block IDs를 뜻하며, cloud prompt를 임의 fragment로 잘라 쓴다는 의미가 아닙니다.

`utils/prompt_surgery_rules.py`는 `version0_13`의 수동 DET prompt repair 지식을 v15 GA용 deterministic feedback mapping으로 정리합니다.

- `invalid_json`: Output_Schema / JSON-only 강화
- `unknown_service`: Service_Mapping / canonical service name 강화
- `arg_type`, `enum_grounding`: Enum_Grounding / enum-type grounding 강화
- `numeric_grounding`, `temporal_error`: Temporal_Rule / elapsed-time, unit grounding 강화
- `gt_receiver_coverage`: Owner_Device_Rule / receiver binding 강화
- `dataflow`: Dataflow / sensor-to-action flow 강화
- `extraneous`: Minimality / no-unrelated-action 강화

Optional LLM mutation advisor:

- `--llm-mutation-advisor`를 켜면 population-level diagnostics를 보고 prompt-block mutation proposal만 생성합니다.
- Advisor는 JOILang code를 생성하지 않고, retrieval pre-mapping/top-k/service context를 변경하지 않습니다.
- Advisor proposal은 다음 세대 child genome으로 들어가며 일반 deterministic validation과 promotion gate를 통과해야 합니다.

### Small-To-Large GA Execution

`run_ga_search.py`는 full long run을 기본으로 시작하지 않습니다.

- Stage flag가 없고 `--full-run`도 없으면 safe dry-run으로 동작합니다.
- `--dry-run`: model call 없이 CLI, dataset/category selection, genome, block split, output path를 검증합니다.
- `--smoke`: one-row smoke. population/gens/candidate_k가 안전 범위로 cap됩니다.
- `--small-category-smoke`: category `1,2`, `limit_per_category<=2`로 category diagnostics와 failure histogram을 검증합니다.
- `--small-ga-advisor-smoke`: advisor path를 켜고 endpoint가 없으면 mock advisor JSON으로 schema/proposal safety를 검증합니다.
- `--full-run`: uncapped long run 허용. days-scale 실행은 이 flag가 필요합니다.
- `--resume` / `--force`: 기존 output directory에 이어 쓰거나 강제 쓰기 할 때만 사용합니다.

Structured deterministic feedback은 다음 파일에 저장됩니다.

- `results/paper_study_<timestamp>/structured_feedback.jsonl`
- `results/paper_study_<timestamp>/structured_feedback_summary.csv`

GA 단독 실행에서는 아래 파일에 저장됩니다.

- `results/ga_search_<timestamp>/structured_feedback.jsonl`
- `results/ga_search_<timestamp>/structured_feedback_summary.csv`
- `results/ga_search_<timestamp>/ga_block_diffs.jsonl`
- `results/ga_search_<timestamp>/ga_population_diagnostics.csv`
- `results/ga_search_<timestamp>/advisor_mutation_proposals.jsonl`
- `results/ga_search_<timestamp>/advisor_mutation_summary.csv`
- `results/ga_search_<timestamp>/population_transitions.csv`

Replay cases는 `ReplayAcc` main leaderboard column이 아니라 `ReplayFit` 또는 `replay_gate_pass` 형태의 feedback/acceptance 조건입니다.

### Acceptance Gate Semantics

- Candidate prompt는 생성됩니다.
- Candidate prompt는 benchmark/replay/regression으로 평가됩니다.
- Gate를 실패하면 promotion만 거절됩니다.
- 이전 accepted prompt는 계속 active 상태로 유지됩니다.
- rejection reason은 promotion artifact에 저장됩니다.

## 2. cold vs warm 정의

- `cold_load_sec`
  - fresh worker에서 warmup 첫 요청에 걸린 시간
  - worker start + model load + 첫 요청 setup이 포함된 cold-start 지표
- `warm_latency_mean/p50/p95`
  - warmup 이후 evaluation rows만 기준
  - 같은 모델이 이미 메모리에 올라간 상태에서의 row-level LLM latency

## 3. prompt token 측정 방식

- `prompt_tokens`는 각 모델 tokenizer 기준으로 계산됩니다.
- 같은 문자열 prompt라도 모델마다 token 수가 다를 수 있습니다.
- row-level `prompt_tokens`는 그 row를 처리하는 동안 사용된 LLM call들의 총합입니다.
  - `candidate_k=1`, `repair_attempts=0`이면 사실상 단일 generation call과 같습니다.
  - `candidate_k>1` 또는 repair가 있으면 pipeline 전체 token cost가 합산됩니다.
- `--limit`은 전체 selected rows에 대한 global cap이고, `--limit-per-category`는 category별 balanced cap입니다.

## 4. VRAM / OOM 측정 방식

- worker가 `torch.cuda.max_memory_allocated` 기반 peak VRAM을 반환합니다.
- row-level `peak_vram_gb`는 그 row 처리 중 관찰된 최대값입니다.
- summary의 `peak_vram_gb_max`는 모델 전체 row 중 최대값입니다.
- OOM은 `cuda_oom`으로 분류됩니다.

주요 generation failure taxonomy:

- `cuda_oom`
- `cpu_fallback_timeout`
- `invalid_json`
- `worker_crash`
- `gated_model`
- `missing_cache`
- `incompatible_runtime`
- `local_llm_error`

## 5. 권장 환경 변수

```bash
cd /home/mgjeong/Desktop/llm/JOILang-Server

export JOI_V15_WORKER_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
export JOI_V15_LOCAL_DEVICE=cuda:0
```

## 6. paper_local5 model key

- `phi35_mini`
- `qwen25_coder_7b`
- `llama31_8b`
- `gemma2_9b_it`
- `qwen25_coder_14b`

현재 바로 같은 prompt compare까지 확인된 runnable subset:

- `qwen25_coder_7b`
- `qwen25_coder_14b`

## 7. 가장 먼저 할 점검

preflight:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --preflight-only \
  --print-worker-info
```

model preparation:

```bash
python gpt_mg/version0_15_update20260413/scripts/prepare_local_models.py \
  --suite paper_local5 \
  --download-missing
```

## 8. 실행 예시

single row:

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

row range:

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

specific category:

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
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
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
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --list-categories
```

full dataset:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --candidate-k 1 \
  --repair-attempts 0 \
  --print-mode summary
```

fair latency mode:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
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

explicit warmup control:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
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

wall-clock-oriented parallel mode:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
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

주의:

- 이 parallel 모드는 wall-clock 단축용입니다.
- fair latency 비교용 결과로 쓰면 안 됩니다.

export-paper-artifacts:

```bash
python gpt_mg/version0_15_update20260413/scripts/run_model_suite_benchmark.py \
  --suite paper_local5 \
  --model-key qwen25_coder_7b \
  --model-key qwen25_coder_14b \
  --row-no 1 \
  --candidate-k 1 \
  --repair-attempts 0 \
  --paper-fair-mode \
  --export-paper-artifacts \
  --print-mode summary
```

standalone figure export:

```bash
python gpt_mg/version0_15_update20260413/scripts/export_paper_figures.py \
  --results-dir /home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_15_update20260413/results/model_suite_20260421_121042
```

## 9. compare mode에서 보는 정보

`--print-mode compare`는 row마다 아래를 출력합니다.

- row id
- input command
- category
- GT code
- generated code
- DET score
- det pass / exact / similarity
- failure reasons
- prompt tokens
- llm latency
- peak VRAM
- concise diff summary

## 10. 결과 파일

기본 benchmark output:

- `suite_manifest.json`
- `suite_summary.json`
- `suite_summary.csv`
- `row_comparison.csv`
- `failure_reason_summary.csv`
- `generation_error_summary.csv`
- `category_summary.csv`
- `category_model_comparison.csv`
- `latency_breakdown.csv`
- `main_model_comparison.csv`
- `tradeoff_summary.csv`
- `latency_summary.csv`
- `vram_summary.csv`
- `tokenizer_summary.csv`
- `paper_metrics_summary.json`

모델별 raw outputs:

- `*_candidates.csv`
- `*_rerank.csv`
- `*_summary.json`
- fair mode일 때 `*_warmup_candidates.csv`
- fair mode일 때 `*_warmup_summary.json`

figure export:

- `paper_figures/det_vs_warm_latency.png`
- `paper_figures/det_vs_warm_latency.pdf`
- `paper_figures/det_vs_prompt_tokens.png`
- `paper_figures/det_vs_prompt_tokens.pdf`
- `paper_figures/det_vs_peak_vram.png`
- `paper_figures/paper_summary_bars.png`
- `paper_figures/category_det_vs_warm_latency.png`
- `paper_figures/category_det_vs_warm_latency.pdf`
- `paper_figures/category_det_vs_prompt_tokens.png`
- `paper_figures/category_det_vs_prompt_tokens.pdf`
- `paper_figures/category_metric_panels.png`
- `paper_figures/category_metric_panels.pdf`
- `paper_figures/paper_figures_summary.json`

카테고리 figure 참고:

- `category_summary.csv`가 존재하면 category별 trade-off figure가 같이 생성됩니다.
- `category_det_vs_warm_latency.*`
  - category별 subplot에서 모델 간 `DET vs warm latency`를 비교합니다.
- `category_det_vs_prompt_tokens.*`
  - category별 subplot에서 모델 간 `DET vs prompt tokens`를 비교합니다.
- `category_metric_panels.*`
  - category별 `avg_det_score`, `det_pass_rate`, `warm_latency_p50`, `avg_prompt_tokens`를 grouped bar로 비교합니다.

## 11. 지금 기준 추천 실험 순서

1. `--preflight-only`로 cache/runtime을 확인합니다.
2. `prepare_local_models.py --download-missing`로 local suite 준비 상태를 업데이트합니다.
3. `candidate-k=1`, `repair-attempts=0`으로 raw same-prompt transfer를 먼저 봅니다.
4. `--paper-fair-mode`로 cold/warm/prompt/VRAM 축을 같이 수집합니다.
5. 필요한 경우 repair를 켠 pipeline utility 비교를 별도 실험으로 분리합니다.

## 12. 알려진 제한사항

- `phi35_mini`는 현재 row 1 schema fallback prompt에서 OOM이 발생할 수 있습니다.
- `llama31_8b`, `gemma2_9b_it`는 Hugging Face gated access가 필요합니다.
- benchmark는 기본적으로 HF cache + worker를 사용하므로 Ollama 상태와 직접 연결되지 않습니다.
- `paper_local5` 정의와 “현재 즉시 runnable subset”은 다를 수 있습니다.
