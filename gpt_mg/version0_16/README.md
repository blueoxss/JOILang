# JOILang PromptOps v0.16 Dynamic Atomic Block Space

`gpt_mg.version0_16` is a versioned prompt/model package for generation-dynamic atomic prompt block-space GA search.

The canonical prompt source is:

```text
gpt_mg/version0_16/prompts/source/merged_system_prompt_260413.md
```

The files under `blocks/generated/g*/` are generated segmentation outputs, not the permanent source of truth.

## Why This Is Not v15 Blocks

`version0_15_update20260413` uses a small set of coarse prompt blocks such as generator, repair, reranker, and DET helper blocks. Those blocks are useful as a baseline, but they do not expose JOILang grammar, output schema, service grounding, receiver grounding, temporal policy, loop constraints, dataflow, numeric/enum grounding, and repair policy as independent GA genes.

`version0_16` represents those concepts as generation-local semantic atoms. Numeric IDs like `00` or `06` are local to one block-space manifest and must not be used as permanent identifiers.

## Dynamic Invariant

The stable cross-generation identity metadata is:

- `semantic_family`
- `semantic_role`
- `behavior_tags`
- `content_hash`
- `source_span`
- `lineage`
- `failure_targets`

The unstable generation-local metadata is:

- `local_id`
- generated block filename
- atom count

The seed generation `g000` currently has 26 atoms only because it is a deterministic seed segmentation. The fixture generation `g001` has 16 atoms and demonstrates that rendering and patch resolution do not depend on a fixed 26-block taxonomy.

## Runtime

The canonical runtime is:

```text
utils/
utils/ga_search/
utils/det_evaluator.py
```

`gpt_mg/version0_15_update20260413/scripts` is not used as a runtime dependency for `version0_16`.

## Main Files

- `config_loader.py`: package loader compatible with `utils.ga_search.render_adapter`.
- `model_config.json`: metadata and local-worker defaults.
- `tools/prompt_decompiler.py`: deterministic seed/g001 segmentation generator.
- `tools/block_space_ops.py`: manifest/genome validation, rendering, dynamic operations, failure mapping, and dynamic patch resolution.
- `tools/dynamic_patch_adapter.py`: command-line adapter for old advisor patch artifacts.
- `tools/smoke_check.py`: local static/dynamic assertions for v16.
- `registries/generation_block_space_g000.json`: generation-0 seed manifest.
- `registries/generation_block_space_g001.json`: non-seed fixture manifest with a different atom count.
- `genomes/base_genome_g000.json`, `genomes/base_genome_g001.json`: base genomes referencing generation-local atom IDs.

## Old Notebook Compatibility

The `01_cloudless_det_feedback_ga_search` notebook can still produce evidence and advisor patch artifacts such as `advisor_prompt_patches.json`, but fixed `target_block_id` values are only fallback hints in v16.

Patch application must flow through semantic resolution:

```text
old fixed block patch
  -> dynamic_patch_adapter
  -> current generation manifest
  -> semantic_family / behavior_tags / lineage / failure_targets scoring
  -> atom-level micro-rule, rewrite, or explicit create_new_atom
```

Silent fallback to a generic fixed block such as `06` is forbidden and recorded as `silent_fallback_count = 0`.

## Supported Dynamic Operations

The architecture exposes hooks for:

```text
activate_atom
deactivate_atom
rewrite_atom
replace_atom_variant
split_atom
merge_atoms
relabel_atom
reorder_atoms
promote_required
demote_optional
attach_micro_rule
remove_micro_rule
create_new_atom
retire_atom
```

The first implementation is deterministic/heuristic, but the manifest and genome schema are designed so later GA generations can split, merge, relabel, retire, or create atoms without changing old baselines.

## Quick Checks

Use the JOILang Python environment:

```bash
JOI_PY=/root/llm/je/bin/python JOI_GA_MODEL=gpt_mg.version0_16 /root/llm/je/bin/python -m gpt_mg.version0_16.tools.smoke_check
```

Render through the canonical runtime:

```bash
JOI_PY=/root/llm/je/bin/python JOI_GA_MODEL=gpt_mg.version0_16 /root/llm/je/bin/python -m utils.ga_search.cli render \
  --model gpt_mg.version0_16 \
  --user-input "Turn on the light." \
  --search-mode auto \
  --dry-run
```
