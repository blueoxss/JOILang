# GA PromptOps advisor + summary fix — todo

Target: `gpt_mg/version0_15_update20260413`

## Confirmed bugs (reproduced with mock advisor smoke)
- [x] advisor proposals logged with empty parent/child ids (logged before application)
- [x] ga_block_diffs llm_advised=false (advisor children never applied — quota full)
- [x] population_transitions new_by_advisor=0 (elites=3 + cloudless=1 == pop=4 before advisor loop)
- [x] ga_summary.json missing best_DETPass / accepted_best_DETPass; compact_best empty

## Implementation
- [ ] Extend `MutationProposal` with lifecycle/advisor fields (proposal_state, advisor_batch_id, category/group scope, scheduling_reason, duplicate fields, token delta, regression risk, priority)
- [ ] New module `scripts/advisor_feedback.py`:
  - [ ] deterministic `category_feedback(histogram)` mapping
  - [ ] `build_category_diagnostics`, `build_group_diagnostics`
  - [ ] `select_representative_failures`
  - [ ] `build_advisor_feedback_batch` (full packet)
  - [ ] `build_advisor_prompt_from_batch`
  - [ ] `validate_advisor_proposal`
  - [ ] `apply_advisor_proposal` (parent -> child via ga_mutation.apply_mutation_proposal)
- [ ] run_ga_search.py wiring:
  - [ ] CLI flags (strict, max-representative-failures, feedback-detail, include-candidate-code, include-prompt-summary, force-child-quota, min-population-for-child); trigger-mode `always`
  - [ ] advisor invocation gated by trigger mode; batch packet written; raw responses saved
  - [ ] advisor-aware elite quota so advisor child gets a slot
  - [ ] apply accepted advisor proposals -> children with lifecycle states; advisor candidate pool
  - [ ] new_by_advisor + advisor transition columns
  - [ ] log advisor MutationProposal rows AFTER application (parent/child filled)
  - [ ] topk source + advisor_batch_id
  - [ ] summary rewrite: all required fields + summary_consistency_check
- [ ] Tests: `tests/test_advisor_feedback_loop.py` (10 tests)
- [ ] compileall + pytest both test files
- [ ] mock smoke (advisor pop=4) + cloudless vs advisor A/B
- [ ] OpenAI advisor smoke (token via env only — never written to repo)

## Review section
(filled at end)
