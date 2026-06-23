# GA Search

`utils/ga_search` is the canonical repository-level runtime for JOILang prompt rendering, strict DET evaluation, GA search scaffolding, candidate generation, and advisor seed artifacts.

Execution logic lives here, not inside model packages. Model packages provide prompt assets such as `config_loader.py`, `model_config.json`, `blocks/`, and `genomes/`.

## Model Packages

Both dotted modules and filesystem paths are supported:

```bash
python -m utils.ga_search.cli render --model gpt_mg.version0_13 --user-input "Turn on the light." --dry-run
python -m utils.ga_search.cli render --model gpt_cap.stage_2 --user-input "Turn on the light." --dry-run
python -m utils.ga_search.cli render --model-package gpt_mg/version0_13 --user-input "Turn on the light." --dry-run
```

The resolver rejects the legacy v15 update folder as a canonical runtime dependency. That folder may remain as backup/reference material, but `utils/ga_search` must not import it.

## Strict DET Policy

- Official ground truth column: `gt`
- `gt_raw` is not used for official evaluation.
- Strict DET is the official metric.
- Cloud semantic judge and cloud advisor output are auxiliary diagnostics only.

## Render

```bash
python -m utils.ga_search.cli render \
  --model gpt_mg.version0_13 \
  --user-input "Turn on the light." \
  --dry-run
```

## Eval

Mock eval uses the official `gt` field as a deterministic candidate fixture. It is intended for pipeline health checks, not model quality claims.

```bash
python -m utils.ga_search.cli eval \
  --model gpt_mg.version0_13 \
  --dataset datasets/JOICommands-280.csv \
  --row-no 1 \
  --llm-mode mock \
  --det-profile strict
```

Outputs include:

- `candidates/generation_000.csv`
- `eval/row_evaluation.csv`
- `eval/failure_reason_summary.csv`
- `eval/category_summary.csv`
- `eval/summary.json`

Real candidate generation modes are also wired:

- `--llm-mode worker`: subprocess local worker using the rendered package's `model_input.local_worker` or `JOI_GA_WORKER_PATH`.
- `--llm-mode local`: OpenAI-compatible local HTTP endpoint, defaulting to `JOI_GA_LOCAL_ENDPOINT` or `http://127.0.0.1:8000/v1/chat/completions`.
- `--llm-mode openai`: OpenAI SDK with `OPENAI_API_KEY`, `JOI_EVAL_OPENAI_API_KEY`, or `JOI_V15_OPENAI_API_KEY`.

If a backend is unavailable, canonical eval writes explicit generation error fields and returns a non-zero status. It never falls back to mock candidates silently.

## Search

The search command preserves the deterministic mock foundation and adds a real-generation skeleton. With `--llm-mode mock`, `--engine-mode auto` runs the mock foundation. With `--llm-mode worker|local|openai`, `--engine-mode auto` runs the real skeleton:

- initialize/evaluate a population;
- compute strict DET fitness;
- select/promote the best genome;
- create mutation events for the next generation;
- record `ga_generation_progress.csv`, `mutation_events.*`, `promotion_decisions.*`, `best_genome.json`, and `ga_summary.json`.

This is not full parity with older model-package-local GA operators yet; `ga_summary.json` records known limitations when advanced hooks are only scheduled.

```bash
python -m utils.ga_search.cli search \
  --model gpt_mg.version0_13 \
  --dataset datasets/JOICommands-280.csv \
  --category 5 \
  --limit-per-category 1 \
  --population 2 \
  --gens 1 \
  --llm-mode mock \
  --det-profile strict
```

Outputs include:

- `genomes/initial_population.json`
- `genomes/generation_*.json`
- `best_genome.json`
- `ga_summary.json`
- `ga_generation_progress.csv`
- `ga_block_diffs.jsonl`

Useful real-mode flags:

```bash
python -m utils.ga_search.cli search \
  --model gpt_mg.version0_13 \
  --dataset datasets/JOICommands-280.csv \
  --row-no 1 \
  --llm-mode worker \
  --engine-mode auto \
  --timeout-sec 1800 \
  --retries 0
```

Prompt patches can be applied without editing prompt source files:

```bash
python -m utils.ga_search.prompt_patch_apply \
  --prompt-patches artifacts/prompt_advisor_test/prompt_patches.json \
  --out-dir artifacts/ga_search/patch_apply_test
```

The search CLI also accepts `--prompt-patches` and writes `patch_application/` with `patched_genome.json`, `patch_application_report.json`, and `patch_diff.md`.

## Advisor

Advisor modes remain separate from official DET scoring:

- `local`: strict DET/local report evidence
- `cloud`: cloud judge CSV as auxiliary semantic evidence
- `hybrid`: strict DET primary plus cloud reasoning auxiliary

Dry-run advisor creates deterministic `prompt_patches.json` and mutation population artifacts without API calls.

Advisor checks require real artifacts:

```bash
python -m utils.ga_search.cli check \
  --check advisor_transport_smoke \
  --advisor-dir artifacts/some_run/advisor

python -m utils.ga_search.cli check \
  --check advisor_effectiveness_smoke \
  --advisor-dir artifacts/some_run/advisor
```

They do not report `PASS` unless prompt patches, mutation population, accepted proposal count, scheduled child count, and advisor-backed diff evidence are present.

## Check Scripts

```bash
./run_eval_pipeline_check.sh smoke2
./run_ga_search_check.sh smoke
```

Both scripts route through `python -m utils.ga_search.cli`.
