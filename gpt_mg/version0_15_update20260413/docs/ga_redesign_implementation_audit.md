# GA Redesign Implementation Audit

This audit was created before the GA redesign implementation work for `gpt_mg/version0_15_update20260413`.

## Source Documents Read

- `docs/joilang_ga_search_diagnostic_research_note.docx`
- `docs/redesign_report_ga_fitness_elite_selection.docx`
- `docs/redesign_report_cloudless_mutation_v3_v4.docx`
- `docs/redesign_report_generation_stop_condition.docx`

## Current Implementation Map

- Genomes are loaded in `scripts/run_ga_search.py` through `load_genome()` from `utils/pipeline_common.py`, then normalized by `validate_genome_blocks()` from `utils/ga_block_model.py`.
- Prompt blocks are rendered in `utils/pipeline_common.py` through `render_blocks_for_genome()` and `render_prompt_bundle()`.
- Core and optional block semantics live in `utils/ga_block_model.py`; core blocks are always normalized back into the genome.
- Random genome creation is in `scripts/run_ga_search.py::_random_genome()`.
- Mutation is currently applied in `scripts/run_ga_search.py::_mutate_genome()`.
- Crossover is currently applied in `scripts/run_ga_search.py::_crossover()`.
- Fitness is currently computed in `scripts/run_ga_search.py::_evaluate_one()` as `AvgDET - alpha * VarDET`.
- Population sorting currently happens in `scripts/run_ga_search.py::run_ga_search()` by `fitness`, then `validation_avg_det_score`, then genome id.
- Elite selection currently happens in `scripts/run_ga_search.py::run_ga_search()` by taking the top current-generation scalar-fitness genomes.
- Generation progress CSV is written in `scripts/run_ga_search.py::run_ga_search()` to `ga_generation_progress.csv`.
- Top-k genome CSV is written in `scripts/run_ga_search.py::run_ga_search()` to `ga_topk_genomes.csv`.
- Summary and best genome are written at the end of `scripts/run_ga_search.py::run_ga_search()` to `ga_summary.json`, `best_genome.json`, and `best_prompt_metadata.json`.
- Advisor proposal generation is handled by `_build_advisor_prompt()`, `_call_mutation_advisor()`, and `_safe_advisor_proposals()` in `scripts/run_ga_search.py`.
- DET feedback-guided mutation is mapped in `utils/ga_block_model.py` through `feedback_records_from_rows()`, `summarize_deterministic_feedback()`, and `suggest_mutation_from_feedback()`.
- Token counts are logged by generation helpers in `scripts/run_generate.py` as `generation_prompt_tokens_total`, then summarized in `scripts/run_ga_search.py::_avg_prompt_tokens()`.
- Category diagnostics are computed in `scripts/run_ga_search.py::_category_diagnostics()`.
- Stop/plateau logic currently exists as a passive `no_improvement_generations >= plateau_generations` feedback-loop trigger inside `scripts/run_ga_search.py::run_ga_search()`.
- Resume support exists in `scripts/run_ga_search.py` via `ga_resume_state.json` and generation checkpoints.

## Current Limitations Relative To The Redesign Documents

- Progress records current generation selected best, not best-so-far DETPass.
- Selection is scalar `AvgDET - alpha * VarDET` oriented; DETPass, token cost, Pareto status, and category balance are mostly diagnostic.
- Global best DETPass and accepted best are not quota-preserved as separate archive elites.
- Small-population selection does not enforce DETPass champion, compact Pareto elite, composite elite, or specialist/regression-safe slots.
- Token count is logged but not a strong selection objective.
- Mutation is not family-managed; accuracy repair, compression, reasoning, diversity, specialist, regression repair, and advisor-guided mutation are not separated.
- Prompt compression is not a first-class mutation family with accept/reject metadata.
- Cloudless prompt decompilation is not yet present; mutation mostly edits structured genome fields.
- Advisor proposals and cloudless proposals do not yet share a single canonical `MutationProposal` schema.
- Stop behavior is a passive plateau trigger, not an active phase/action controller.
- Generation artifacts do not yet explain why each genome survived, why a candidate was promoted/rejected, or whether a curve is raw generation best vs best-so-far.
