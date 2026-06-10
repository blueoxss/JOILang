#!/usr/bin/env python3
from __future__ import annotations

import json
import random
from typing import Any

from scripts.mutation_proposals import MutationProposal
from utils.ga_block_model import get_core_blocks, get_optional_blocks, normalize_active_blocks, validate_genome_blocks
from utils.pipeline_common import seeded_uuid


FAMILY_RATIOS = {
    "ACCURACY_SEARCH": {
        "accuracy_repair": 0.60,
        "temporal_reasoning": 0.15,
        "diversity": 0.15,
        "compression": 0.10,
    },
    "ROBUSTNESS_STABILIZATION": {
        "accuracy_repair": 0.35,
        "temporal_reasoning": 0.20,
        "regression_repair": 0.15,
        "compression": 0.20,
        "diversity": 0.10,
    },
    "COMPRESSION_SEARCH": {
        "compression": 0.75,
        "regression_repair": 0.10,
        "diversity": 0.07,
        "accuracy_repair": 0.05,
        "temporal_reasoning": 0.03,
    },
    "DISRUPTIVE_SEARCH": {
        "compression": 0.35,
        "diversity": 0.35,
        "accuracy_repair": 0.15,
        "temporal_reasoning": 0.15,
    },
}

COMPRESSION_MUTATION_TYPES = {
    "drop_optional_block",
    "drop_optional_blocks_for_budget",
    "reduce_few_shot_count",
    "reduce_few_shot_count_to_zero",
    "reduce_few_shot_count_by_one",
    "merge_duplicate_micro_rules",
    "dedupe_duplicate_micro_rules",
    "prune_stale_micro_rules",
    "prune_micro_rules_to_top_k",
    "prune_micro_rules_to_top_k_safe",
    "template_compress_rule_family",
    "reduce_candidate_strategies",
    "compress_candidate_strategies_to_minimal",
    "compact_reasoning_skeleton",
    "lower_output_max_tokens",
    "lower_output_max_tokens_safe",
    "lower_output_max_tokens_aggressive",
    "compact_block_params",
    "compact_block_params_safe",
    "remove_redundant_hint_lines",
    "multi_block_compression_plan",
    "global_render_budget_down",
    "category_example_budget_down",
    "service_context_render_budget_down",
    "compact_service_schema_fields",
    "dedupe_service_value_enums",
    "drop_unused_device_capabilities",
}

PROTECTED_BLOCK_IDS = set(get_core_blocks()) | {"03"}
PROTECTED_RULE_MARKERS = (
    "return exactly one json",
    "json object only",
    "never emit markdown",
    "required keys",
    "name, cron, period",
    "output schema",
    "json-only",
)


def mutation_family_for_phase(phase: str, rng: random.Random) -> str:
    ratios = FAMILY_RATIOS.get(str(phase or "ACCURACY_SEARCH"), FAMILY_RATIOS["ACCURACY_SEARCH"])
    roll = rng.random()
    cumulative = 0.0
    for family, weight in ratios.items():
        cumulative += weight
        if roll <= cumulative:
            return family
    return next(iter(ratios))


def proposal_for_family(
    *,
    family: str,
    generation: int,
    parent_genome_id: str,
    feedback_hint: dict[str, Any] | None = None,
    rng: random.Random,
    aggressive_compression: bool = False,
) -> MutationProposal:
    if family == "compression":
        safe_operators = [
            "reduce_few_shot_count",
            "merge_duplicate_micro_rules",
            "prune_micro_rules_to_top_k",
            "reduce_candidate_strategies",
            "compact_reasoning_skeleton",
            "lower_output_max_tokens",
            "compact_block_params",
        ]
        aggressive_operators = [
            "drop_optional_block",
            "drop_optional_blocks_for_budget",
            "reduce_few_shot_count_to_zero",
            "compress_candidate_strategies_to_minimal",
            "lower_output_max_tokens_aggressive",
            "prune_stale_micro_rules",
            "template_compress_rule_family",
        ]
        operator = rng.choice(safe_operators + aggressive_operators if aggressive_compression else safe_operators)
    elif family == "temporal_reasoning":
        operator = "activate_temporal_skeleton"
    elif family == "diversity":
        operator = rng.choice(["layout_shuffle", "block_variant_switch", "random_compact_seed"])
    elif family == "specialist":
        operator = rng.choice(["basic_compact_prompt", "temporal_skeleton_prompt", "complex_state_machine_prompt"])
    elif family == "regression_repair":
        operator = "restore_regression_safe_rule"
    else:
        operator = str((feedback_hint or {}).get("suggested_mutation_type") or "add_micro_rule")
    return MutationProposal(
        proposal_id=f"{family}_g{generation:03d}_{seeded_uuid(rng)[:8]}",
        source="det_feedback" if feedback_hint else "cloudless",
        mutation_family=family,
        operator=operator,
        target_block_id=str((feedback_hint or {}).get("prompt_block_id", "")),
        target_block_family=str((feedback_hint or {}).get("affected_block_family", "")),
        replacement_text=str((feedback_hint or {}).get("rule", "")),
        risk_score=0.45 if family == "compression" and aggressive_compression else (0.35 if family == "compression" else 0.2),
        affected_failure_families=[str((feedback_hint or {}).get("failure_type", ""))] if feedback_hint else [],
        expected_effect=f"{family} mutation generated by phase-aware scheduler.",
        generation=generation,
        parent_genome_id=parent_genome_id,
    )


def apply_mutation_proposal(
    genome: dict[str, Any],
    proposal: MutationProposal,
    *,
    rng: random.Random,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    before = json.loads(json.dumps(genome, ensure_ascii=False))
    child = json.loads(json.dumps(genome, ensure_ascii=False))
    child["id"] = f"gen-{seeded_uuid(rng)}"
    child["seed"] = rng.randint(1, 10**9)
    child.setdefault("params", {})
    child.setdefault("block_params", {})
    child.setdefault("blocks", get_core_blocks())
    optional = [block for block in child.get("blocks", []) if block in get_optional_blocks()]
    operator = proposal.operator
    target_block_id = proposal.selected_block_id or proposal.target_block_id
    target_blocks = [str(block) for block in (proposal.selected_block_ids or proposal.target_units or []) if str(block).strip()]
    if target_block_id and target_block_id not in {"genome", "optional"} and not target_blocks:
        target_blocks = [target_block_id]
    if operator == "drop_optional_block" and optional:
        removable = [block for block in optional if block not in PROTECTED_BLOCK_IDS]
        if target_block_id and target_block_id in removable:
            removable = [target_block_id]
        if removable:
            target = removable[0]
            child["blocks"] = normalize_active_blocks([block for block in child.get("blocks", []) if block != target])
    elif operator == "drop_optional_blocks_for_budget" and optional:
        removable = [block for block in optional if block not in PROTECTED_BLOCK_IDS]
        if target_blocks:
            removable = [block for block in target_blocks if block in removable]
        if removable:
            remove_count = 1 if len(removable) == 1 else max(1, len(removable) - 1)
            targets = set(removable[:remove_count])
            child["blocks"] = normalize_active_blocks([block for block in child.get("blocks", []) if block not in targets])
    elif operator in {"reduce_few_shot_count", "few_shot_reduction", "reduce_few_shot_count_by_one"}:
        block_ids = target_blocks or ["02"]
        for block_id in block_ids:
            block = child["block_params"].setdefault(block_id, {})
            before_count = int(block.get("few_shot_count", 2) or 2)
            block["few_shot_count"] = max(0, before_count - 1)
    elif operator == "reduce_few_shot_count_to_zero":
        changed = False
        candidate_items = (
            [(block_id, child["block_params"].setdefault(block_id, {})) for block_id in target_blocks]
            if target_blocks
            else list(child["block_params"].items())
        )
        for _block_id, params in candidate_items:
            if isinstance(params, dict) and "few_shot_count" in params:
                params["few_shot_count"] = 0
                changed = True
        if not changed and not target_blocks and "02" in child["block_params"]:
            child["block_params"].setdefault("02", {})["few_shot_count"] = 0
    elif operator in {"merge_duplicate_micro_rules", "dedupe_duplicate_micro_rules", "prune_stale_micro_rules", "template_compress_rule_family", "remove_redundant_hint_lines"}:
        candidate_items = (
            [(block_id, child["block_params"].setdefault(block_id, {})) for block_id in target_blocks]
            if target_blocks
            else list(child["block_params"].items())
        )
        for block_id, params in candidate_items:
            rules = list(params.get("micro_rules") or [])
            params["micro_rules"] = _dedupe_and_limit_rules(rules, limit=4)
    elif operator in {"prune_micro_rules_to_top_k", "prune_micro_rules_to_top_k_safe"}:
        candidate_items = (
            [(block_id, child["block_params"].setdefault(block_id, {})) for block_id in target_blocks]
            if target_blocks
            else list(child["block_params"].items())
        )
        for block_id, params in candidate_items:
            rules = list(params.get("micro_rules") or [])
            params["micro_rules"] = _dedupe_and_limit_rules(rules, limit=3 if operator.endswith("_safe") else 2)
    elif operator == "reduce_candidate_strategies":
        strategies = list(child["params"].get("candidate_strategies") or [])
        child["params"]["candidate_strategies"] = strategies[: max(1, min(2, len(strategies)))] or ["direct"]
    elif operator == "compress_candidate_strategies_to_minimal":
        strategies = list(child["params"].get("candidate_strategies") or [])
        compact = [item for item in ["minimal", "canonical_names_first"] if item in strategies]
        child["params"]["candidate_strategies"] = compact or ["minimal"]
    elif operator == "compact_reasoning_skeleton":
        child["params"]["reasoning_layout"] = "compact_skeleton"
        for block_id in (target_blocks or ["06"]):
            block = child["block_params"].setdefault(block_id, {})
            if block.get("micro_rules"):
                block["micro_rules"] = _dedupe_and_limit_rules(list(block.get("micro_rules") or []), limit=2)
    elif operator in {"lower_output_max_tokens", "lower_max_tokens", "lower_output_max_tokens_safe"}:
        child["params"]["max_tokens"] = min(int(child["params"].get("max_tokens", 768) or 768), 512)
    elif operator == "lower_output_max_tokens_aggressive":
        current = int(child["params"].get("max_tokens", 768) or 768)
        child["params"]["max_tokens"] = 384 if current > 384 else (256 if current > 256 else current)
    elif operator in {"compact_block_params", "compact_block_params_safe"}:
        compacted: dict[str, Any] = {}
        for block_id, params in list(child["block_params"].items()):
            if target_blocks and block_id not in target_blocks:
                compacted[str(block_id)] = params
                continue
            if not isinstance(params, dict) or not params:
                continue
            cleaned = {}
            for key, value in params.items():
                key_text = str(key)
                if key_text in {"layout_notes", "strategy_notes", "verbosity_hint", "verbose_reasoning", "long_rationale"}:
                    continue
                if key_text == "micro_rules":
                    cleaned[key_text] = _dedupe_and_limit_rules(list(value or []), limit=3)
                elif value not in ("", None) and value != [] and value != {}:
                    cleaned[key_text] = value
            if cleaned:
                compacted[str(block_id)] = cleaned
        child["block_params"] = compacted
    elif operator == "multi_block_compression_plan":
        for block_id in target_blocks[:3]:
            params = child["block_params"].setdefault(block_id, {})
            if block_id not in PROTECTED_BLOCK_IDS and int(params.get("few_shot_count") or 0) > 0:
                params["few_shot_count"] = 0
            if params.get("micro_rules"):
                params["micro_rules"] = _dedupe_and_limit_rules(list(params.get("micro_rules") or []), limit=3)
        child["params"]["reasoning_layout"] = "compact_skeleton"
    elif operator in {"global_render_budget_down", "category_example_budget_down"}:
        child["params"]["max_tokens"] = min(int(child["params"].get("max_tokens", 768) or 768), 384)
        child["params"]["candidate_strategies"] = [
            item
            for item in ["minimal", "canonical_names_first"]
            if item in list(child["params"].get("candidate_strategies") or [])
        ] or ["minimal"]
    elif operator in {"service_context_render_budget_down", "compact_service_schema_fields", "dedupe_service_value_enums", "drop_unused_device_capabilities"}:
        child["params"]["service_context_render_budget"] = "compact"
    elif operator in {"activate_temporal_skeleton", "strengthen_temporal_rule"}:
        blocks = list(child.get("blocks", []))
        if "06" not in blocks:
            blocks.append("06")
        child["blocks"] = normalize_active_blocks(blocks)
        rules = child["block_params"].setdefault("06", {}).setdefault("micro_rules", [])
        rule = "Use compact skeleton: trigger -> delay/repeat -> guard -> action -> termination."
        if rule not in rules:
            rules.append(rule)
    elif operator in {"layout_shuffle", "block_variant_switch", "random_compact_seed"}:
        child["params"]["layout_mode"] = rng.choice(["schema_task_output", "output_first", "temporal_first", "skeleton_first"])
    elif proposal.replacement_text:
        block_id = proposal.target_block_id if proposal.target_block_id in {"02", "03", "06"} else "02"
        rules = child["block_params"].setdefault(block_id, {}).setdefault("micro_rules", [])
        if proposal.replacement_text not in rules:
            rules.append(proposal.replacement_text)
    child.setdefault("_ga_metadata", {})
    child["_ga_metadata"].update(
        {
            "parent_ids": [proposal.parent_genome_id or str(genome.get("id", ""))],
            "mutation_types": [operator],
            "mutation_family": proposal.mutation_family,
            "mutation_operator": operator,
            "mutation_proposal_id": proposal.proposal_id,
            "base_genome_id": proposal.parent_genome_id or str(genome.get("id", "")),
        }
    )
    child = validate_genome_blocks(child)
    diffs = _diff(before, child, proposal)
    child["_ga_metadata"]["diffs"] = diffs
    return child, diffs


def _is_protected_rule(rule: str) -> bool:
    normalized = " ".join(str(rule).lower().split())
    return any(marker in normalized for marker in PROTECTED_RULE_MARKERS)


def _dedupe_and_limit_rules(rules: list[Any], *, limit: int) -> list[str]:
    deduped: list[str] = []
    protected: list[str] = []
    seen: set[str] = set()
    for rule in rules:
        text = str(rule).strip()
        if not text:
            continue
        key = " ".join(text.lower().split())
        if key in seen:
            continue
        seen.add(key)
        if _is_protected_rule(text):
            protected.append(text)
        else:
            deduped.append(text)
    selected = protected + deduped[: max(0, int(limit) - len(protected))]
    return selected or deduped[: max(0, int(limit))]


def _diff(before: dict[str, Any], after: dict[str, Any], proposal: MutationProposal) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fields = [
        ("blocks", before.get("blocks"), after.get("blocks")),
        ("params", before.get("params"), after.get("params")),
        ("block_params", before.get("block_params"), after.get("block_params")),
    ]
    for field, old, new in fields:
        if old != new:
            rows.append(
                {
                    "block_id": proposal.target_block_id or "genome",
                    "field": field,
                    "old_value": json.dumps(old, ensure_ascii=False, sort_keys=True),
                    "new_value": json.dumps(new, ensure_ascii=False, sort_keys=True),
                    "mutation_type": proposal.operator,
                    "mutation_family": proposal.mutation_family,
                    "compression_level": proposal.compression_level,
                    "selected_compression_target": proposal.selected_compression_target,
                    "selected_block_id": proposal.selected_block_id,
                    "selected_block_ids": json.dumps(proposal.selected_block_ids, ensure_ascii=False),
                    "expected_token_delta": proposal.expected_token_delta or proposal.estimated_token_delta,
                    "feedback_driven": proposal.source in {"det_feedback", "advisor"},
                    "llm_advised": proposal.source == "advisor",
                    "advisor_proposal_id": proposal.advisor_proposal_id or (proposal.proposal_id if proposal.source == "advisor" else ""),
                    "advisor_batch_id": proposal.advisor_batch_id if proposal.source == "advisor" else "",
                    "failure_type_source": "|".join(proposal.affected_failure_families),
                }
            )
    return rows
