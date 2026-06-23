# JOILang GA Search Tutorial Notebooks

These files are the canonical tutorial files for `tutorial/`.

They replace/update:

- `tutorial/01_cloudless_det_feedback_ga_search.ipynb`
- `tutorial/02_cloud_only_feedback_ga_search.ipynb`
- `tutorial/03_merged_feedback_ga_search.ipynb`
- `tutorial/JOILang_GA_Notebook_README.md`

## Canonical runtime

All notebooks use only the repository-level canonical runtime:

```bash
python -m utils.ga_search.cli
```

They do **not** call:

```bash
gpt_mg/version0_15_update20260413/scripts/run_ga_search.py
gpt_mg/version0_15_update20260413/scripts/run_benchmark.py
gpt_mg/version0_15_update20260413/scripts/run_feedback_loop.py
```

The `gpt_mg/version0_15_update20260413` package is backup/reference only and should not be required.

## Tutorial files

### 01_cloudless_det_feedback_ga_search.ipynb

Use this first.

It checks:

- canonical import origin;
- `python -m compileall utils`;
- render smoke;
- strict DET eval using official `gt`;
- `engine-mode=mock` foundation path;
- `engine-mode=real` + `llm-mode=local` unavailable honesty test;
- optional worker real row smoke;
- prompt patch application;
- patch visibility;
- prompt logs/raw response paths.

### 02_cloud_only_feedback_ga_search.ipynb

Use this after the cloudless notebook.

It checks:

- strict DET evidence generation;
- cloud/hybrid advisor dry-run artifacts;
- advisor transport/effectiveness checks with artifacts;
- advisor-generated prompt patches;
- patch-applied search;
- optional OpenAI smoke.

### 03_merged_feedback_ga_search.ipynb

Use this after 01 and 02.

It checks:

- strict DET primary signal;
- cloud/advisor auxiliary evidence;
- baseline vs hybrid-patched search;
- advisor effectiveness via `--run-dir`;
- prompt patch report;
- optional worker real comparison.

## Required policy

- Official ground truth column: `gt`
- `gt_raw` is not used as official evaluation GT.
- Official metric: strict DET
- Cloud/advisor feedback: auxiliary only
- `llm-mode=mock`: deterministic smoke/foundation path
- `llm-mode=worker|local|openai`: real generation or explicit failure, never silent mock fallback

## Recommended smoke commands

```bash
cd /root/llm/JOILang-Server

python -m compileall utils

./run_eval_pipeline_check.sh smoke2 /root/llm/JOILang-Server
./run_ga_search_check.sh smoke /root/llm/JOILang-Server
```

## Optional worker configuration

For real local worker smoke, set the worker path and model path:

```bash
export JOI_GA_MODEL=gpt_mg.version0_13
export MODEL_KEY=qwen25_coder_14b
export JOI_GA_WORKER_PATH=gpt_mg/version0_13/qwen_local_worker.py
export JOI_GA_WORKER_PYTHON=/home/mgjeong/miniconda3/envs/l/bin/python
export JOI_GA_LOCAL_MODEL_NAME=/home/mgjeong/Desktop/llm/local_models/qwen25_coder_14b
export JOI_GA_LOCAL_DEVICE=cuda:0
```

Then enable `RUN_WORKER_REAL = True` inside the relevant notebook cell.

## Optional OpenAI configuration

For OpenAI smoke, set your endpoint/API key according to the current `utils.ga_search.llm_backends` implementation and then enable:

```python
RUN_OPENAI_SMOKE = True
```

inside `02_cloud_only_feedback_ga_search.ipynb`.

## Interpretation

The notebooks are designed to separate:

1. canonical runtime health;
2. mock deterministic artifact validation;
3. explicit non-mock failure behavior;
4. real worker/openai generation when environment is ready;
5. advisor artifact and patch visibility checks.

A PASS in mock mode confirms the pipeline and artifact structure, not model quality.
