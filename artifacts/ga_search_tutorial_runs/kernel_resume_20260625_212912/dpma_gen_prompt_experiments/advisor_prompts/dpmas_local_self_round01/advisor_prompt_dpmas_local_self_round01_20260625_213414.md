# System

You are the local model acting as a JOILang prompt self-advisor. You must propose compact mutations that the same local model can reliably follow.

You are not generating JOILang code.
You are not rewriting the full JOILang generation prompt.
You are mutating selected blocks of the current generation prompt.

Strict DET is the official metric.
Use row-level diagnostics and representative GT/generated examples as evidence.
The advisor prompt contains selected gen_n block cards/snippets, not the entire gen_n prompt.

Return exactly one valid JSON object.
Do not use markdown fences.
Do not write prose outside JSON.
Do not output runtime-only patches, Block 00 patches, or Generation_Health patches.
If the primary block candidate is not sufficient, you may redirect to a secondary block or create an auxiliary patch block.

# User

Generate a block-level prompt mutation payload.

Input package:
{
  "meta": {
    "schema_version": "dpma_advisor_prompt_input_v1",
    "created_at": "2026-06-25T21:34:14",
    "advisor_variant": "dpmas_local_self_round01",
    "advisor_mode": "local_self",
    "advisor_model": "qwen25_coder_7b",
    "official_metric": "strict_det",
    "purpose": "Infer block-level prompt mutations. The advisor prompt and selected gen_n blocks are inputs; the output is a mutation payload, not a full JOILang generation prompt."
  },
  "concepts": {
    "gen_n": "The current JOILang generation prompt represented as a block-structured prompt genome.",
    "advisor_prompt": "A meta prompt that combines instructions, diagnostics, examples, and selected gen_n blocks.",
    "block_mutation_payload": "The advisor output. It specifies how selected prompt blocks should be mutated.",
    "gen_n_plus_1": "The next generation prompt produced by applying validated mutations to gen_n.",
    "soft_block_targeting": "The system gives primary, secondary, and auxiliary block candidates. The advisor may accept, redirect, combine, or supplement these candidates."
  },
  "official_policy": {
    "strict_det_is_official": true,
    "cloud_reasoning_is_auxiliary": false,
    "do_not_generate_joilang_code": true,
    "do_not_rewrite_full_prompt": true,
    "mutate_selected_blocks_only": true
  },
  "output_schema": {
    "top_level": [
      "advisor_meta",
      "mutations"
    ],
    "mutation_required_keys": [
      "mutation_id",
      "target_block_id",
      "target_block_family",
      "operation",
      "mutation_text",
      "rationale",
      "evidence_rows",
      "evidence_diagnostics",
      "expected_effect",
      "risk",
      "token_delta_estimate"
    ],
    "allowed_operations": [
      "append_micro_rule",
      "replace_micro_rule",
      "compress_block_rule",
      "create_auxiliary_patch_block",
      "disable_conflicting_rule",
      "adjust_example_selection"
    ],
    "expected_block_by_family": {
      "Service_Mapping": "02",
      "Receiver_Tag_Preservation": "02",
      "Enum_Grounding": "02",
      "Argument_Grounding": "02",
      "Output_Schema": "03",
      "Parser_Extraction": "03",
      "Temporal_Rule": "06",
      "Numeric_Unit_Grounding": "06",
      "Dataflow": "06",
      "Intent_Fulfillment": "06",
      "Skeleton": "06",
      "DET_Helper": "06",
      "Minimality": "06",
      "Auxiliary_Patch_Block": "AUX"
    },
    "forbidden_families": [
      "Generation_Health",
      "No_Mutation",
      "Prompt_Budget",
      "Runtime_Health"
    ],
    "minimum_mutations": 1
  },
  "diagnostic_summary": {
    "row_count": 280,
    "top_signals": [
      [
        "output_collapse",
        280
      ],
      [
        "unknown_service",
        280
      ],
      [
        "gt_service_coverage",
        280
      ],
      [
        "period_mismatch",
        280
      ],
      [
        "gt_mismatch",
        280
      ],
      [
        "gt_receiver_coverage",
        279
      ],
      [
        "numeric_grounding",
        161
      ],
      [
        "enum_grounding",
        161
      ],
      [
        "cron_mismatch",
        40
      ]
    ],
    "top_advisor_families": [
      [
        "Skeleton",
        280
      ],
      [
        "Service_Mapping",
        280
      ],
      [
        "Temporal_Rule",
        280
      ],
      [
        "DET_Helper",
        280
      ],
      [
        "Receiver_Tag_Preservation",
        279
      ],
      [
        "Numeric_Unit_Grounding",
        161
      ],
      [
        "Enum_Grounding",
        161
      ]
    ],
    "dominant_pattern": "The current local generator often collapses to unrelated repeated output and shows canonical service, receiver, schedule, numeric, and enum grounding failures."
  },
  "failure_taxonomy": [
    {
      "signal": "cron_mismatch",
      "diagnostic_template": "cron mismatch: gt cron={gt_cron!r}, generated cron={generated_cron!r}. Fixed wall-clock schedule was lost.",
      "target_family": "Temporal_Rule",
      "target_block_id": 6,
      "micro_rule": "For explicit fixed times, weekdays, midnight, or scheduled one-shot commands, derive cron first and preserve it exactly. Do not replace a fixed schedule with a period loop or a Clock guard unless repeated monitoring is explicit.",
      "mutation_policy": "fixed wall-clock/day schedule uses cron first; do not replace with period + Clock guard"
    },
    {
      "signal": "period_mismatch",
      "diagnostic_template": "period mismatch: gt period={gt_period!r}, generated period={generated_period!r}.",
      "target_family": "Temporal_Rule",
      "target_block_id": 6,
      "micro_rule": "For one-shot action or scheduled one-shot commands, use period=0 unless repeated monitoring is explicit. Use positive period only for repeated monitoring loops and never use -1 as a substitute for a valid one-shot period.",
      "mutation_policy": "classify one-shot / cron / repeated loop first, then apply period policy"
    },
    {
      "signal": "gt_mismatch",
      "diagnostic_template": "gt mismatch: code is schema-valid but not target-equivalent; prioritize concrete mismatches.",
      "target_family": "DET_Helper",
      "target_block_id": 6,
      "micro_rule": "When code is schema-valid but not target-equivalent, compare schedule, receiver, service, numeric, enum, dataflow, and action order before final output.",
      "mutation_policy": "umbrella only; do not make primary patch if concrete service/receiver/schedule/numeric/enum reason exists"
    },
    {
      "signal": "gt_service_coverage",
      "diagnostic_template": "missing GT service: gt services={gt_services}, generated services={generated_services}.",
      "target_family": "Service_Mapping",
      "target_block_id": 2,
      "micro_rule": "Include every service implied by the command. Select services only from the injected schema under the selected receiver and do not substitute adjacent service families.",
      "mutation_policy": "select command target receiver first, then select schema-valid service under that receiver"
    },
    {
      "signal": "unknown_service",
      "diagnostic_template": "unknown/canonical service error: generated services={generated_services}; expected schema/GT services={gt_services}.",
      "target_family": "Service_Mapping",
      "target_block_id": 2,
      "micro_rule": "Never invent service/member names. Copy the canonical device-prefixed service member exactly from the injected service schema. Do not emit camelCase, class-style, capitalized, or paraphrased service names.",
      "mutation_policy": "replace non-schema member with nearest valid canonical schema member before final output"
    },
    {
      "signal": "gt_receiver_coverage",
      "diagnostic_template": "receiver mismatch: gt receivers={gt_receivers}, generated receivers={generated_receivers}.",
      "target_family": "Receiver_Tag_Preservation",
      "target_block_id": 2,
      "micro_rule": "Select receiver tags from the current command target before service selection. Preserve owner, location, group, and sector tags exactly, and do not reuse a receiver from another row.",
      "mutation_policy": "owner/location/group/sector tag preservation; condition receiver and action receiver may differ"
    },
    {
      "signal": "numeric_grounding",
      "diagnostic_template": "numeric mismatch: gt numeric literals={gt_numeric_literals}, generated numeric literals={generated_numeric_literals}.",
      "target_family": "Numeric_Unit_Grounding",
      "target_block_id": 6,
      "micro_rule": "Preserve required numeric arguments and thresholds from the command. Convert units using the selected service descriptor, such as minutes to seconds for seconds-based arguments.",
      "mutation_policy": "temporal numbers and service argument numbers both use descriptor-grounded conversion"
    },
    {
      "signal": "enum_grounding",
      "diagnostic_template": "enum mismatch: gt string args={gt_string_args}, generated string args={generated_string_args}.",
      "target_family": "Enum_Grounding",
      "target_block_id": 2,
      "micro_rule": "For enum-valued services, copy the allowed enum value exactly from the selected service descriptor. Do not translate, paraphrase, or borrow enum values from another device or service.",
      "mutation_policy": "copy allowed enum from selected service descriptor only"
    },
    {
      "signal": "arg_type",
      "diagnostic_template": "argument type mismatch: preserve positional order, numeric/string/boolean type, and schema separator.",
      "target_family": "Argument_Grounding",
      "target_block_id": 2,
      "micro_rule": "Preserve positional argument order, argument type, separator, bounds, and format from the selected service descriptor.",
      "mutation_policy": "type/order/separator/format rule"
    },
    {
      "signal": "dataflow",
      "diagnostic_template": "dataflow mismatch: generated does not preserve read-bind-use structure required by GT.",
      "target_family": "Dataflow",
      "target_block_id": 6,
      "micro_rule": "When reading a value for reporting or control, bind it with JOILang ':=' and use that bound value downstream. Do not replace read-bind-use flow with an unrelated direct action.",
      "mutation_policy": "sensor read → variable bind → downstream speak/action structure preservation"
    },
    {
      "signal": "semantic",
      "diagnostic_template": "semantic intent mismatch: generated code follows a different high-level intent than the command.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Classify the current command as one-shot, condition-action, cron schedule, period loop, or trigger-then-repeat before service emission.",
      "mutation_policy": "use only with concrete diagnostic; do not patch from semantic alone"
    },
    {
      "signal": "conditions",
      "diagnostic_template": "condition mismatch: generated condition does not preserve command precondition or trigger subject.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Preserve explicit if-condition subjects and action targets separately. Do not convert a precondition into an action or omit the trigger subject.",
      "mutation_policy": "condition subject/action target separation"
    },
    {
      "signal": "precondition",
      "diagnostic_template": "precondition mismatch: output ignores or changes required if-condition before action.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Represent explicit state preconditions as guard conditions before actions. Do not replace a required state check with an unconditional action.",
      "mutation_policy": "precondition-first skeleton"
    },
    {
      "signal": "invalid_json",
      "diagnostic_template": "invalid JSON: return exactly one JSON object with keys name, cron, period, code; no markdown/prose/code fences.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Return exactly one JSON object with required keys name, cron, period, and code. Do not emit markdown fences, prose, comments, or multiple JSON objects.",
      "mutation_policy": "JSON-only if raw candidate exists; Generation_Health if raw candidate is empty"
    },
    {
      "signal": "invalid_json.non_json_text",
      "diagnostic_template": "non-json output: raw candidate exists but starts as prose/text.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Return bare JSON only. Do not introduce the answer with prose or explanation.",
      "mutation_policy": "JSON-only rule"
    },
    {
      "signal": "invalid_json.markdown_fence",
      "diagnostic_template": "markdown fence error: remove JSON/code fences and return bare JSON only.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Do not wrap the final JSON in markdown code fences. Output the JSON object directly.",
      "mutation_policy": "fence prohibition"
    },
    {
      "signal": "invalid_json.malformed_json",
      "diagnostic_template": "malformed JSON: raw output exists but cannot be parsed.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Emit parseable JSON with double-quoted keys and values where required. Do not output trailing text after the JSON object.",
      "mutation_policy": "parseable JSON contract"
    },
    {
      "signal": "truncated_json",
      "diagnostic_template": "truncated JSON: output ended before a complete JSON object was produced.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Keep the final JSON concise and complete. Close every object/string and avoid verbose names or explanations that risk truncation.",
      "mutation_policy": "shorter parseable JSON; also inspect max_new_tokens"
    },
    {
      "signal": "missing_required_key",
      "diagnostic_template": "missing required JSON key: {reason}.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Always include required keys name, cron, period, and code. Do not rename code to script in final generated JSON unless the evaluator explicitly accepts it.",
      "mutation_policy": "required key rule"
    },
    {
      "signal": "schema_missing_required_keys",
      "diagnostic_template": "schema missing required keys: required final keys were omitted.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Validate final JSON keys before returning. The object must contain name, cron, period, and code.",
      "mutation_policy": "required keys and aliases"
    },
    {
      "signal": "schema_invalid_field_type",
      "diagnostic_template": "schema invalid field type: name/cron/code must be strings and period must be scalar.",
      "target_family": "Output_Schema",
      "target_block_id": 3,
      "micro_rule": "Use string values for name, cron, and code, and use an integer/scalar value for period. Do not use arrays or objects for these fields.",
      "mutation_policy": "field type rule"
    },
    {
      "signal": "missing_generated_code",
      "diagnostic_template": "empty generated code: candidate has no behavior although GT is non-empty.",
      "target_family": "Intent_Fulfillment",
      "target_block_id": 6,
      "micro_rule": "For a non-empty user command, the code field must contain at least one required JOILang action, condition, or schedule body. Do not return empty code unless the GT behavior is explicitly empty.",
      "mutation_policy": "valid JSON empty behavior routes to Intent/Skeleton unless raw generation failed"
    },
    {
      "signal": "missing_official_gt",
      "diagnostic_template": "dataset issue: official gt is missing; do not mutate prompt based on this row.",
      "target_family": "No_Mutation",
      "target_block_id": 0,
      "micro_rule": "Do not mutate prompts from rows whose official GT is missing.",
      "mutation_policy": "exclude from prompt mutation"
    },
    {
      "signal": "missing_gt_code",
      "diagnostic_template": "dataset issue: GT code is empty; suppress semantic prompt mutation unless empty behavior is intended.",
      "target_family": "No_Mutation",
      "target_block_id": 0,
      "micro_rule": "Do not create semantic/service patches from rows with empty GT code unless the row explicitly tests empty behavior.",
      "mutation_policy": "exclude or validate empty behavior"
    },
    {
      "signal": "generation_empty_output",
      "diagnostic_template": "generation failure: no valid raw candidate was produced.",
      "target_family": "Generation_Health",
      "target_block_id": 0,
      "micro_rule": "Fix generation health before semantic prompt mutation. Inspect raw response, worker logs, prompt length, model config, and timeout.",
      "mutation_policy": "short-circuit semantic diagnostics; inspect worker/runtime/prompt length"
    },
    {
      "signal": "generation_runtime_error",
      "diagnostic_template": "runtime failure: generation raised runtime error.",
      "target_family": "Generation_Health",
      "target_block_id": 0,
      "micro_rule": "Runtime failures are not JOILang semantic failures. Fix worker/runtime error before adding service or receiver rules.",
      "mutation_policy": "runtime fix first"
    },
    {
      "signal": "generation_cuda_oom",
      "diagnostic_template": "CUDA OOM: reduce prompt payload/context or runtime memory before semantic rules.",
      "target_family": "Prompt_Budget",
      "target_block_id": 0,
      "micro_rule": "For CUDA OOM, reduce prompt payload or runtime memory first. Do not add semantic rules that increase prompt length.",
      "mutation_policy": "prompt budget reduction, schema top-k, quantization/runtime config"
    },
    {
      "signal": "generation_timeout",
      "diagnostic_template": "generation timeout: tune timeout/retry/model loading before semantic prompt mutation.",
      "target_family": "Runtime_Health",
      "target_block_id": 0,
      "micro_rule": "For timeouts, tune worker timeout, retry policy, or model loading. Do not infer service/receiver semantic failure from timeout rows.",
      "mutation_policy": "retry/time budget/runtime policy"
    },
    {
      "signal": "candidate_extraction_failure",
      "diagnostic_template": "candidate extraction failure: inspect wrapping/fences/prose and extraction regex before semantic changes.",
      "target_family": "Parser_Extraction",
      "target_block_id": 3,
      "micro_rule": "Ensure the model returns exactly one bare JSON object so the extractor can identify it unambiguously.",
      "mutation_policy": "extractor improvement or JSON-only rule"
    },
    {
      "signal": "valid_json_empty_behavior_match",
      "diagnostic_template": "no-op match: valid empty JSON was expected because GT behavior is empty.",
      "target_family": "No_Mutation",
      "target_block_id": 0,
      "micro_rule": "Do not mutate prompts for rows where empty behavior is the correct GT behavior.",
      "mutation_policy": "no mutation"
    },
    {
      "signal": "valid_json_empty_behavior_failure",
      "diagnostic_template": "valid JSON but empty behavior: command requires non-empty code.",
      "target_family": "Intent_Fulfillment",
      "target_block_id": 6,
      "micro_rule": "If the command requests any action, condition, schedule, or notification, generate non-empty code that implements it.",
      "mutation_policy": "minimum behavior generation"
    },
    {
      "signal": "semantic_intent",
      "diagnostic_template": "cloud semantic-intent low score: use only as auxiliary explanation; strict DET remains primary.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Use cloud semantic feedback only as auxiliary reasoning when it agrees with strict DET component failures.",
      "mutation_policy": "priority boost only when aligned with strict DET"
    },
    {
      "signal": "device_service",
      "diagnostic_template": "cloud device-service low score: selected receiver/service does not align with command target.",
      "target_family": "Service_Mapping",
      "target_block_id": 2,
      "micro_rule": "Use device-service cloud feedback only when strict DET also shows service or receiver mismatch.",
      "mutation_policy": "combine with strict service/receiver diagnostics only"
    },
    {
      "signal": "gpt_semantic",
      "diagnostic_template": "GPT semantic mismatch: auxiliary holistic judgment says output changes user intent.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Do not use GPT holistic score as the official metric. Use it only to explain strict DET-backed failures.",
      "mutation_policy": "strict DET first"
    },
    {
      "signal": "extraneous",
      "diagnostic_template": "extraneous action: remove generated actions not implied by command or GT.",
      "target_family": "Minimality",
      "target_block_id": 6,
      "micro_rule": "Do not add services, actions, reads, variables, or wrapper logic that are not implied by the current command.",
      "mutation_policy": "remove unnecessary read/action/wrapper/state"
    },
    {
      "signal": "output_collapse",
      "diagnostic_template": "output collapse: same generated code reused across unrelated rows.",
      "target_family": "Skeleton",
      "target_block_id": 6,
      "micro_rule": "Solve each row independently from the current command. Never reuse a previous row's JSON name, receiver, service, enum, or code skeleton.",
      "mutation_policy": "row independence and command-specific receiver/service selection"
    }
  ],
  "dpma_r_draft_proposal": [
    {
      "patch_id": "row_advisor_001_Skeleton_06",
      "target_block_family": "Skeleton",
      "target_block_id": "06",
      "operation": "append_micro_rule",
      "patch_text": "Solve each dataset row independently from the current command only. Never reuse a previous row's JSON name, receiver, service, enum argument, numeric argument, or code skeleton.",
      "rationale": "Expanded Skeleton rule from 280 empirical row(s). Representative diagnostics: output collapse: same generated code reused across unrelated rows.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "output collapse: same generated code reused across unrelated rows."
      ]
    },
    {
      "patch_id": "row_advisor_002_Service_Mapping_02",
      "target_block_family": "Service_Mapping",
      "target_block_id": "02",
      "operation": "append_micro_rule",
      "patch_text": "Never invent service/member names. Copy the exact canonical device-prefixed service member from the injected schema, preserving lowercase, underscores, and device prefix. If a generated member looks camelCase, class-style, capitalized, or paraphrased, replace it with the nearest schema-valid canonical member before final JSON.",
      "rationale": "Expanded Service_Mapping rule from 280 empirical row(s). Representative diagnostics: service mismatch: expected canonical schema service but generated service differs or is hallucinated.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "service mismatch: expected canonical schema service but generated service differs or is hallucinated."
      ]
    },
    {
      "patch_id": "row_advisor_003_Temporal_Rule_06",
      "target_block_family": "Temporal_Rule",
      "target_block_id": "06",
      "operation": "append_micro_rule",
      "patch_text": "Classify schedule type before writing JSON: one-shot action, fixed cron trigger, repeated period loop, delay sequence, or trigger-then-repeat. Use period=0 for one-shot or scheduled one-shot commands, preserve explicit cron triggers, and use positive period only when repeated monitoring is explicit.",
      "rationale": "Expanded Temporal_Rule rule from 280 empirical row(s). Representative diagnostics: schedule mismatch: cron/period policy differs from GT.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "schedule mismatch: cron/period policy differs from GT."
      ]
    },
    {
      "patch_id": "row_advisor_004_DET_Helper_06",
      "target_block_family": "DET_Helper",
      "target_block_id": "06",
      "operation": "append_micro_rule",
      "patch_text": "When code is schema-valid but not target-equivalent, compare schedule, receiver, service, numeric, enum, dataflow, and action order before final output. Verify schedule, receiver, service, numeric, enum, dataflow, and output schema before final JSON.",
      "rationale": "Expanded DET_Helper rule from 280 empirical row(s). Representative diagnostics: overall GT mismatch: perform component-wise final verification.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "overall GT mismatch: perform component-wise final verification."
      ]
    },
    {
      "patch_id": "row_advisor_005_Receiver_Tag_Preservation_02",
      "target_block_family": "Receiver_Tag_Preservation",
      "target_block_id": "02",
      "operation": "append_micro_rule",
      "patch_text": "Select the receiver tag from the current command target before choosing any service. Preserve owner/location/group/sector tags exactly and choose only services attached to that receiver; never reuse a receiver from a previous row.",
      "rationale": "Expanded Receiver_Tag_Preservation rule from 279 empirical row(s). Representative diagnostics: receiver mismatch: generated receiver differs from command/GT receiver.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "receiver mismatch: generated receiver differs from command/GT receiver."
      ]
    },
    {
      "patch_id": "row_advisor_006_Numeric_Unit_Grounding_06",
      "target_block_family": "Numeric_Unit_Grounding",
      "target_block_id": "06",
      "operation": "append_micro_rule",
      "patch_text": "Preserve every numeric literal required by the current command and bind it to the selected service argument. Convert units using the service descriptor, such as minutes to seconds for seconds-based arguments, and never drop numeric thresholds or durations.",
      "rationale": "Expanded Numeric_Unit_Grounding rule from 161 empirical row(s). Representative diagnostics: numeric mismatch: required numeric literal or converted unit is missing or incorrect.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "251",
        "211",
        "219",
        "230",
        "216"
      ],
      "evidence_diagnostics": [
        "numeric mismatch: required numeric literal or converted unit is missing or incorrect."
      ]
    },
    {
      "patch_id": "row_advisor_007_Enum_Grounding_02",
      "target_block_family": "Enum_Grounding",
      "target_block_id": "02",
      "operation": "append_micro_rule",
      "patch_text": "For enum-valued services, copy the allowed enum string exactly from the selected service descriptor. Do not translate, paraphrase, or borrow enum values from another device or previous row.",
      "rationale": "Expanded Enum_Grounding rule from 161 empirical row(s). Representative diagnostics: enum/string mismatch: generated enum argument differs from selected service descriptor.",
      "evidence_rows": [
        "218",
        "222",
        "195",
        "186",
        "187",
        "264",
        "174",
        "280",
        "259",
        "150"
      ],
      "evidence_diagnostics": [
        "enum/string mismatch: generated enum argument differs from selected service descriptor."
      ]
    }
  ],
  "selected_block_candidates": [
    {
      "block_id": "02",
      "block_family": "Service_Mapping",
      "title": "Required candidate for Service_Mapping",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Service_Mapping.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.7,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "primary"
    },
    {
      "block_id": "06",
      "block_family": "Temporal_Rule",
      "title": "Required candidate for Temporal_Rule",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Temporal_Rule.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.7,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "secondary"
    },
    {
      "block_id": "06",
      "block_family": "Skeleton",
      "title": "Required candidate for Skeleton",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Skeleton.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.7,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "secondary"
    },
    {
      "block_id": "06",
      "block_family": "DET_Helper",
      "title": "Required candidate for DET_Helper",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for DET_Helper.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.7,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "secondary"
    },
    {
      "block_id": "02",
      "block_family": "Receiver_Tag_Preservation",
      "title": "Required candidate for Receiver_Tag_Preservation",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Receiver_Tag_Preservation.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.6975,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "secondary"
    },
    {
      "block_id": "02",
      "block_family": "Enum_Grounding",
      "title": "Required candidate for Enum_Grounding",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Enum_Grounding.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.4025,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "06",
      "block_family": "Numeric_Unit_Grounding",
      "title": "Required candidate for Numeric_Unit_Grounding",
      "path": "",
      "hash": "virtual",
      "char_count": 0,
      "summary": "Candidate mutation block for Numeric_Unit_Grounding.",
      "current_text_snippet": "",
      "allowed_operations": [
        "append_micro_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.4025,
      "targeting_reason": "required family candidate from failure taxonomy",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "retry_command",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/retry_command.md",
      "hash": "123c21b207ff1d4d",
      "char_count": 1310,
      "summary": "# version 2025-08-06\n\"When generating a new JOI Lang code after user feedback, Don't generate the previously generated code ({all_items[choice_no]}) as the same.\n    Integrate all newly added conditions with the previous requirements, and ensure the new code satisfies every combined requirement.\n    Regenerate the JOI Lang code based on **current sentence** and **the added conditions**.: {current_sentence}\n\n---\n\n- ✅ This rule applies to **function** services (e.g., `switch_on`, `alarm_off`)  \nan\n...<truncated>",
      "current_text_snippet": "# version 2025-08-06\n\"When generating a new JOI Lang code after user feedback, Don't generate the previously generated code ({all_items[choice_no]}) as the same.\n    Integrate all newly added conditions with the previous requirements, and ensure the new code satisfies every combined requirement.\n    Regenerate the JOI Lang code based on **current sentence** and **the added conditions**.: {current_sentence}\n\n---\n\n- ✅ This rule applies to **function** services (e.g., `switch_on`, `alarm_off`)  \nand also to **value** services used in conditions (e.g., `temperatureMeasurement_temperature > 30`)\n\n- ❗ When the input mentions broad categories like \"모든 장치\" or \"all devices\",  \nyou must **not generalize to all known devices** with the matching function (e.g., switch_off).\nInstead, follow this stricter rule:\n\n✅ Only include device categories that have already been **explicitly or implicitly referenced** in the original input or earlier part of the code.\n\n- Example:\n- Input: \"조명을 꺼줘 + 모든 장치 꺼줘.\"\n- Since only `조명 (Light)` was mentioned, only `Light` is a valid inferred category.\n- Final code: `all(#Light).switch_off()`\n\n❌ Do not auto-include all categories like `#Fan`, `#DoorLock`, `#Feeder`, etc.  \nunless they were **previously mentioned** or **explicitly covered by tag filters** in connected_devices.",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.0026,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.026",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "caution_prompt_8",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/caution_prompt_8.md",
      "hash": "0353b5e34b8ea5c9",
      "char_count": 23492,
      "summary": "# STRICT INSTRUCTIONS:\n## If [**Connected_devices**] exist: Additional Constraints on Functional Equivalence and Device Availability\n## Else use all [**service_list**]\n- Functional synonyms must be resolved based on device availability:\n  - If both `#Alarm` and `#Siren` are potential alert devices:\n    - Use `#Alarm` only if `#Alarm` exists in connected_devices.\n    - Use `#Siren` only if `#Alarm` is absent and `#Siren` exists.\n    - Treat “alert”, “notify”, “alarm”, and “siren” as equivalent ex\n...<truncated>",
      "current_text_snippet": "# STRICT INSTRUCTIONS:\n## If [**Connected_devices**] exist: Additional Constraints on Functional Equivalence and Device Availability\n## Else use all [**service_list**]\n- Functional synonyms must be resolved based on device availability:\n  - If both `#Alarm` and `#Siren` are potential alert devices:\n    - Use `#Alarm` only if `#Alarm` exists in connected_devices.\n    - Use `#Siren` only if `#Alarm` is absent and `#Siren` exists.\n    - Treat “alert”, “notify”, “alarm”, and “siren” as equivalent expressions for this rule, \"알람\", \"사이렌\" as synonymous\n    Below are examples of how similar user instructions produce different code depending on the service:\n    \"사이렌과 경광등을 동시에 켜 줘\"\n    {\"code\": \"(#Alarm).alarm_both()\"} for #Alarm\n    {\"code\": \"(#Siren).siren_setsirenmode(\\\"both\\\")\"} for #Siren\n    \"사이렌과 경광등을 꺼 줘\"\n    {\"code\": \"(#Alarm).alarm_off()\"} for #Alarm\n    {\"code\": \"(#Siren).siren_setsirenmode(\\\"off\\\")\"} for #Siren\n    make sure the generated code matches the correct service context.\n    **Important:** If the command is about activating a specific feature such as the strobe light on a siren, do **not** use `switch_on()` which only powers the device.  \n    Instead, use the appropriate action method.\n    #### Example:\n    - **Command:** \"Turn on the strobe.\"  \n      - [Correct]\n        ```\n        {\n          \"name\": \"Scenario1\",\n          \"cron\": \"\",\n          \"period\": -1,\n          \"code\": \"(#Siren).siren_setsirenmode(\\\"strobe\\\")\"\n        }\n        ```\n      - [Incorrect]\n        ```\n        {\n          \"name\": \"Scenario1\",\n          \"cron\": \"\",\n          \"period\": -1,\n          \"code\": \"(#Siren).switch_on()\"\n        }\n        ```\n\n  - If both `#PresenceSensor` and `#OccupancySensor` provide presence detection:\n    - Use `#PresenceSensor` only if it exists in connected_devices.\n      example: (#PresenceSensor).presencesensor_presence == \\\"present\\\"\n    - Use `#OccupancySensor` only if `#PresenceSensor` is absent and `#OccupancySensor` exists.\n      example: (#OccupancySensor).occupancysensor_presence == \\\"present\\\"\n    - Treat “presence detection”, “occupancy detection”, “재실 여부”, “존재 여부” as synonymous.\n- In presence of `connected_devices`, device references must *\n...<truncated>",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.02,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.200",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "grammar_ver1.5.10",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/grammar_ver1.5.10.md",
      "hash": "0065eb550c13c58f",
      "char_count": 15077,
      "summary": "# Timing Control\n## cron\n- `cron` (String): UNIX cron syntax for trigger. \n  - cron = '': Start immediately. No further cron triggers.\n  - Resets scenario regardless of blocking.\n  - Use \"cron\": \"* * * * *\", and specify other fields (hour, day, etc.) as needed in standard  \n  - UNIX cron order: minute, hour, day, month, weekday.\n  - Use cron for scenarios triggered at specific time schedules, such as:\n  - \"매일\", \"매주\", \"매월\" 같은 정기적인 시간 기반 반복\n## [Example] \"매일 아침 9시에 실행\" → cron: \"0 9 * * *\"\n### Warni\n...<truncated>",
      "current_text_snippet": "# Timing Control\n## cron\n- `cron` (String): UNIX cron syntax for trigger. \n  - cron = '': Start immediately. No further cron triggers.\n  - Resets scenario regardless of blocking.\n  - Use \"cron\": \"* * * * *\", and specify other fields (hour, day, etc.) as needed in standard  \n  - UNIX cron order: minute, hour, day, month, weekday.\n  - Use cron for scenarios triggered at specific time schedules, such as:\n  - \"매일\", \"매주\", \"매월\" 같은 정기적인 시간 기반 반복\n## [Example] \"매일 아침 9시에 실행\" → cron: \"0 9 * * *\"\n### Warning\n  - The cron field only determines when the scenario starts. Once triggered, the period field controls how frequently the code repeats.\n  - Without a proper termination condition (break), the scenario may continue running indefinitely, even when the original cron condition is no longer valid.\n  - Use the following condition at the start of your code block to stop execution on weekdays:\n### ✅ Required Behavior  \n- **Always insert a `break` statement when the repetition condition is no longer valid.**  \n- For scenarios that should only run on specific days (e.g., weekends), include logic such as:\n```\n'cron': '0 0 * * 0,6', \n'period': 5000\n'code':\nweekday = (#Clock).clock_weekday\nif ((weekday != 'saturday') and (weekday != 'sunday')) {\n    break\n}\n```\n\n## period\n- `period` (Integer): Controls execution loop after cron trigger\n  - `-1`: Execute once, then stop.\n  - `0`: Execute once per cron trigger. (no further execution within the same cron cycle)\n  - `>= 100`: Repeat every period milliseconds (continuous monitoring).\n\n## *break*: Stops current/future periods until next cron.\n  - **If the user command includes instructions to stop or terminate the repetition (for example, \"반복을 중단해\", \"더 이상 반복하지 마\", \"중단\", \"until stopped\", etc.), you must ensure the periodic execution loop is interrupted by using `break` inside the code block at the appropriate condition.**\n  - With cron = \"\": stops permanently after break\n  - With scheduled cron: stops until next cron trigger\n\n### [Example]\n```\ncode:\n  <flag> := true\n  if (<stop_condition>) {\n    break\n  }\n  if (<flag> == true) {\n    (#Tag).<action>()\n    <flag> = false\n  }\n```\n\n## When to Use `period` over `cron`\n- If the user command inc\n...<truncated>",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.02,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.200",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "response_prompt_baseline_cot",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/response_prompt_baseline_cot.md",
      "hash": "faa1b0ba7dbde583",
      "char_count": 12477,
      "summary": "# System Prompt – Response Steps\n## **Step 1: Device and Service Extraction**\n\nFrom the input sentence, extract **all relevant device tags and their associated services** using both `[service_list]` and `[connected_devices]`.  \nThis step is critical to ensure accurate JoILang code generation for all mentioned devices and actions.\n\n### Device & Service Matching Principles:\n- If multiple devices are mentioned together using conjunctions like:\n  - `\"A와 B\"`, `\"A 및 B\"`, `\"A, B\"`, `\"A 또는 B\"`, `\"A와 B 모\n...<truncated>",
      "current_text_snippet": "# System Prompt – Response Steps\n## **Step 1: Device and Service Extraction**\n\nFrom the input sentence, extract **all relevant device tags and their associated services** using both `[service_list]` and `[connected_devices]`.  \nThis step is critical to ensure accurate JoILang code generation for all mentioned devices and actions.\n\n### Device & Service Matching Principles:\n- If multiple devices are mentioned together using conjunctions like:\n  - `\"A와 B\"`, `\"A 및 B\"`, `\"A, B\"`, `\"A 또는 B\"`, `\"A와 B 모두\"`\n  → You **must extract all services for each device individually**.\n\n- For compound possessive or nested expressions such as:  \n  `\"알람과 사이렌의 알림과 경광등을 켜줘\"`  \n  → You must resolve **accurate device–service mappings**.  \n  Example:\n  - `\"알람\"` device supports:\n    - `alarm_siren()`\n    - `strobe_on()`\n  - `\"사이렌\"` device supports:\n    - `siren_setsirenmode(\"siren\")`\n    - `strobe_on()`\n  → Final extraction:\n    - `#Alarm` → `[alarm_siren(), strobe_on()]`\n    - `#Siren` → `[siren_setsirenmode(\"siren\"), strobe_on()]`\n\n---\n\n### Strict Extraction Rules\n\n- **Exact service name match** required:  \n  Service names must match **exactly** those defined in `[service_list]`.\n\n- **Exact connected tag preservation required:**\n  - If the user mentions a room, group, sector, top/bottom, odd/even, or other qualifier that appears in `[connected_devices]`, include the exact connected tag in the receiver.\n  - Every receiver tag after `#` must start with an uppercase English letter. Use `#Bedroom`, `#Sector1`, `#Entrance`, and `#TemperatureSensor`, never `#bedroom`, `#sector1`, `#entrance`, or `#temperaturesensor`.\n  - Use `all(...)` whenever the user says all/every/모든/모두.\n  - Do not replace connected tags with synonyms. Use `#Top` if the connected tag is `Top`, not `#Upper`.\n\n- **Descriptor/unit grounding required:**\n  - Read `descriptor`, `return_descriptor`, `argument_descriptor`, `argument_bounds`, and `argument_format` before writing values.\n  - If the service descriptor says millivolts, convert volts to millivolts: `220V` -> `220000`.\n  - If the function argument is seconds, convert minutes to seconds.\n  - If the argument format is comma, do not use `|`.\n  - For plain \"turn on/off\", \"st\n...<truncated>",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.02,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.200",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "service_prompt_10",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/service_prompt_10.md",
      "hash": "8f64ba140db7d07a",
      "char_count": 22299,
      "summary": "## Step-by-Step Guide for Separating `value` and `function` in Natural Language Commands (Prompt Guide)\n\n---\n\n## Purpose\nYour task is to:\n1. Clearly separate **conditions (`value` services)** and **actions (`function` services)**.\n2. Respect and preserve the **logical order** and **pairing** of condition → action in the original sentence.\n3. Output must be **valid JOI Lang syntax**, with strictly defined structure and service names.\n\n---\n\n## Current Service Naming Policy\n- The injected `[service\n...<truncated>",
      "current_text_snippet": "## Step-by-Step Guide for Separating `value` and `function` in Natural Language Commands (Prompt Guide)\n\n---\n\n## Purpose\nYour task is to:\n1. Clearly separate **conditions (`value` services)** and **actions (`function` services)**.\n2. Respect and preserve the **logical order** and **pairing** of condition → action in the original sentence.\n3. Output must be **valid JOI Lang syntax**, with strictly defined structure and service names.\n\n---\n\n## Current Service Naming Policy\n- The injected `[service_list]`, `[service_list_value]`, and `[service_list_function]` snippets are authoritative.\n- When a service entry has a `canonical_name`, use that device-prefixed service name and lowercase the final JOILang member after the dot.\n  - `Siren_SetSirenMode` -> `(#Siren).siren_setsirenmode(\"siren\")`\n  - `TemperatureSensor_Temperature` -> `(#TemperatureSensor).temperaturesensor_temperature`\n  - `Speaker_Speak` -> `(#Speaker).speaker_speak(message)`\n  - `RobotVacuumCleaner_SetRobotVacuumCleanerModeMode` -> `(#RobotVacuumCleaner).robotvacuumcleaner_setrobotvacuumcleanermodemode(\"auto\")`\n- Do not use older capability-style service names when the injected current service list provides a device-prefixed canonical service.\n- Do not spell service names from memory. Copy the exact current canonical service name and only lowercase it for the final JOILang member.\n- Never insert, remove, or reorder words inside a service member name. For example, `setrobotvacuumcleanermodemode` must not become `setrobotvacuumcleanermodermode`.\n\n## Descriptor and Unit Grounding Policy\n- The service entry fields `descriptor`, `return_descriptor`, `argument_descriptor`, `argument_type`, `argument_bounds`, and `argument_format` are authoritative.\n- Before writing any comparison value or argument literal, read these descriptor fields and convert the user value to the service unit.\n  - If `return_descriptor` says `millivolts`, convert volts to millivolts: `220V` -> `220000`.\n  - If a cooking-time argument is described in seconds, convert minutes to seconds: `30 minutes` -> `1800`.\n  - If an argument format says comma, use comma-separated arguments, never `|`.\n- Source selection is part of descriptor grounding\n...<truncated>",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.02,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.200",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "13",
      "block_family": "Prompt_Block",
      "title": "tempo_prompt_9",
      "path": "/home/mgjeong/Desktop/llm/JOILang-Server/gpt_mg/version0_13/tempo_prompt_9.md",
      "hash": "35412ccb0e85f812",
      "char_count": 12457,
      "summary": "### 1. Static condition (state check): ~였으면, ~인 상태면, ~라면 (If)\n   - This applies when the condition is already true at the time of evaluation.\n   - The system simply checks the current state and executes immediately if the condition is met.\n   - It assumes that the state has already been sustained for some time.\n   Common Expressions:\n      \"if it is...\", \"if the state is...\", \"in case of...\"\n   #### Caution:\n   - if (...) only checks the current state.\n   - It does not detect or care about any p\n...<truncated>",
      "current_text_snippet": "### 1. Static condition (state check): ~였으면, ~인 상태면, ~라면 (If)\n   - This applies when the condition is already true at the time of evaluation.\n   - The system simply checks the current state and executes immediately if the condition is met.\n   - It assumes that the state has already been sustained for some time.\n   Common Expressions:\n      \"if it is...\", \"if the state is...\", \"in case of...\"\n   #### Caution:\n   - if (...) only checks the current state.\n   - It does not detect or care about any prior changes.\n   - It will not trigger if the system is waiting for a transition (e.g., from \"off\" to \"on\").\n   **Applies when the state is already true at evaluation time.**\n   #### [example]\n   - “if the door is closed” → if ((#Door).doorControl_door == \"closed\")\n   - “if the light is on” → if ((#Light).switch_switch == \"on\")\n   - Korean command: “문이 닫혀 있으면”\n   - English translated command: \"if the door is closed\"\n   - → if ((#Door).doorControl_door == \"closed\")\n   - 현재 상태가 닫힘일 때 즉시 실행\n\n### 2. Dynamic transition (state change detection): ~하면, ~되면, ~하게 되면 (When)\n   **Triggers only when the condition becomes true from the opposite state.**\n   **If the condition implies a **transition** from a previous numeric state (e.g., below threshold → above threshold)**\n   - This triggers only when a condition changes from false to true.\n   - It captures a moment of change, not just a static state.\n   - This is important for event-driven scenarios where the system must wait for a state to become true.\n   - **Important**: Even though this looks like a numeric threshold, it still implies a **change in state** (from <80 to >=80), and must be treated as **Dynamic Transition**.\n   - And uses words like “되면”, “넘으면”, “이상이 되면”, “떨어지면”,\n   - Then use:  \n   → `wait until (...)`\n   #### [incorrect]\n   - DO NOT use `if (humidity >= 80)` for:\n   - \"습도가 80% 이상이 되면\"  \n   - Instead, use `wait until (humidity >= 80)`\n   #### [example2]\n   - “습도가 80% 이상이 되면 블라인드를 내려 줘.”  \n   → `wait until ((#HumiditySensor).relativeHumidityMeasurement_humidity >= 80.0)`  \n   → `(#Blind).windowShade_close()`\n   - Korean command: \"습도가 80% 이상이 되면\"\n   - English translated command: \"when humidity becomes greater than or eq\n...<truncated>",
      "allowed_operations": [
        "append_micro_rule",
        "replace_micro_rule",
        "compress_block_rule",
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": -0.02,
      "targeting_reason": "taxonomy_prior=0.000, keyword_score=0.000, token_penalty=0.200",
      "candidate_role": "auxiliary_or_low_priority"
    },
    {
      "block_id": "AUX",
      "block_family": "Auxiliary_Patch_Block",
      "title": "Auxiliary patch block option",
      "path": "",
      "hash": "new",
      "char_count": 0,
      "summary": "Use only if no existing selected block can localize the mutation without creating conflicting rules.",
      "current_text_snippet": "",
      "allowed_operations": [
        "create_auxiliary_patch_block"
      ],
      "soft_target_score": 0.1,
      "targeting_reason": "fallback option for advisor-correctable mutation",
      "candidate_role": "auxiliary"
    }
  ],
  "representative_examples": [
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Service_Mapping"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Service_Mapping"
    },
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Receiver_Tag_Preservation"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Receiver_Tag_Preservation"
    },
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Enum_Grounding"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Enum_Grounding"
    },
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Temporal_Rule"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Temporal_Rule"
    },
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Numeric_Unit_Grounding"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Numeric_Unit_Grounding"
    },
    {
      "row_no": "218",
      "category": "7",
      "command_eng": "Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.",
      "command_kor": "자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.",
      "det_score": 10.035,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['door_doorstate', 'levelcontrol_movetolevel'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Hallway#Light', 'all(#Door'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 0-5 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['50', '0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['open'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.167832, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "door_doorstate",
          "levelcontrol_movetolevel"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Hallway#Light",
          "all(#Door"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "50",
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "open"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 0-5 * * *",
        "period": 0,
        "code_or_script": "if (all(#Door).door_doorstate ==| \"open\") {\n\n    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Skeleton"
    },
    {
      "row_no": "222",
      "category": "7",
      "command_eng": "Every morning at 8 AM, make the speaker speak 'Get up'. Additionally, if the window is closed, open it.",
      "command_kor": "매일 아침 8시에 스피커로 ‘일어나세요’라고 말해 줘. 그리고 창문이 닫혀있으면 열어줘.",
      "det_score": 11.9512,
      "det_pass": false,
      "failure_reasons": [
        "cron_mismatch",
        "period_mismatch",
        "gt_mismatch",
        "gt_service_coverage",
        "unknown_service",
        "gt_receiver_coverage",
        "numeric_grounding",
        "enum_grounding"
      ],
      "normalized_signals": [
        "output_collapse",
        "unknown_service",
        "gt_receiver_coverage",
        "gt_service_coverage",
        "cron_mismatch",
        "period_mismatch",
        "numeric_grounding",
        "enum_grounding",
        "gt_mismatch"
      ],
      "advisor_families": [
        "Skeleton",
        "Service_Mapping",
        "Receiver_Tag_Preservation",
        "Temporal_Rule",
        "Numeric_Unit_Grounding",
        "Enum_Grounding",
        "DET_Helper"
      ],
      "concrete_diagnostics": [
        "output_collapse: no specialized diagnostic rule; compare gt_code and generated_code",
        "service mismatch: gt services=['armrobot_currentposition', 'speaker_speak', 'windowcovering_uporopen'], generated services=['dishwasherMode_setDishwasherMode']; generated service 'dishwasherMode_setDishwasherMode' looks camelCase/class-style; copy schema canonical lowercase_underscore member",
        "receiver mismatch: gt receivers=['#Speaker', '#Window', '(#Window'], generated receivers=['#Dishwasher']",
        "cron mismatch: gt cron='0 8 * * *', generated cron=''",
        "period mismatch: gt period=0, generated period=-1",
        "numeric mismatch: gt numeric literals=['0'], generated numeric literals=[]",
        "enum/string mismatch: gt string args=['일어나세요'], generated string args=['dry']",
        "overall GT mismatch: gt_similarity=0.231707, code_match=False; prioritize concrete component diagnostics"
      ],
      "diff_summary": {
        "gt_services": [
          "armrobot_currentposition",
          "speaker_speak",
          "windowcovering_uporopen"
        ],
        "generated_services": [
          "dishwasherMode_setDishwasherMode"
        ],
        "gt_receivers": [
          "#Speaker",
          "#Window",
          "(#Window"
        ],
        "generated_receivers": [
          "#Dishwasher"
        ],
        "gt_numeric_literals": [
          "0"
        ],
        "generated_numeric_literals": [],
        "gt_string_args": [
          "일어나세요"
        ],
        "generated_string_args": [
          "dry"
        ]
      },
      "gt_json": {
        "name": "",
        "cron": "0 8 * * *",
        "period": 0,
        "code_or_script": "(#Speaker).speaker_speak(\"일어나세요\")\n\nif ((#Window).armrobot_currentposition == 0) {\n\n    (#Window).windowcovering_uporopen()\n\n}"
      },
      "generated_json": {
        "name": "DishwasherDryMode",
        "cron": "",
        "period": -1,
        "code_or_script": "(#Dishwasher).dishwasherMode_setDishwasherMode(\"dry\")"
      },
      "example_for_family": "Skeleton"
    }
  ],
  "source_artifacts": {
    "row_advisor_mapping": "/home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/qwen25_coder_7b/row_advisor_mapping/row_advisor_mapping.csv",
    "advisor_rich_feedback": "/home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/qwen25_coder_7b/row_advisor_mapping/advisor_rich_feedback.json",
    "failure_taxonomy": "/home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/qwen25_coder_7b/row_advisor_mapping/failure_taxonomy_table.csv",
    "dpma_r_payload": "/home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/qwen25_coder_7b/row_advisor_mapping/advisor_prompt_patches.json",
    "expanded_verified_patches": "/home/mgjeong/Desktop/llm/JOILang-Server/artifacts/ga_search_tutorial_runs/cloudless_model_suite_20260624_021806/full_det_qwen25_coder_7b_allrows_20260624_021859/qwen25_coder_7b/row_advisor_mapping/expanded_verified_patches.json"
  }
}

Output exactly one JSON object in this shape:

{
  "advisor_meta": {
    "schema_version": "block_mutation_payload_v1",
    "source": "dpmas_local_self_round01",
    "advisor_mode": "local_self",
    "source_model": "qwen25_coder_7b",
    "target_prompt_transition": "gen_n_to_gen_n+1",
    "official_metric": "strict_det"
  },
  "mutations": [
    {
      "mutation_id": "dpmas_local_self_round01_block02_service_mapping",
      "target_block_id": "02",
      "target_block_family": "Service_Mapping",
      "operation": "append_micro_rule",
      "mutation_text": "Never invent service/member names. Copy the exact canonical device-prefixed service member from the injected schema.",
      "rationale": "Rows show camelCase/class-style service hallucinations.",
      "evidence_rows": ["row ids"],
      "evidence_diagnostics": ["concrete diagnostic strings"],
      "expected_effect": ["reduce unknown_service"],
      "risk": "May over-constrain service aliasing if schema aliases are valid.",
      "token_delta_estimate": 40
    }
  ]
}

Rules:
- The output is a mutation payload, not the final gen prompt.
- Include at least one mutation.
- Prefer small, block-local mutations.
- Preserve token budget.
- You may refine or reject the DPMA-R draft proposal.
- You may choose primary, secondary, or auxiliary block candidates.