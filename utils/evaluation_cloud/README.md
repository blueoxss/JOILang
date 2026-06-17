# JOI Lang Cloud Semantic Evaluation

`utils/evaluation_cloud` is the auxiliary cloud semantic judge layer for JOI Lang evaluation. It does not replace the official strict DET benchmark.

## Roles

- Official strict DET benchmark: `gpt_mg/version0_15_update20260413/scripts/run_benchmark.py`
- Strict DET post-processing: `utils/export_local_det_failure_report.py`
- Auxiliary cloud semantic judges: `utils/evaluation_cloud/main_evaluator.py lang/gpt`
- Official rich feedback merge: `utils/merge_strict_det_with_cloud_judges.py`

`main_evaluator.py det` and `main_evaluator.py hybrid` are legacy/debug/backward compatibility modes. `hybrid` expands internally to `det+lang+gpt`, but official rich feedback does not use that legacy DET score. The official adapter reads strict DET artifacts and cloud judge CSVs independently.

## Environment

API keys must live only in the shell environment, not in repository files.

```bash
source ~/.bashrc
python - <<'PY'
import os
print("OPENAI_API_KEY set:", bool(os.environ.get("OPENAI_API_KEY")))
print("JOI_V15_OPENAI_API_KEY set:", bool(os.environ.get("JOI_V15_OPENAI_API_KEY")))
print("LANGSMITH_TRACING:", os.environ.get("LANGSMITH_TRACING"))
print("LANGCHAIN_TRACING_V2:", os.environ.get("LANGCHAIN_TRACING_V2"))
PY
```

OpenAI-compatible judge calls require one of:

- `OPENAI_API_KEY`
- `JOI_EVAL_OPENAI_API_KEY`
- `JOI_V15_OPENAI_API_KEY`

LangSmith/LangChain keys are optional and only needed when tracing/logging is explicitly enabled. With `LANGSMITH_TRACING=false` and `LANGCHAIN_TRACING_V2=false`, the local `lang` and `gpt` judges do not require a LangSmith key.

## Cloud Semantic Judges

The actual entrypoint is:

```bash
cd utils/evaluation_cloud
python main_evaluator.py lang joi 66 version0_13
python main_evaluator.py gpt joi 66 version0_13
python main_evaluator.py lang gpt joi 66 version0_13
EVAL_LIMIT=50 python main_evaluator.py lang gpt
```

Supported families are `joi`, `cap`, and `qwen`.

`lang` runs a local CLI multi-criteria semantic judge through ChatOpenAI/LangChain. It is not the older LangSmith server `run_on_dataset` workflow. Expected result CSV columns include:

- `overall_lang`
- `ls_semantic_intent`
- `ls_conditions`
- `ls_time_period`
- `ls_device_service`
- `ls_judge_reasoning`

`gpt` runs a custom GPT holistic semantic similarity judge between GT and candidate code. When valid GT code is unavailable, it can use a reconverted Korean instruction fallback. Expected result CSV columns include:

- `overall_gpt`
- `gpt_judge_reasoning`
- `gpt_reconverted_reference_sentence`
- `gpt_reconverted_sentence`
- `gpt_reconverted_same`
- `gpt_reconverted_score`
- `gpt_reconverted_reasoning`

The default output remains `result_<model>.csv` in the current directory. You can keep cloud judge reports separate with:

```bash
python main_evaluator.py lang gpt joi version0_13 --out-dir results
```

These CSVs are auxiliary semantic diagnostic reports. They are not official benchmark scores and are intended as adapter input.

## Strict DET Report

The official strict DET artifacts are produced outside this directory:

```bash
python utils/export_local_det_failure_report.py \
  --results-dir gpt_mg/version0_15_update20260413/results/model_suite_YYYYMMDD_HHMMSS \
  --model-key gpt41_mini
```

The adapter expects the strict results directory to already contain:

- `row_comparison.csv`
- `failure_reason_summary.csv`
- `local_det_failure_report.json`

If `local_det_failure_report.json` is missing, the adapter prints the command above and exits. It does not generate strict DET reports automatically.

## Rich Feedback Adapter

Run the adapter from the repository root after both independent reports exist:

```bash
cd ../..
python utils/merge_strict_det_with_cloud_judges.py \
  --strict-results-dir gpt_mg/version0_15_update20260413/results/model_suite_YYYYMMDD_HHMMSS \
  --cloud-judge-csv utils/evaluation_cloud/result_gpt_mg_version0_13.csv \
  --model-key gpt41_mini \
  --out-dir artifacts/hybrid_strict_cloud_v13
```

Outputs:

- `advisor_rich_feedback.json`
- `hybrid_strict_cloud_report.csv`
- `hybrid_strict_cloud_report.md`

The adapter preserves separation of concerns:

- It reads strict DET artifacts only.
- It reads cloud semantic judge CSVs only.
- It does not rerun strict DET.
- It does not overwrite either input report.
- It records `joined_rows`, `strict_only_rows`, and `cloud_only_rows` when only part of the rows join.

## Interpretation

Strict DET is the reproducible official benchmark metric. Cloud judge scores are auxiliary semantic diagnostic signals. `advisor_rich_feedback.json` is intended for prompt mutation/advisor analysis, not as a replacement official benchmark score.
