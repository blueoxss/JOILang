# GA Search

`utils/ga_search` is the canonical repository-level runtime for JOILang prompt rendering, strict DET evaluation, smoke GA search, and advisor seed artifacts.

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

## Search

The current search command provides a lightweight smoke GA loop with population/generation artifacts. It is designed to validate the new repository-level execution path before migrating heavier optimization operators.

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

## Advisor

Advisor modes remain separate from official DET scoring:

- `local`: strict DET/local report evidence
- `cloud`: cloud judge CSV as auxiliary semantic evidence
- `hybrid`: strict DET primary plus cloud reasoning auxiliary

Dry-run advisor creates deterministic `prompt_patches.json` and mutation population artifacts without API calls.

## Check Scripts

```bash
./run_eval_pipeline_check.sh smoke2
./run_ga_search_check.sh smoke
```

Both scripts route through `python -m utils.ga_search.cli`.
