You are a prompt-block mutation advisor for a JOILang code-generation system.
You receive ONE generation-level feedback packet describing DET evaluation results.
Return ONLY a JSON object that matches required_response_schema. No prose, no markdown.
Rules:
- Do not rewrite the whole prompt; propose compact, targeted prompt-block edits only.
- Do not remove safety or output-schema constraints.
- Do not remove output schema, JSON-only rules, core blocks, service mapping, retrieval, pre-mapping, or service-context construction logic.
- Every proposal must name target_block_id, target_block_family, and affected_failure_families.
- Use only allowed_mutation_types from the packet.
Advisor Case B: DETPass is above threshold.
- Inspect prompt_token_breakdown and block_token_breakdown.
- Prefer the largest non-protected compression_allowed block-level target.
- Output at least one block_compression_proposals item when any compression_allowed block exists.
- If the largest block is protected, explicitly skip it and choose the next largest non-protected block.
- Do not propose only compress_candidate_strategies_to_minimal unless no block-level target exists and the delta is non-trivial.
- Required block fields: proposal_id, selected_block_id, selected_block_family, exact_mutation_operator, operator, mutation_type, original_token_estimate, proposed_token_estimate_after, expected_token_delta, preserved_content, removable_content, why_safe, regression_risk, validation_requirement.
- If best DETPass is above compression threshold, prioritize token-reducing mutations.
- When accuracy is saturated, propose at least one compression mutation unless regression risk is high.
- Prefer reducing few-shot count, duplicate micro-rules, candidate strategies, optional blocks, and max output tokens before adding new rules.
- Compression proposals must include expected_token_delta as a negative number.
- Do not repeat no-op compression, such as compress_candidate_strategies_to_minimal when strategies are already ["minimal"].
- When compression_ready=True, do not return only genome-level candidate_strategies compression unless candidate_strategies is not already minimal, no non-protected block-level compression target exists, and expected_token_delta is non-trivial.
- If block_token_breakdown shows compression_allowed=false or is_protected_block=true, do not target that block; explain the skip reason or choose another block.
- Do not remove output schema, JSON-only rules, core blocks, service mapping, retrieval, pre-mapping, or service-context construction.


TOKEN_REDUCTION_OBJECTIVE:
- Reduce total prompt + output tokens, not input tokens only.
- Preserve DETPass as a hard gate.
- Prefer meaningful block-level token delta over tiny genome-level changes.
- Do not propose no-op compression.

REASONING_BUDGET_ROUTER:
- Simple device commands: reasoning_budget=none. Output JOILang DSL only.
- Single condition: reasoning_budget=cod_1. At most one short decision slot.
- Temporal/delay/wait: reasoning_budget=cod_2. Slots: intent, temporal/dataflow.
- Loop/break/split+delay: reasoning_budget=cod_4. Slots: intent, device/function, temporal, loop/break.
- Never ask the final generator to output verbose Chain-of-Thought.

CHAIN_OF_DRAFT_POLICY:
- Replace verbose CoT instructions with short Chain-of-Draft slots.
- Draft is internal and optional; final output remains JOILang DSL/code only.
- Example before: 'Think step by step and explain mapping decisions.'
- Example after: 'Draft if needed: intent | temporal/loop | device/function. Then output DSL only.'

TOKENSKIP_APPROX_POLICY:
- Approximate TokenSkip at prompt level.
- Remove repeated restatement, tutorial prose, obvious reasoning, filler, and duplicated warnings.
- Keep only decision-critical tokens: intent, device/function, temporal/loop constraint, output contract.

SKELETON_OF_THOUGHT_PIPELINE:
- Use SoT as internal pipeline only: classify -> select rules/devices/examples -> generate -> validate -> repair.
- Do not expose verbose skeleton to the final model unless debug=True.
- Compress pipeline text into compact cards when possible.

SELECTIVE_CONTEXT_POLICY:
- Do not render all devices, services, enum values, examples, or rules.
- Keep only category-relevant and command-relevant context.
- Compress rendered service context, not retrieval/pre-mapping logic.

RULE_CARD_COMPRESSION_POLICY:
- Prefer compact rule cards over long prose.
- DELAY=(#Clock).clock_delay(ms)
- WAIT=wait until <cond>
- BREAK=period>0 only
- VAR_DECL=:= only at block start
- FORBID={while,sleep,inner:=,markdown,explanation}

FEW_SHOT_BUDGET_POLICY:
- Simple categories: no-example or top-1 compact NL=>DSL example.
- Temporal/loop categories: top-1/top-2 category prototype examples.
- Remove explanation/notes from examples unless they contain required JOILang identifiers.

VALIDATOR_HEAVY_REPAIR_POLICY:
- Do not resend full grammar in repair prompt.
- Repair prompt should contain: command, invalid output, compact validator error, minimal rule card, output contract.
- Escalate to fuller repair only after compact repair fails.

BLOCK_LEVEL_REWRITE_EXAMPLES:
- Verbose reasoning block -> compact_reasoning_skeleton with CoD slots.
- Long negative rules -> schema-only FORBID card.
- Many examples -> reduce_few_shot_count or category_example_budget_down.
- Long service context -> service_context_render_budget_down or compact_service_schema_fields.
- Duplicate micro-rules -> dedupe_duplicate_micro_rules or prune_micro_rules_to_top_k.
feedback_packet:
{
  "advisor_batch_id": "advisor_batch_g001_0cc56be3",
  "generation": 1,
  "model_key": "qwen25_coder_14b",
  "advisor_model_key": "gpt41_mini",
  "categories": [
    1,
    2
  ],
  "limit_per_category": 1,
  "sample_size": 2,
  "validation_size": 2,
  "generation_phase": "ACCURACY_SEARCH",
  "plateau_type": "warming_up",
  "next_action": "continue_accuracy",
  "overall": {
    "best_DETPass": 100.0,
    "best_AvgDET": 100.0,
    "best_tokens": 27082.0,
    "best_latency": 8.9198,
    "best_so_far_DETPass": 100.0,
    "accepted_best_DETPass": 0.0,
    "pareto_archive_size": 1,
    "top_failure_types": []
  },
  "category_diagnostics": [
    {
      "generation": 1,
      "model_key": "qwen25_coder_14b",
      "category": 1,
      "group": "basic",
      "row_count": 4,
      "det_pass_count": 4,
      "det_pass_rate": 100.0,
      "avg_det_score": 100.0,
      "failure_histogram": {},
      "dominant_failure_type": "",
      "likely_prompt_issue": "No deterministic failures observed; prompt grounding looks adequate.",
      "recommended_mutation_family": "diversity",
      "suggested_target_block": "06",
      "suggested_target_block_family": "DET_Helper",
      "suggested_mutation_type": "add_targeted_repair_hint",
      "representative_failures": [],
      "reasoning_budget_hint": {
        "reasoning_budget": "none",
        "draft_items_max": 0,
        "policy": "No reasoning. Generate JOILang DSL only."
      }
    },
    {
      "generation": 1,
      "model_key": "qwen25_coder_14b",
      "category": 2,
      "group": "basic",
      "row_count": 4,
      "det_pass_count": 4,
      "det_pass_rate": 100.0,
      "avg_det_score": 100.0,
      "failure_histogram": {},
      "dominant_failure_type": "",
      "likely_prompt_issue": "No deterministic failures observed; prompt grounding looks adequate.",
      "recommended_mutation_family": "diversity",
      "suggested_target_block": "06",
      "suggested_target_block_family": "DET_Helper",
      "suggested_mutation_type": "add_targeted_repair_hint",
      "representative_failures": [],
      "reasoning_budget_hint": {
        "reasoning_budget": "none",
        "draft_items_max": 0,
        "policy": "No reasoning. Generate JOILang DSL only."
      }
    }
  ],
  "group_diagnostics": {
    "basic": {
      "categories": [
        1,
        2
      ],
      "row_count": 8,
      "det_pass_count": 8,
      "det_pass_rate": 100.0,
      "avg_det_score": 100.0,
      "failure_histogram": {},
      "dominant_failure_type": "",
      "likely_prompt_issue": "No deterministic failures observed; prompt grounding looks adequate.",
      "recommended_mutation_family": "diversity"
    },
    "temporal": {
      "categories": [],
      "row_count": 0,
      "det_pass_count": 0,
      "det_pass_rate": 0.0,
      "avg_det_score": 0.0,
      "failure_histogram": {},
      "dominant_failure_type": "",
      "likely_prompt_issue": "",
      "recommended_mutation_family": ""
    },
    "complex": {
      "categories": [],
      "row_count": 0,
      "det_pass_count": 0,
      "det_pass_rate": 0.0,
      "avg_det_score": 0.0,
      "failure_histogram": {},
      "dominant_failure_type": "",
      "likely_prompt_issue": "",
      "recommended_mutation_family": ""
    }
  },
  "genome_diagnostics": {
    "top_genomes": [
      {
        "rank": 1,
        "genome_id": "gen-af17dfa2-8346-1468-fe4c-138bdd4e7245",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 27082.0,
        "blocks": [
          "01",
          "02",
          "03"
        ]
      },
      {
        "rank": 2,
        "genome_id": "gen-e6f98332-8830-5d32-df5c-e9fedd38fc7e",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 49557.0,
        "blocks": [
          "01",
          "02",
          "03",
          "05",
          "06"
        ]
      },
      {
        "rank": 3,
        "genome_id": "gen-bbf8b961-f83c-3169-009b-831460788576",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 49604.0,
        "blocks": [
          "01",
          "02",
          "03",
          "05",
          "06"
        ]
      }
    ],
    "bottom_genomes": [
      {
        "rank": 1,
        "genome_id": "gen-378892e9-ecc3-87ab-8b45-85023a0286cc",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 50876.0,
        "blocks": [
          "01",
          "02",
          "05",
          "06"
        ]
      },
      {
        "rank": 2,
        "genome_id": "gen-bbf8b961-f83c-3169-009b-831460788576",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 49604.0,
        "blocks": [
          "01",
          "02",
          "03",
          "05",
          "06"
        ]
      },
      {
        "rank": 3,
        "genome_id": "gen-e6f98332-8830-5d32-df5c-e9fedd38fc7e",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 49557.0,
        "blocks": [
          "01",
          "02",
          "03",
          "05",
          "06"
        ]
      }
    ],
    "pareto_candidates": [
      {
        "rank": 1,
        "genome_id": "gen-af17dfa2-8346-1468-fe4c-138bdd4e7245",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 27082.0,
        "blocks": [
          "01",
          "02",
          "03"
        ]
      }
    ],
    "compact_candidates": [
      {
        "rank": 1,
        "genome_id": "gen-af17dfa2-8346-1468-fe4c-138bdd4e7245",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 27082.0,
        "blocks": [
          "01",
          "02",
          "03"
        ]
      },
      {
        "rank": 2,
        "genome_id": "gen-e6f98332-8830-5d32-df5c-e9fedd38fc7e",
        "det_pass_rate": 100.0,
        "avg_det_score": 100.0,
        "avg_prompt_tokens": 49557.0,
        "blocks": [
          "01",
          "02",
          "03",
          "05",
          "06"
        ]
      }
    ]
  },
  "representative_failures": [],
  "current_prompt_artifact": {
    "genome_id": "gen-af17dfa2-8346-1468-fe4c-138bdd4e7245",
    "blocks": [
      "01",
      "02",
      "03"
    ],
    "params": {
      "model": "Qwen/Qwen2.5-Coder-14B-Instruct",
      "temperature": 0.05,
      "few_shot_count": 3,
      "max_tokens": 1024,
      "candidate_strategies": [
        "compact_json",
        "explicit_preconditions"
      ]
    },
    "block_params_summary": {
      "02": {
        "few_shot_count": 2
      },
      "05": {
        "repair_mode": "conservative",
        "few_shot_count": 3
      }
    },
    "micro_rules_by_block": {
      "02": [
        "Return exactly one JSON object only with keys name, cron, period, code.",
        "For INTEGER and DOUBLE arguments, avoid quoted numeric literals."
      ]
    },
    "prompt_token_count": 27082.0,
    "block_signature": "01,02,03",
    "prompt_hash": "8c473916accbd4e8"
  },
  "prompt_token_breakdown": {
    "generation": 1,
    "model_key": "qwen25_coder_14b",
    "total_prompt_token_estimate": 10800,
    "block_token_total_estimate": 10756,
    "genome_params_token_estimate": 44,
    "measurement_method": "char_div_4_estimate",
    "largest_token_component": "02",
    "largest_token_component_tokens": 6883
  },
  "block_token_breakdown": [
    {
      "generation": 1,
      "model_key": "qwen25_coder_14b",
      "block_id": "01",
      "block_family": "Core_System",
      "block_role": "core",
      "is_core_block": true,
      "is_protected_block": true,
      "char_count": 14148,
      "token_estimate": 3537,
      "few_shot_count": 0,
      "micro_rule_count": 0,
      "candidate_strategy_count": 0,
      "optional_status": "",
      "current_params": {},
      "compression_allowed": false,
      "safe_mutation_types": [],
      "measurement_method": "char_div_4_estimate"
    },
    {
      "generation": 1,
      "model_key": "qwen25_coder_14b",
      "block_id": "02",
      "block_family": "Service_Mapping",
      "block_role": "core",
      "is_core_block": true,
      "is_protected_block": true,
      "char_count": 27529,
      "token_estimate": 6883,
      "few_shot_count": 2,
      "micro_rule_count": 2,
      "candidate_strategy_count": 0,
      "optional_status": "",
      "current_params": {
        "few_shot_count": 2,
        "micro_rules": [
          "Return exactly one JSON object only with keys name, cron, period, code.",
          "For INTEGER and DOUBLE arguments, avoid quoted numeric literals."
        ]
      },
      "compression_allowed": false,
      "safe_mutation_types": [],
      "measurement_method": "char_div_4_estimate"
    },
    {
      "generation": 1,
      "model_key": "qwen25_coder_14b",
      "block_id": "03",
      "block_family": "Output_Schema",
      "block_role": "optional",
      "is_core_block": false,
      "is_protected_block": true,
      "char_count": 1343,
      "token_estimate": 336,
      "few_shot_count": 0,
      "micro_rule_count": 0,
      "candidate_strategy_count": 0,
      "optional_status": "active",
      "current_params": {},
      "compression_allowed": false,
      "safe_mutation_types": [],
      "measurement_method": "char_div_4_estimate"
    }
  ],
  "token_reduction_guidance": {
    "reasoning_budget_router": [
      {
        "task": "simple device command",
        "reasoning_budget": "none",
        "draft_items_max": 0,
        "instruction": "No reasoning. DSL-only.",
        "example": "Turn on the light => direct JOILang DSL."
      },
      {
        "task": "single condition",
        "reasoning_budget": "cod_1",
        "draft_items_max": 1,
        "instruction": "One short intent/device slot only if needed."
      },
      {
        "task": "temporal/delay/wait",
        "reasoning_budget": "cod_2",
        "draft_items_max": 2,
        "instruction": "Use intent + temporal/dataflow slots only."
      },
      {
        "task": "loop/break/split+loop+delay",
        "reasoning_budget": "cod_4",
        "draft_items_max": 4,
        "instruction": "Use at most 4 short decision slots internally."
      }
    ],
    "compact_rule_cards": [
      {
        "name": "OUTPUT",
        "card": "Return JOILang DSL/code only. No prose, no markdown."
      },
      {
        "name": "DELAY",
        "card": "delay => (#Clock).clock_delay(ms)"
      },
      {
        "name": "WAIT",
        "card": "wait => wait until <condition>"
      },
      {
        "name": "BREAK",
        "card": "break valid only when period > 0"
      },
      {
        "name": "VAR_DECL",
        "card": "var := only at block start"
      },
      {
        "name": "FORBID",
        "card": "FORBID={while,sleep,inner:=,explanation,markdown}"
      },
      {
        "name": "SCHEMA",
        "card": "Preserve required JOILang keys and output contract."
      }
    ],
    "token_reduction_method_cards": [
      {
        "method": "Chain of Draft",
        "apply_to": "reasoning instructions / DET helper / temporal skeleton",
        "rewrite_pattern": "Replace verbose CoT with <= 2~4 short decision slots. Never ask final model to output reasoning.",
        "example_before": "Think step by step and explain how to map the user command to devices, services, arguments, temporal constraints, and final code.",
        "example_after": "Draft only if needed: intent | device/function | temporal/loop. Then output JOILang DSL only.",
        "safe_operators": [
          "compact_reasoning_skeleton",
          "compact_block_params"
        ]
      },
      {
        "method": "TokenSkip approximation",
        "apply_to": "verbose natural-language rules",
        "rewrite_pattern": "Remove restatement, tutorial prose, obvious reasoning, repeated warnings; keep only decision-critical tokens.",
        "example_before": "You should carefully consider whether the user may be referring to a device and then decide the appropriate action.",
        "example_after": "Map device→function→args. No unrelated action.",
        "safe_operators": [
          "remove_redundant_hint_lines",
          "template_compress_rule_family"
        ]
      },
      {
        "method": "Skeleton-of-Thought pipeline",
        "apply_to": "internal prompt organization",
        "rewrite_pattern": "Use internal pipeline: classify→select rules/devices/examples→generate→validate→repair. Do not expose skeleton unless debug.",
        "example_before": "Long explanation of all possible categories and procedures.",
        "example_after": "PIPE={classify,select,generate,validate,repair}; output=DSL-only.",
        "safe_operators": [
          "compact_reasoning_skeleton"
        ]
      },
      {
        "method": "Selective Context / LLMLingua-style",
        "apply_to": "service context / device capabilities / examples",
        "rewrite_pattern": "Keep only category-relevant devices, functions, enum values, temporal rules, and top examples.",
        "example_before": "Render all device capabilities and all examples.",
        "example_after": "Render only relevant device/function/value cards and top-1/top-2 examples.",
        "safe_operators": [
          "service_context_render_budget_down",
          "compact_service_schema_fields",
          "drop_unused_device_capabilities"
        ]
      },
      {
        "method": "Few-shot distillation",
        "apply_to": "few-shot blocks",
        "rewrite_pattern": "Replace many verbose examples with top-1/top-2 compact NL=>DSL prototypes.",
        "example_before": "User command + explanation + notes + DSL for many categories.",
        "example_after": "NL => DSL compact pair, selected by category.",
        "safe_operators": [
          "reduce_few_shot_count",
          "reduce_few_shot_count_to_zero",
          "reduce_few_shot_count_by_one"
        ]
      },
      {
        "method": "Schema-only compact prompting",
        "apply_to": "rule-heavy blocks",
        "rewrite_pattern": "Replace long natural-language rules with compact cards, sets, EBNF-like constraints.",
        "example_before": "Do not use while. Do not use sleep. Do not declare variables inside nested scopes...",
        "example_after": "FORBID={while,sleep,inner:=}; VAR_DECL=block-start only.",
        "safe_operators": [
          "compact_block_params",
          "template_compress_rule_family"
        ]
      }
    ],
    "output_policy": {
      "final_output": "JOILang DSL/code only",
      "forbid": [
        "markdown",
        "explanation",
        "analysis",
        "reasoning text"
      ],
      "stop_markers": [
        "Explanation:",
        "Notes:",
        "Reason:",
        "Analysis:"
      ]
    }
  },
  "cloudless_feedback_summary": {
    "structured_feedback_count": 0,
    "applied_cloudless_mutations": [],
    "active_failure_families": [],
    "mutation_operator_credit": []
  },
  "advisor_request": {
    "goal": "Generate structured mutation proposals for the next generation.",
    "allowed_mutation_types": [
      "activate_or_strengthen_temporal_rule",
      "activate_temporal_skeleton",
      "add_canonical_service_name_rule",
      "add_micro_rule",
      "add_schema_grounding_rule",
      "add_sensor_to_action_flow_rule",
      "add_targeted_repair_hint",
      "category_example_budget_down",
      "compact_block_params",
      "compact_block_params_safe",
      "compact_reasoning_skeleton",
      "compact_service_schema_fields",
      "compress_candidate_strategies_to_minimal",
      "dedupe_duplicate_micro_rules",
      "dedupe_service_value_enums",
      "drop_optional_block",
      "drop_optional_blocks_for_budget",
      "drop_unused_device_capabilities",
      "global_render_budget_down",
      "lower_output_max_tokens",
      "lower_output_max_tokens_aggressive",
      "lower_output_max_tokens_safe",
      "merge_duplicate_micro_rules",
      "multi_block_compression_plan",
      "prune_micro_rules_to_top_k",
      "prune_micro_rules_to_top_k_safe",
      "prune_stale_micro_rules",
      "reduce_candidate_strategies",
      "reduce_few_shot_count",
      "reduce_few_shot_count_by_one",
      "reduce_few_shot_count_to_zero",
      "remove_redundant_hint_lines",
      "service_context_render_budget_down",
      "strengthen_enum_type_rule",
      "strengthen_json_only_rule",
      "strengthen_minimality_rule",
      "strengthen_no_unrelated_action_rule",
      "strengthen_owner_device_rule",
      "strengthen_rule",
      "strengthen_skeleton_rule",
      "strengthen_temporal_rule",
      "template_compress_rule_family"
    ],
    "compression_policy": {
      "activate_when_detpass_ge": 90.0,
      "compression_ready": true,
      "compression_phase": "COMPRESSION_READY",
      "prefer_compression_if_accuracy_saturated": true,
      "target_token_reduction_ratio": 0.15,
      "allow_aggressive_compression": false,
      "preserve_core_blocks": true,
      "preserve_output_schema": true,
      "preserve_service_mapping": true
    },
    "constraints": [
      "Do not rewrite the whole prompt.",
      "Return structured JSON proposals only.",
      "Prefer compact targeted changes.",
      "Do not remove safety/output schema constraints.",
      "Every proposal must specify target block/family and affected failure family.",
      "If compression is proposed, specify expected token reduction and regression risk."
    ]
  },
  "render_budget_hooks": {
    "enabled": false,
    "allowed_global_budget_operators": []
  }
}

required_response_schema:
{
  "advisor_status": "accepted",
  "compression_policy": {
    "activate_when_detpass_ge": 90.0,
    "compression_ready": true,
    "compression_phase": "COMPRESSION_READY",
    "prefer_compression_if_accuracy_saturated": true,
    "target_token_reduction_ratio": 0.15,
    "allow_aggressive_compression": false,
    "preserve_core_blocks": true,
    "preserve_output_schema": true,
    "preserve_service_mapping": true
  },
  "prompt_token_breakdown_seen": true,
  "block_token_breakdown_seen": true,
  "proposals": [
    {
      "proposal_id": "g001_01",
      "target_block_id": "02",
      "target_block_family": "Service_Mapping",
      "mutation_family": "accuracy_repair",
      "mutation_type": "add_micro_rule",
      "priority": 1,
      "reason": "short reason",
      "affected_failure_families": [
        "schema_violation",
        "unknown_service"
      ],
      "category_scope": [
        1,
        2
      ],
      "group_scope": [
        "basic"
      ],
      "proposed_micro_rule": "concise rule text",
      "expected_effect": "what the change should fix",
      "expected_token_delta": 12,
      "regression_risk": 0.2,
      "apply_mode": "create_child",
      "token_reduction_methods": [],
      "reasoning_budget_before": "",
      "reasoning_budget_after": "",
      "prompt_rewrite_before": "",
      "prompt_rewrite_after": "",
      "rule_cards_added_or_kept": [],
      "output_budget_policy": ""
    },
    {
      "proposal_id": "g001_compress_01",
      "target_block_id": "genome",
      "target_block_family": "Compression",
      "mutation_family": "compression",
      "mutation_type": "compress_candidate_strategies_to_minimal",
      "priority": 3,
      "reason": "Accuracy is saturated; reduce prompt token cost.",
      "affected_failure_families": [
        "token_overbudget"
      ],
      "category_scope": [
        1,
        2
      ],
      "group_scope": [
        "basic"
      ],
      "proposed_micro_rule": "",
      "expected_effect": "Reduce prompt tokens while preserving schema/service grounding.",
      "expected_token_delta": -1000,
      "regression_risk": 0.25,
      "apply_mode": "create_child",
      "token_reduction_methods": [
        "TokenSkip approximation"
      ],
      "reasoning_budget_before": "",
      "reasoning_budget_after": "",
      "prompt_rewrite_before": "verbose candidate strategy list",
      "prompt_rewrite_after": "minimal candidate strategy",
      "rule_cards_added_or_kept": [],
      "output_budget_policy": "unchanged"
    }
  ],
  "micro_compression_proposals": [
    {
      "proposal_id": "g001_micro_01",
      "mutation_family": "compression",
      "compression_level": "micro",
      "target_block_id": "genome",
      "target_block_family": "Compression",
      "mutation_type": "dedupe_duplicate_micro_rules",
      "expected_token_delta": -80,
      "regression_risk": 0.05,
      "token_reduction_methods": [
        "TokenSkip approximation"
      ],
      "reasoning_budget_before": "",
      "reasoning_budget_after": "",
      "prompt_rewrite_before": "duplicate or redundant micro-rules",
      "prompt_rewrite_after": "deduplicated compact micro-rules",
      "rule_cards_added_or_kept": [],
      "output_budget_policy": "unchanged",
      "affected_failure_families": [
        "token_overbudget"
      ]
    }
  ],
  "block_compression_proposals": [
    {
      "proposal_id": "g001_block_01",
      "mutation_family": "compression",
      "compression_level": "block",
      "target_block_id": "06",
      "target_block_family": "DET_Helper",
      "selected_block_id": "06",
      "selected_block_family": "DET_Helper",
      "exact_mutation_operator": "prune_micro_rules_to_top_k",
      "operator": "prune_micro_rules_to_top_k",
      "mutation_type": "prune_micro_rules_to_top_k",
      "original_token_estimate": 5200,
      "proposed_token_estimate_after": 2600,
      "expected_token_delta": -2600,
      "preserved_content": [
        "validator-critical JSON/service/temporal rules"
      ],
      "removable_content": [
        "duplicate or tutorial-style rules"
      ],
      "why_safe": "The selected block is non-core and keeps validator-critical constraints.",
      "regression_risk": 0.2,
      "validation_requirement": "strict DETPass gate",
      "affected_failure_families": [
        "token_overbudget"
      ],
      "token_reduction_methods": [
        "Chain of Draft",
        "TokenSkip approximation"
      ],
      "reasoning_budget_before": "verbose_or_unbounded",
      "reasoning_budget_after": "cod_2",
      "prompt_rewrite_before": "verbose instruction summary",
      "prompt_rewrite_after": "compact instruction summary",
      "rule_cards_added_or_kept": [
        "DELAY",
        "WAIT",
        "FORBID"
      ],
      "output_budget_policy": "DSL-only, no prose",
      "block_rewrite_strategy": "schema_only_card | chain_of_draft | selective_context | few_shot_distillation",
      "example_before": "Verbose prompt instructions, long few-shot examples, or repeated natural-language rules.",
      "example_after": "Compact rule cards, CoD slots, selected context, or distilled NL=>DSL examples."
    }
  ],
  "multi_block_compression_proposals": [
    {
      "proposal_id": "g001_multi_01",
      "mutation_family": "compression",
      "compression_level": "multi_block",
      "target_block_id": "genome",
      "target_block_family": "Compression",
      "operator": "multi_block_compression_plan",
      "mutation_type": "multi_block_compression_plan",
      "selected_block_ids": [
        "05",
        "06"
      ],
      "exact_mutation_operator": "multi_block_compression_plan",
      "steps": [
        {
          "block_id": "06",
          "operator": "prune_micro_rules_to_top_k",
          "k": 3
        },
        {
          "block_id": "05",
          "operator": "compact_block_params"
        }
      ],
      "total_expected_token_delta": -3300,
      "regression_risk": 0.35,
      "affected_failure_families": [
        "token_overbudget"
      ],
      "token_reduction_methods": [
        "Chain of Draft",
        "TokenSkip approximation",
        "Selective Context / LLMLingua-style"
      ],
      "reasoning_budget_before": "verbose_or_unbounded",
      "reasoning_budget_after": "cod_2_or_cod_4_by_category",
      "prompt_rewrite_before": "multiple verbose or redundant blocks",
      "prompt_rewrite_after": "compact CoD/rule-card/selective-context blocks",
      "rule_cards_added_or_kept": [
        "DELAY",
        "WAIT",
        "BREAK",
        "FORBID"
      ],
      "output_budget_policy": "DSL-only, no prose",
      "block_rewrite_strategy": "multi_block: chain_of_draft + schema_only_card + selective_context",
      "example_before": "Block 05/06 contain repeated rules, verbose helper text, or many examples.",
      "example_after": "Block 05/06 keep only compact rule cards, top-k micro-rules, and DSL-only output contract."
    }
  ],
  "global_budget_compression_proposals": [
    {
      "proposal_id": "g001_global_01",
      "mutation_family": "compression",
      "compression_level": "global_budget",
      "exact_mutation_operator": "service_context_render_budget_down",
      "operator": "service_context_render_budget_down",
      "mutation_type": "service_context_render_budget_down",
      "target_block_id": "genome",
      "target_block_family": "Compression",
      "expected_token_delta": -1500,
      "regression_risk": 0.3,
      "validation_requirement": "strict DETPass gate",
      "affected_failure_families": [
        "token_overbudget"
      ],
      "token_reduction_methods": [
        "Selective Context / LLMLingua-style"
      ],
      "reasoning_budget_before": "",
      "reasoning_budget_after": "",
      "prompt_rewrite_before": "full rendered service context",
      "prompt_rewrite_after": "category-relevant rendered service context only",
      "rule_cards_added_or_kept": [],
      "output_budget_policy": "unchanged"
    }
  ]
}