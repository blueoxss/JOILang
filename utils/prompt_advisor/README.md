# Prompt Advisor

`utils/prompt_advisor` turns rich benchmark feedback into prompt mutation candidates. It does not edit prompt block files directly and it does not generate JOILang code.

## Role

- `advisor_rich_feedback.json` is the evidence input from the strict DET + cloud semantic adapter.
- `build_advisor_prompt.py` compresses that evidence into a small Feedback Advisor prompt.
- `run_feedback_advisor.py` creates `prompt_patches.json`.
- `apply_prompt_patches.py` expands `prompt_patches.json` into diverse candidate genomes.

Strict DET remains the official benchmark metric. Cloud judge scores remain auxiliary diagnostic signals only.

## Build Advisor Prompt

```bash
python utils/prompt_advisor/build_advisor_prompt.py \
  --advisor-rich-feedback artifacts/hybrid_strict_cloud_test/advisor_rich_feedback.json \
  --prompt-version version0_13 \
  --model-key gpt41_mini \
  --out artifacts/prompt_advisor_test/advisor_prompt.json \
  --top-rows 20 \
  --representatives-per-cluster 3
```

The builder keeps strict DET failure reasons, concrete diagnostics, component scores, and recommended mutations as primary evidence. Lang/GPT reasoning is compressed as auxiliary explanation.

## Dry Run

Dry-run does not call any API. It writes a deterministic local `prompt_patches.json` preview that can be used for population smoke tests.

```bash
python utils/prompt_advisor/run_feedback_advisor.py \
  --advisor-prompt artifacts/prompt_advisor_test/advisor_prompt.json \
  --out artifacts/prompt_advisor_test/prompt_patches.json \
  --dry-run
```

## API Mode

API mode calls an OpenAI-compatible chat completion endpoint and expects JSON only.

```bash
python utils/prompt_advisor/run_feedback_advisor.py \
  --advisor-prompt artifacts/prompt_advisor_test/advisor_prompt.json \
  --out artifacts/prompt_advisor_test/prompt_patches.json \
  --model gpt-4.1-mini \
  --temperature 0
```

Keys are read only from environment variables:

- `OPENAI_API_KEY`
- `JOI_EVAL_OPENAI_API_KEY`
- `JOI_V15_OPENAI_API_KEY`

`OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`.

## Build Population

```bash
python utils/prompt_advisor/apply_prompt_patches.py \
  --prompt-patches artifacts/prompt_advisor_test/prompt_patches.json \
  --base-genome gpt_mg/version0_15_update20260413/genomes/base.json \
  --out-dir artifacts/prompt_advisor_test/population \
  --population-size 12
```

If `--base-genome` is missing or the path does not exist, a compatible fallback genome is used:

```json
{
  "blocks": ["01", "02", "03", "06"],
  "params": {},
  "block_params": {},
  "seed": 0
}
```

Outputs:

- `prompt_patches.normalized.json`
- `mutation_population.json`
- `mutation_population.csv`
- `mutation_population.md`
- `genomes/*.json`

The generated population is intended for GA evaluation. Candidate genomes vary by mutation intent: single patch attribution, cluster-focused repair, balanced repair, conservative low-risk repair, aggressive repair, and diversity branches.

## Validation

After population generation, rerun strict DET on selected candidate genomes through the existing benchmark/GA path that supports `--genome-json`. Cloud semantic judges can be rerun afterward as auxiliary explanation, not as the official benchmark score.

