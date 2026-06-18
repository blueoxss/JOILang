# GA Search Foundation

`utils/ga_search` prepares repository-wide prompt search artifacts from a model package. It keeps service model folders focused on deployment-time prompt rendering and keeps GA/advisor/mutation artifacts outside model folders.

## Boundaries

- `model_config.json` may declare only `prompt_render`.
- GA search mode is a CLI option, not a model config setting.
- Gene, genome, population, mutation, advisor, and search-space artifacts are written under `artifacts/ga_search/`.
- `gpt_mg/version0_15_update20260413` remains a read-only legacy/reference workspace.
- Strict DET remains the official metric. Cloud semantic judges are auxiliary diagnostics only.

## Render And Search Modes

Model render mode comes from `model_config.json`:

```json
{
  "prompt_render": {
    "mode": "monolith",
    "loader": "config_loader.py",
    "loader_function": "load_version_config",
    "merged_prompt_output": "merged_system_prompt.md"
  }
}
```

GA search mode comes from CLI:

- `--search-mode monolith`: use the merged system prompt as the search input.
- `--search-mode blocks`: use provided block metadata if available; otherwise decompose the merged prompt into dynamic blocks.

Supported combinations:

| model render mode | GA search mode | behavior |
|---|---|---|
| monolith | monolith | use merged prompt |
| monolith | blocks | decompose merged prompt |
| blocks | monolith | use service-merged prompt |
| blocks | blocks | use blocks metadata, else decompose |

## Basic Smoke

```bash
python utils/ga_search/cli.py \
  --model-package gpt_mg/version0_16 \
  --search-mode monolith \
  --advisor-mode none \
  --user-input "Turn on the light." \
  --out-dir artifacts/ga_search/smoke_v16_monolith \
  --print-summary
```

```bash
python utils/ga_search/cli.py \
  --model-package gpt_mg/version0_16 \
  --search-mode blocks \
  --advisor-mode none \
  --user-input "Turn on the light." \
  --out-dir artifacts/ga_search/smoke_v16_blocks \
  --print-summary
```

Outputs:

- `rendered_base_prompt.md`
- `render_metadata.json`
- `decomposed_blocks.json` for blocks mode
- `search_input.json`
- `manifest.json`
- `candidates/candidates_manifest.json`

## Advisor Modes

`--advisor-mode local|cloud|hybrid` attaches feedback evidence and creates prompt mutation seed artifacts.

| mode | input | policy |
|---|---|---|
| local | `local_det_failure_report.json` | strict DET is primary |
| cloud | cloud judge CSV | auxiliary semantic diagnostics only |
| hybrid | `advisor_rich_feedback.json` or strict+cloud inputs | strict DET primary, cloud auxiliary |

Dry-run advisor does not call APIs. It deterministically maps evidence clusters to `prompt_patches.json`, then builds a seed mutation population and candidate manifest.

```bash
python utils/ga_search/cli.py \
  --model-package gpt_mg/version0_16 \
  --search-mode blocks \
  --advisor-mode hybrid \
  --advisor-rich-feedback artifacts/hybrid_strict_cloud_test/advisor_rich_feedback.json \
  --dry-run-advisor \
  --user-input "Turn on the light." \
  --out-dir artifacts/ga_search/smoke_advisor_hybrid \
  --print-summary
```

Advisor outputs:

- `advisor/advisor_mode.json`
- `advisor/advisor_evidence_packet.json`
- `advisor/advisor_prompt.json`
- `advisor/prompt_patches.json`
- `advisor/mutation_population.json`
- `advisor/mutation_population.csv`
- `advisor/mutation_population.md`
- `candidates/candidate_*.json`
- `candidates/candidates_manifest.json`

The advisor never writes final generation prompt files and never generates JOILang code. Its output is a mutation proposal for later GA evaluation. Validate improvement by rerunning strict DET first, then use cloud semantic judges only for diagnostic explanation.
