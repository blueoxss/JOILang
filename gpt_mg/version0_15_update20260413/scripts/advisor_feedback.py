#!/usr/bin/env python3
"""Generation-level batch feedback for the cloud mutation advisor.

This module builds ONE structured feedback packet per generation (not one
message per row), constructs a deterministic advisor prompt from it, validates
the advisor's structured proposals, and applies accepted proposals to parent
genomes to create real advisor child genomes.

The cloudless DET-feedback path and the cloud-advisor path share the same
deterministic failure -> prompt-block reasoning (`category_feedback`) so the
A/B comparison is experimentally defensible.
"""
from __future__ import annotations

import hashlib
import json
import statistics
from collections import Counter
from typing import Any

from scripts.ga_metrics import DET_PASS_THRESHOLD, category_group
from scripts.ga_mutation import apply_mutation_proposal
from scripts.mutation_proposals import (
    MutationProposal,
    PROPOSAL_STATE_PROPOSED,
    PROPOSAL_STATE_REJECTED,
    proposal_from_advisor,
)
from utils.prompt_surgery_rules import base_failure_reason, get_prompt_surgery_rule


# Mutation operators the GA can actually apply to a prompt-block genome.
# Anything outside this set is rejected at validation time.
SUPPORTED_ADVISOR_MUTATION_TYPES = {
    "add_micro_rule",
    "strengthen_rule",
    "add_schema_grounding_rule",
    "add_canonical_service_name_rule",
    "strengthen_enum_type_rule",
    "strengthen_temporal_rule",
    "activate_or_strengthen_temporal_rule",
    "activate_temporal_skeleton",
    "strengthen_owner_device_rule",
    "add_sensor_to_action_flow_rule",
    "strengthen_skeleton_rule",
    "strengthen_minimality_rule",
    "strengthen_no_unrelated_action_rule",
    "strengthen_json_only_rule",
    "add_targeted_repair_hint",
    "merge_duplicate_micro_rules",
    "prune_stale_micro_rules",
    "template_compress_rule_family",
    "reduce_few_shot_count",
    "drop_optional_block",
    "drop_optional_blocks_for_budget",
    "reduce_candidate_strategies",
    "compress_candidate_strategies_to_minimal",
    "lower_output_max_tokens",
    "lower_output_max_tokens_safe",
    "lower_output_max_tokens_aggressive",
    "reduce_few_shot_count_to_zero",
    "reduce_few_shot_count_by_one",
    "prune_micro_rules_to_top_k",
    "prune_micro_rules_to_top_k_safe",
    "compact_reasoning_skeleton",
    "compact_block_params",
    "compact_block_params_safe",
    "dedupe_duplicate_micro_rules",
    "remove_redundant_hint_lines",
    "multi_block_compression_plan",
    "global_render_budget_down",
    "category_example_budget_down",
    "service_context_render_budget_down",
    "compact_service_schema_fields",
    "dedupe_service_value_enums",
    "drop_unused_device_capabilities",
}

ADVISOR_COMPRESSION_MUTATION_TYPES = {
    "drop_optional_block",
    "drop_optional_blocks_for_budget",
    "reduce_candidate_strategies",
    "compress_candidate_strategies_to_minimal",
    "lower_output_max_tokens",
    "lower_output_max_tokens_safe",
    "lower_output_max_tokens_aggressive",
    "reduce_few_shot_count",
    "reduce_few_shot_count_to_zero",
    "reduce_few_shot_count_by_one",
    "merge_duplicate_micro_rules",
    "dedupe_duplicate_micro_rules",
    "prune_stale_micro_rules",
    "prune_micro_rules_to_top_k",
    "prune_micro_rules_to_top_k_safe",
    "template_compress_rule_family",
    "compact_reasoning_skeleton",
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

RULE_ADDING_MUTATION_TYPES = {
    "add_micro_rule",
    "strengthen_rule",
    "add_schema_grounding_rule",
    "add_canonical_service_name_rule",
    "strengthen_enum_type_rule",
    "strengthen_temporal_rule",
    "strengthen_owner_device_rule",
    "add_sensor_to_action_flow_rule",
    "strengthen_skeleton_rule",
    "strengthen_minimality_rule",
    "strengthen_no_unrelated_action_rule",
    "strengthen_json_only_rule",
    "add_targeted_repair_hint",
}

# Operators that would remove protected output-schema / safety constraints.
PROTECTED_REMOVAL_OPERATORS = {
    "remove_core_block",
    "block_deactivation",
    "block_replacement",
    "drop_output_schema",
    "remove_json_rule",
    "remove_safety_rule",
}

PROTECTED_RULE_MARKERS = (
    "return exactly one json",
    "json object only",
    "do not include reasoning",
    "never emit markdown",
    "required keys",
    "name, cron, period",
)

RETRIEVAL_MARKERS = (
    "retrieval",
    "top-k",
    "topk",
    "service-context",
    "service context",
    "premapping",
    "pre-mapping",
)

# Coarse mutation-family token (matches ga_mutation.FAMILY_RATIOS) per block family.
_FAMILY_TO_MUTATION_FAMILY = {
    "Service_Mapping": "accuracy_repair",
    "Enum_Grounding": "accuracy_repair",
    "Owner_Device_Rule": "accuracy_repair",
    "Output_Schema": "accuracy_repair",
    "Skeleton": "accuracy_repair",
    "DET_Helper": "accuracy_repair",
    "Temporal_Rule": "temporal_reasoning",
    "Dataflow": "temporal_reasoning",
    "Minimality": "compression",
}

# Category-level reasoning maps a dominant DET failure to ONE prompt-block family.
# Several block-06 failure modes (temporal + dataflow) are bucketed under
# Temporal_Rule at the category level because they share block 06 ownership.
_CATEGORY_FAMILY_MAP = {
    "invalid_json": "Output_Schema",
    "schema_missing_keys": "Output_Schema",
    "schema_violation": "Service_Mapping",
    "unknown_service": "Service_Mapping",
    "service_match": "Service_Mapping",
    "gt_service_coverage": "Service_Mapping",
    "arg_type": "Enum_Grounding",
    "enum_grounding": "Enum_Grounding",
    "enum_type_mismatch": "Enum_Grounding",
    "numeric_grounding": "Temporal_Rule",
    "temporal_error": "Temporal_Rule",
    "dataflow": "Temporal_Rule",
    "dataflow_error": "Temporal_Rule",
    "gt_receiver_coverage": "Owner_Device_Rule",
    "owner_device_mismatch": "Owner_Device_Rule",
    "extraneous": "Minimality",
    "extraneous_action": "Minimality",
    "semantic": "Skeleton",
    "gt_mismatch": "Skeleton",
}

_FAMILY_ISSUE_TEXT = {
    "Output_Schema": (
        "Failures are concentrated in JSON/output-schema validity; the prompt likely "
        "needs stronger JSON-only and required-key grounding."
    ),
    "Service_Mapping": (
        "Failures are concentrated in service/schema grounding; the prompt likely needs "
        "stronger canonical service-name and service_list grounding."
    ),
    "Enum_Grounding": (
        "Failures are concentrated in enum/argument-type grounding; the prompt likely needs "
        "stronger enum-literal and numeric-type grounding."
    ),
    "Temporal_Rule": (
        "Failures are concentrated in temporal/dataflow handling; the prompt likely confuses "
        "delay, period, duration, wait-until, and sensor-to-action binding."
    ),
    "Owner_Device_Rule": (
        "Failures are concentrated in receiver/owner-device coverage; the prompt likely needs "
        "stronger owner, location, and device selector binding."
    ),
    "Minimality": (
        "The prompt is over-generating actions and needs minimality / no-unrelated-action "
        "strengthening."
    ),
    "Skeleton": (
        "Failures are concentrated in semantic/skeleton mismatch; the prompt likely needs "
        "stronger skeleton decomposition and owner-device binding."
    ),
    "DET_Helper": (
        "Failures are schema-valid but not target-equivalent; the prompt needs a targeted "
        "repair hint toward receiver, service, dataflow, numeric, and enum grounding."
    ),
}


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _row_passes(row: dict[str, Any]) -> bool:
    return bool(row.get("det_gt_exact")) or float(row.get("det_score") or 0.0) >= DET_PASS_THRESHOLD


def _failure_histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        reasons = row.get("failure_reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        for reason in reasons:
            counter[base_failure_reason(reason)] += 1
    return dict(counter.most_common())


def category_feedback(failure_histogram: dict[str, int]) -> dict[str, Any]:
    """Deterministically map a failure histogram to prompt-block guidance.

    Shared by both the cloudless mutation path and the advisor batch builder so
    the two feedback regimes reason about failures identically.
    """
    cleaned = {base_failure_reason(key): int(value) for key, value in (failure_histogram or {}).items() if int(value or 0) > 0}
    if not cleaned:
        return {
            "dominant_failure_type": "",
            "likely_prompt_issue": "No deterministic failures observed; prompt grounding looks adequate.",
            "recommended_mutation_family": "diversity",
            "suggested_target_block": "06",
            "suggested_target_block_family": "DET_Helper",
            "suggested_mutation_type": "add_targeted_repair_hint",
        }
    dominant = max(cleaned.items(), key=lambda item: (item[1], item[0]))[0]
    det_rule = get_prompt_surgery_rule(dominant)
    family = _CATEGORY_FAMILY_MAP.get(dominant, str(det_rule.get("affected_block_family") or "DET_Helper"))
    return {
        "dominant_failure_type": str(det_rule.get("failure_type") or dominant),
        "likely_prompt_issue": _FAMILY_ISSUE_TEXT.get(family, _FAMILY_ISSUE_TEXT["DET_Helper"]),
        "recommended_mutation_family": _FAMILY_TO_MUTATION_FAMILY.get(family, "accuracy_repair"),
        "suggested_target_block": str(det_rule.get("prompt_block_id") or "06"),
        "suggested_target_block_family": family,
        "suggested_mutation_type": str(det_rule.get("suggested_mutation_type") or "add_targeted_repair_hint"),
    }


def _row_failures(item: dict[str, Any]) -> list[dict[str, Any]]:
    genome_id = str((item.get("genome") or {}).get("id", ""))
    rows = list((item.get("validation_metrics") or {}).get("rows") or [])
    return [{**row, "genome_id": genome_id} for row in rows]


def build_category_diagnostics(
    evaluated_population: list[dict[str, Any]],
    *,
    generation: int,
    model_key: str,
    max_representative_failures_per_category: int = 2,
    include_candidate_code: bool = False,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in evaluated_population:
        for row in _row_failures(item):
            category = str(row.get("category", "") or "uncategorized")
            buckets.setdefault(category, []).append(row)
    diagnostics: list[dict[str, Any]] = []
    for category, rows in sorted(buckets.items(), key=lambda kv: kv[0]):
        scores = [float(row.get("det_score") or 0.0) for row in rows]
        pass_count = sum(1 for row in rows if _row_passes(row))
        histogram = _failure_histogram(rows)
        guidance = category_feedback(histogram)
        failed_rows = [row for row in rows if not _row_passes(row)]
        representatives = _representative_payload(
            failed_rows[:max_representative_failures_per_category],
            include_candidate_code=include_candidate_code,
        )
        diagnostics.append(
            {
                "generation": generation,
                "model_key": model_key,
                "category": _coerce_category(category),
                "group": category_group(category),
                "row_count": len(rows),
                "det_pass_count": pass_count,
                "det_pass_rate": round((pass_count / len(rows)) * 100.0, 4) if rows else 0.0,
                "avg_det_score": round(statistics.fmean(scores), 4) if scores else 0.0,
                "failure_histogram": histogram,
                "dominant_failure_type": guidance["dominant_failure_type"],
                "likely_prompt_issue": guidance["likely_prompt_issue"],
                "recommended_mutation_family": guidance["recommended_mutation_family"],
                "suggested_target_block": guidance["suggested_target_block"],
                "suggested_target_block_family": guidance["suggested_target_block_family"],
                "suggested_mutation_type": guidance["suggested_mutation_type"],
                "representative_failures": representatives,
            }
        )
    return diagnostics


def build_group_diagnostics(category_diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {"basic": [], "temporal": [], "complex": []}
    for diag in category_diagnostics:
        group = str(diag.get("group", ""))
        if group in groups:
            groups[group].append(diag)
    summary: dict[str, Any] = {}
    for group, diags in groups.items():
        if not diags:
            summary[group] = {
                "categories": [],
                "row_count": 0,
                "det_pass_count": 0,
                "det_pass_rate": 0.0,
                "avg_det_score": 0.0,
                "failure_histogram": {},
                "dominant_failure_type": "",
                "likely_prompt_issue": "",
                "recommended_mutation_family": "",
            }
            continue
        row_count = sum(int(diag.get("row_count") or 0) for diag in diags)
        pass_count = sum(int(diag.get("det_pass_count") or 0) for diag in diags)
        merged_hist: Counter[str] = Counter()
        for diag in diags:
            for key, value in (diag.get("failure_histogram") or {}).items():
                merged_hist[key] += int(value or 0)
        guidance = category_feedback(dict(merged_hist))
        score_values = [float(diag.get("avg_det_score") or 0.0) for diag in diags]
        summary[group] = {
            "categories": [diag.get("category") for diag in diags],
            "row_count": row_count,
            "det_pass_count": pass_count,
            "det_pass_rate": round((pass_count / row_count) * 100.0, 4) if row_count else 0.0,
            "avg_det_score": round(statistics.fmean(score_values), 4) if score_values else 0.0,
            "failure_histogram": dict(merged_hist.most_common()),
            "dominant_failure_type": guidance["dominant_failure_type"],
            "likely_prompt_issue": guidance["likely_prompt_issue"],
            "recommended_mutation_family": guidance["recommended_mutation_family"],
        }
    return summary


def _coerce_category(category: Any) -> Any:
    token = str(category or "").strip()
    return int(token) if token.isdigit() else token


def _representative_payload(rows: list[dict[str, Any]], *, include_candidate_code: bool) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for row in rows:
        reasons = row.get("failure_reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        bases = [base_failure_reason(reason) for reason in reasons]
        guidance = category_feedback(Counter(bases)) if bases else category_feedback({})
        entry = {
            "row_id": row.get("row_no", ""),
            "category": _coerce_category(row.get("category", "")),
            "group": category_group(row.get("category", "")),
            "command": row.get("command_eng", ""),
            "expected": row.get("gt", ""),
            "candidate": row.get("output", ""),
            "failure_reasons": list(reasons),
            "failure_type": guidance["dominant_failure_type"],
            "receiver_mismatch": any("receiver" in str(reason) or "owner_device" in str(reason) for reason in bases),
            "service_mismatch": any(reason in {"unknown_service", "service_match", "schema_violation", "gt_service_coverage"} for reason in bases),
            "enum_mismatch": any(reason in {"arg_type", "enum_grounding", "enum_type_mismatch"} for reason in bases),
            "temporal_mismatch": any(reason in {"temporal_error", "numeric_grounding"} for reason in bases),
            "dataflow_mismatch": any(reason in {"dataflow", "dataflow_error"} for reason in bases),
            "extraneous_action": any(reason in {"extraneous", "extraneous_action"} for reason in bases),
            "missing_action": any(reason in {"gt_service_coverage", "gt_receiver_coverage"} for reason in bases),
            "diagnostic_summary": guidance["likely_prompt_issue"],
            "suggested_prompt_block": guidance["suggested_target_block"],
            "suggested_mutation_type": guidance["suggested_mutation_type"],
        }
        if include_candidate_code:
            entry["candidate_code"] = row.get("output", "")
        payload.append(entry)
    return payload


def select_representative_failures(
    evaluated_population: list[dict[str, Any]],
    *,
    max_failures: int = 10,
    include_candidate_code: bool = False,
    already_fixed_families: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Select up to `max_failures` diverse, high-signal failures for the advisor.

    Prioritises bottom-genome failures, repeated failures, and failures not yet
    addressed by cloudless feedback, while covering diverse categories/groups.
    """
    already_fixed_families = {str(item) for item in (already_fixed_families or set())}
    # Bottom genomes first (population is expected sorted best->worst).
    ordered = list(reversed(evaluated_population))
    reason_frequency: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for item in ordered:
        for row in _row_failures(item):
            if _row_passes(row):
                continue
            reasons = row.get("failure_reasons") or []
            if isinstance(reasons, str):
                reasons = [reasons]
            bases = [base_failure_reason(reason) for reason in reasons]
            for base in bases:
                reason_frequency[base] += 1
            candidates.append({"row": row, "bases": bases})
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[Any, Any]] = set()
    covered_groups: set[str] = set()
    covered_failure_types: set[str] = set()

    def score(entry: dict[str, Any]) -> tuple[int, int, int]:
        bases = entry["bases"]
        guidance_family = category_feedback(Counter(bases))["suggested_target_block_family"] if bases else ""
        not_fixed = 0 if guidance_family in already_fixed_families else 1
        frequency = max((reason_frequency.get(base, 0) for base in bases), default=0)
        return (not_fixed, frequency, len(bases))

    ranked = sorted(candidates, key=score, reverse=True)
    for entry in ranked:
        if len(selected) >= max_failures:
            break
        row = entry["row"]
        key = (row.get("genome_id", ""), row.get("row_no", ""))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        selected.append(entry)
    # Re-rank the chosen ones to maximise group/failure-type diversity.
    diverse: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    for entry in selected:
        row = entry["row"]
        group = category_group(row.get("category", ""))
        ftype = category_feedback(Counter(entry["bases"]))["dominant_failure_type"] if entry["bases"] else ""
        if group not in covered_groups or ftype not in covered_failure_types:
            covered_groups.add(group)
            covered_failure_types.add(ftype)
            diverse.append(entry)
        else:
            deferred.append(entry)
    final_rows = [entry["row"] for entry in (diverse + deferred)][:max_failures]
    return _representative_payload(final_rows, include_candidate_code=include_candidate_code)


def advisor_batch_id(generation: int, model_key: str) -> str:
    digest = hashlib.sha1(f"{model_key}:{generation}".encode("utf-8")).hexdigest()[:8]
    return f"advisor_batch_g{generation:03d}_{digest}"


def _genome_prompt_summary(genome: dict[str, Any], *, prompt_token_count: float) -> dict[str, Any]:
    block_params = genome.get("block_params", {}) or {}
    micro_rules_by_block = {
        block_id: list(params.get("micro_rules") or [])
        for block_id, params in block_params.items()
        if params.get("micro_rules")
    }
    block_params_summary = {
        block_id: {key: value for key, value in params.items() if key != "micro_rules"}
        for block_id, params in block_params.items()
    }
    payload = {
        "blocks": list(genome.get("blocks") or []),
        "params": genome.get("params", {}),
        "block_params": block_params,
    }
    block_signature = ",".join(str(block) for block in genome.get("blocks") or [])
    prompt_hash = hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return {
        "genome_id": str(genome.get("id", "")),
        "blocks": list(genome.get("blocks") or []),
        "params": genome.get("params", {}),
        "block_params_summary": block_params_summary,
        "micro_rules_by_block": micro_rules_by_block,
        "prompt_token_count": round(float(prompt_token_count or 0.0), 2),
        "block_signature": block_signature,
        "prompt_hash": prompt_hash,
    }


def build_advisor_feedback_batch(
    *,
    generation: int,
    model_key: str,
    advisor_model_key: str,
    evaluated_population: list[dict[str, Any]],
    categories: list[Any],
    limit_per_category: Any,
    sample_size: int,
    validation_size: int,
    generation_phase: str,
    plateau_type: str,
    next_action: str,
    overall: dict[str, Any],
    cloudless_feedback_summary: dict[str, Any],
    best_genome_metric: Any | None,
    max_representative_failures: int = 10,
    include_candidate_code: bool = False,
    include_prompt_summary: bool = True,
    already_fixed_families: set[str] | None = None,
    compression_detpass_threshold: float = 90.0,
    compression_token_reduction_target: float = 0.15,
    allow_aggressive_compression: bool = False,
    compression_ready: bool = False,
    compression_phase: str = "ACCURACY_SEARCH",
    prompt_token_breakdown: dict[str, Any] | None = None,
    block_token_breakdown: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    batch_id = advisor_batch_id(generation, model_key)
    category_diagnostics = build_category_diagnostics(
        evaluated_population,
        generation=generation,
        model_key=model_key,
        include_candidate_code=include_candidate_code,
    )
    group_diagnostics = build_group_diagnostics(category_diagnostics)
    representative_failures = select_representative_failures(
        evaluated_population,
        max_failures=max_representative_failures,
        include_candidate_code=include_candidate_code,
        already_fixed_families=already_fixed_families,
    )
    best = evaluated_population[0]["genome"] if evaluated_population else {}
    prompt_token_count = float(getattr(best_genome_metric, "avg_prompt_tokens", 0.0) or 0.0)
    current_prompt_artifact = (
        _genome_prompt_summary(best, prompt_token_count=prompt_token_count) if include_prompt_summary and best else {}
    )

    def genome_card(item: dict[str, Any], rank: int) -> dict[str, Any]:
        metric = item.get("redesign_metrics")
        genome = item.get("genome") or {}
        return {
            "rank": rank,
            "genome_id": str(genome.get("id", "")),
            "det_pass_rate": float(getattr(metric, "validation_det_pass_rate", 0.0) or 0.0),
            "avg_det_score": float(getattr(metric, "validation_avg_det_score", 0.0) or 0.0),
            "avg_prompt_tokens": float(getattr(metric, "avg_prompt_tokens", 0.0) or 0.0),
            "blocks": list(genome.get("blocks") or []),
        }

    top_genomes = [genome_card(item, idx) for idx, item in enumerate(evaluated_population[:3], start=1)]
    bottom_slice = list(reversed(evaluated_population[-3:])) if evaluated_population else []
    bottom_genomes = [genome_card(item, idx) for idx, item in enumerate(bottom_slice, start=1)]
    pareto_candidates = [
        card
        for card, item in zip(top_genomes, evaluated_population[:3])
        if getattr(item.get("redesign_metrics"), "pareto_frontier_member", False)
    ]
    compact_candidates = sorted(
        (card for card in top_genomes if card["avg_prompt_tokens"] > 0),
        key=lambda card: card["avg_prompt_tokens"],
    )[:2]
    prompt_token_breakdown = prompt_token_breakdown or {}
    block_token_breakdown = block_token_breakdown or []

    return {
        "advisor_batch_id": batch_id,
        "generation": generation,
        "model_key": model_key,
        "advisor_model_key": advisor_model_key,
        "categories": [_coerce_category(cat) for cat in categories],
        "limit_per_category": limit_per_category,
        "sample_size": sample_size,
        "validation_size": validation_size,
        "generation_phase": generation_phase,
        "plateau_type": plateau_type,
        "next_action": next_action,
        "overall": overall,
        "category_diagnostics": category_diagnostics,
        "group_diagnostics": group_diagnostics,
        "genome_diagnostics": {
            "top_genomes": top_genomes,
            "bottom_genomes": bottom_genomes,
            "pareto_candidates": pareto_candidates,
            "compact_candidates": compact_candidates,
        },
        "representative_failures": representative_failures,
        "current_prompt_artifact": current_prompt_artifact,
        "prompt_token_breakdown": prompt_token_breakdown,
        "block_token_breakdown": block_token_breakdown,
        "cloudless_feedback_summary": cloudless_feedback_summary,
        "advisor_request": {
            "goal": "Generate structured mutation proposals for the next generation.",
            "allowed_mutation_types": sorted(SUPPORTED_ADVISOR_MUTATION_TYPES),
            "compression_policy": {
                "activate_when_detpass_ge": compression_detpass_threshold,
                "compression_ready": bool(compression_ready),
                "compression_phase": compression_phase,
                "prefer_compression_if_accuracy_saturated": True,
                "target_token_reduction_ratio": compression_token_reduction_target,
                "allow_aggressive_compression": bool(allow_aggressive_compression),
                "preserve_core_blocks": True,
                "preserve_output_schema": True,
                "preserve_service_mapping": True,
            },
            "constraints": [
                "Do not rewrite the whole prompt.",
                "Return structured JSON proposals only.",
                "Prefer compact targeted changes.",
                "Do not remove safety/output schema constraints.",
                "Every proposal must specify target block/family and affected failure family.",
                "If compression is proposed, specify expected token reduction and regression risk.",
            ],
        },
    }


def build_advisor_prompt_from_batch(batch: dict[str, Any], *, detail: str = "normal") -> str:
    detail = str(detail or "normal").lower()
    max_failures = {"compact": 3, "normal": 8, "verbose": 20}.get(detail, 8)
    packet = json.loads(json.dumps(batch, ensure_ascii=False))
    packet["representative_failures"] = packet.get("representative_failures", [])[:max_failures]
    if detail == "compact":
        packet.pop("current_prompt_artifact", None)
        packet.pop("group_diagnostics", None)
    compression_policy = (batch.get("advisor_request") or {}).get("compression_policy") or {}
    compression_phase = str(compression_policy.get("compression_phase") or "ACCURACY_SEARCH")
    required_schema = {
        "advisor_status": "accepted",
        "compression_policy": compression_policy,
        "prompt_token_breakdown_seen": True,
        "block_token_breakdown_seen": True,
        "proposals": [
            {
                "proposal_id": "g{:03d}_01".format(int(batch.get("generation", 0) or 0)),
                "target_block_id": "02",
                "target_block_family": "Service_Mapping",
                "mutation_family": "accuracy_repair",
                "mutation_type": "add_micro_rule",
                "priority": 1,
                "reason": "short reason",
                "affected_failure_families": ["schema_violation", "unknown_service"],
                "category_scope": [1, 2],
                "group_scope": ["basic"],
                "proposed_micro_rule": "concise rule text",
                "expected_effect": "what the change should fix",
                "expected_token_delta": 12,
                "regression_risk": 0.2,
                "apply_mode": "create_child",
            },
            {
                "proposal_id": "g{:03d}_compress_01".format(int(batch.get("generation", 0) or 0)),
                "target_block_id": "genome",
                "target_block_family": "Compression",
                "mutation_family": "compression",
                "mutation_type": "compress_candidate_strategies_to_minimal",
                "priority": 3,
                "reason": "Accuracy is saturated; reduce prompt token cost.",
                "affected_failure_families": ["token_overbudget"],
                "category_scope": [1, 2],
                "group_scope": ["basic"],
                "proposed_micro_rule": "",
                "expected_effect": "Reduce prompt tokens while preserving schema/service grounding.",
                "expected_token_delta": -1000,
                "regression_risk": 0.25,
                "apply_mode": "create_child",
            }
        ],
        "micro_compression_proposals": [
            {
                "proposal_id": "g{:03d}_micro_01".format(int(batch.get("generation", 0) or 0)),
                "mutation_family": "compression",
                "compression_level": "micro",
                "target_block_id": "genome",
                "target_block_family": "Compression",
                "mutation_type": "dedupe_duplicate_micro_rules",
                "expected_token_delta": -80,
                "regression_risk": 0.05,
            }
        ],
        "block_compression_proposals": [
            {
                "proposal_id": "g{:03d}_block_01".format(int(batch.get("generation", 0) or 0)),
                "mutation_family": "compression",
                "compression_level": "block",
                "selected_block_id": "06",
                "selected_block_family": "DET_Helper",
                "exact_mutation_operator": "prune_micro_rules_to_top_k",
                "original_token_estimate": 5200,
                "proposed_token_estimate_after": 2600,
                "expected_token_delta": -2600,
                "preserved_content": ["validator-critical JSON/service/temporal rules"],
                "removable_content": ["duplicate or tutorial-style rules"],
                "why_safe": "The selected block is non-core and keeps validator-critical constraints.",
                "regression_risk": 0.2,
                "validation_requirement": "strict DETPass gate",
            }
        ],
        "multi_block_compression_proposals": [
            {
                "proposal_id": "g{:03d}_multi_01".format(int(batch.get("generation", 0) or 0)),
                "mutation_family": "compression",
                "compression_level": "multi_block",
                "selected_block_ids": ["05", "06"],
                "exact_mutation_operator": "multi_block_compression_plan",
                "steps": [
                    {"block_id": "06", "operator": "prune_micro_rules_to_top_k", "k": 3},
                    {"block_id": "05", "operator": "compact_block_params"},
                ],
                "total_expected_token_delta": -3300,
                "regression_risk": 0.35,
            }
        ],
        "global_budget_compression_proposals": [],
    }
    # The advisor prompt is phase-aware.
    # Below threshold it prioritizes correctness; after threshold it receives token/block
    # breakdowns, and in aggressive mode it may add multi-block/global plans.
    advisor_case_lines = {
        "ACCURACY_SEARCH": [
            "Advisor Case A: DETPass is below threshold or accuracy-first.",
            "- Focus on correctness and DET repair.",
            "- Optional micro compression is allowed only when it is not a no-op.",
            "- Do not propose aggressive block deletion.",
        ],
        "COMPRESSION_READY": [
            "Advisor Case B: DETPass is above threshold.",
            "- Inspect prompt_token_breakdown and block_token_breakdown.",
            "- Select at least one large non-protected block-level target if available.",
            "- Include selected_block_id, preserved/removable content, expected_token_delta, and regression_risk.",
        ],
        "AGGRESSIVE_COMPRESSION": [
            "Advisor Case C: threshold is met and plateau/token plateau is active.",
            "- Keep block compression active; multi-block/global proposals are additive.",
            "- Prioritize largest non-protected token components and avoid tiny deltas.",
            "- DETPass remains a hard validation gate.",
        ],
    }.get(compression_phase, [])
    lines = [
        "You are a prompt-block mutation advisor for a JOILang code-generation system.",
        "You receive ONE generation-level feedback packet describing DET evaluation results.",
        "Return ONLY a JSON object that matches required_response_schema. No prose, no markdown.",
        "Rules:",
        "- Do not rewrite the whole prompt; propose compact, targeted prompt-block edits only.",
        "- Do not remove safety or output-schema constraints.",
        "- Do not mutate retrieval / pre-mapping / service-context construction.",
        "- Every proposal must name target_block_id, target_block_family, and affected_failure_families.",
        "- Use only allowed_mutation_types from the packet.",
        *advisor_case_lines,
        "- If best DETPass is above compression threshold, prioritize token-reducing mutations.",
        "- When accuracy is saturated, propose at least one compression mutation unless regression risk is high.",
        "- Prefer reducing few-shot count, duplicate micro-rules, candidate strategies, optional blocks, and max output tokens before adding new rules.",
        "- Compression proposals must include expected_token_delta as a negative number.",
        "- Do not repeat no-op compression, such as compress_candidate_strategies_to_minimal when strategies are already [\"minimal\"].",
        "- Do not remove output schema, JSON-only rules, core blocks, service mapping, retrieval, pre-mapping, or service-context construction.",
        "",
        "feedback_packet:",
        json.dumps(packet, ensure_ascii=False, indent=2),
        "",
        "required_response_schema:",
        json.dumps(required_schema, ensure_ascii=False, indent=2),
    ]
    return "\n".join(lines)


def validate_advisor_proposal(
    raw: dict[str, Any],
    *,
    valid_blocks: set[str],
    core_blocks: set[str],
    existing_rules: set[str] | None = None,
    max_token_expansion: int = 60,
    current_genome: dict[str, Any] | None = None,
    block_token_breakdown: list[dict[str, Any]] | None = None,
    min_compression_token_delta: int = 32,
) -> tuple[bool, str]:
    existing_rules = {str(rule).strip().lower() for rule in (existing_rules or set())}
    current_genome = current_genome or {}
    block_token_breakdown = block_token_breakdown or []
    block_id = str(raw.get("selected_block_id") or raw.get("target_block_id", "") or "").strip()
    family = str(raw.get("selected_block_family") or raw.get("target_block_family", "") or "").strip()
    mutation_type = str(raw.get("exact_mutation_operator") or raw.get("mutation_type", "") or raw.get("operator", "") or "").strip()
    micro_rule = str(raw.get("proposed_micro_rule", "") or "").strip()
    affected = raw.get("affected_failure_families") or []
    mutation_family = str(raw.get("mutation_family", "") or "").strip()
    is_compression = mutation_family == "compression" or mutation_type in ADVISOR_COMPRESSION_MUTATION_TYPES
    compression_level = str(raw.get("compression_level") or "").strip()
    selected_block_ids = [
        str(value)
        for value in (raw.get("selected_block_ids") or raw.get("target_units") or [])
        if str(value).strip()
    ]

    text_blob = json.dumps(raw, ensure_ascii=False).lower()
    if any(marker in text_blob for marker in RETRIEVAL_MARKERS):
        return False, "proposal attempted to mutate retrieval/pre-mapping context"
    if not block_id or not family:
        return False, "missing target block id or block family"
    if block_id == "genome" and not is_compression:
        return False, "genome pseudo-target is only allowed for compression proposals"
    if block_id not in valid_blocks and not (is_compression and block_id == "genome"):
        return False, "proposal targets unknown block that cannot be created safely"
    if not mutation_type:
        return False, "missing mutation type"
    if mutation_type in PROTECTED_REMOVAL_OPERATORS or (
        block_id in core_blocks and mutation_type in {"block_deactivation", "block_replacement", "remove_core_block"}
    ):
        return False, "proposal attempted to remove or replace a protected/core block"
    if is_compression and mutation_type in {"drop_optional_block", "drop_optional_blocks_for_budget", "block_deactivation"}:
        if block_id in core_blocks or block_id == "03" or family in {"Core_System", "Service_Mapping", "Output_Schema"}:
            return False, "proposal attempted to remove a protected/core/schema block"
    if is_compression and compression_level == "block" and not block_id:
        return False, "block-level compression proposal missing selected_block_id"
    if is_compression and compression_level == "multi_block" and not selected_block_ids:
        return False, "multi-block compression proposal missing selected_block_ids"
    if mutation_type not in SUPPORTED_ADVISOR_MUTATION_TYPES:
        return False, f"unsupported mutation type: {mutation_type}"
    if is_compression and any(
        marker in text_blob
        for marker in ("remove json", "drop json", "remove output schema", "drop output schema", "ignore schema")
    ):
        return False, "proposal attempted to remove a protected output-schema/safety rule"
    if any(marker in micro_rule.lower() for marker in ("remove json", "drop json", "do not return json", "ignore schema")):
        return False, "proposal attempted to remove a protected output-schema/safety rule"
    if mutation_type in RULE_ADDING_MUTATION_TYPES and not micro_rule:
        return False, "missing proposed_micro_rule"
    if "(#" in micro_rule or ")." in micro_rule:
        return False, "proposal appears to generate JOILang code instead of a prompt mutation"
    if micro_rule and micro_rule.lower() in existing_rules:
        return False, "duplicates an existing micro-rule exactly"
    if not affected:
        if not is_compression:
            return False, "proposal missing affected_failure_families"
        raw["affected_failure_families"] = ["token_overbudget"]
    # Reject no-op compression proposals before scheduling children.
    # This prevents repeated tiny genome mutations; compression-ready generations can
    # still trigger a stronger safe fallback after rejection.
    if is_compression:
        params = current_genome.get("params") or {}
        block_params = current_genome.get("block_params") or {}
        if mutation_type == "compress_candidate_strategies_to_minimal" and list(params.get("candidate_strategies") or []) == ["minimal"]:
            return False, "no-op compression: candidate_strategies already minimal"
        if mutation_type == "reduce_few_shot_count_to_zero":
            target = block_params.get(block_id, {}) if block_id and block_id != "genome" else {}
            if target and int(target.get("few_shot_count") or 0) <= 0:
                return False, "no-op compression: few_shot_count already zero"
        if mutation_type in {"reduce_few_shot_count", "reduce_few_shot_count_by_one"}:
            target = block_params.get(block_id, {}) if block_id and block_id != "genome" else {}
            if target and int(target.get("few_shot_count") or 0) <= int(raw.get("target_count") or 0):
                return False, "no-op compression: few_shot_count already below target"
        if mutation_type == "lower_output_max_tokens_aggressive" and int(params.get("max_tokens") or 768) <= 256:
            return False, "no-op compression: max_tokens already at lower bound"
        token_delta_key_present = "expected_token_delta" in raw or "total_expected_token_delta" in raw
        if not token_delta_key_present:
            return False, "compression proposal missing expected_token_delta"
    token_delta = int(raw.get("expected_token_delta") or raw.get("total_expected_token_delta") or 0)
    if is_compression and compression_level not in {"micro", ""} and abs(token_delta) < int(min_compression_token_delta):
        return False, "compression expected_token_delta too small for block/global proposal"
    if token_delta > max_token_expansion and not affected:
        return False, "token expansion too high without accuracy justification"
    return True, ""


def apply_advisor_proposal(
    parent_genome: dict[str, Any],
    proposal_raw: dict[str, Any],
    *,
    generation: int,
    advisor_batch_id_value: str,
    rng,
) -> tuple[dict[str, Any], list[dict[str, Any]], MutationProposal]:
    """Apply one accepted advisor proposal to a concrete parent genome.

    Returns (child_genome, block_diffs, mutation_proposal). The returned
    MutationProposal has non-empty parent_genome_id and child_genome_id and the
    child genome carries advisor provenance metadata.
    """
    mp = proposal_from_advisor(proposal_raw, generation=generation, advisor_batch_id=advisor_batch_id_value)
    mp.parent_genome_id = str(parent_genome.get("id", ""))
    child, diffs = apply_mutation_proposal(parent_genome, mp, rng=rng)
    mp.child_genome_id = str(child.get("id", ""))
    mp.actual_token_delta = 0
    child.setdefault("_ga_metadata", {})
    child["_ga_metadata"].update(
        {
            "source": "advisor",
            "advisor_used": True,
            "llm_advised": True,
            "advisor_proposal_id": mp.advisor_proposal_id,
            "advisor_batch_id": advisor_batch_id_value,
            "advisor_mutation_type": mp.operator,
            "mutation_family": mp.mutation_family,
            "mutation_operator": mp.operator,
        }
    )
    augmented = [{**diff, "advisor_batch_id": advisor_batch_id_value} for diff in diffs]
    child["_ga_metadata"]["diffs"] = augmented
    return child, augmented, mp


__all__ = [
    "SUPPORTED_ADVISOR_MUTATION_TYPES",
    "category_feedback",
    "build_category_diagnostics",
    "build_group_diagnostics",
    "select_representative_failures",
    "advisor_batch_id",
    "build_advisor_feedback_batch",
    "build_advisor_prompt_from_batch",
    "validate_advisor_proposal",
    "apply_advisor_proposal",
    "PROPOSAL_STATE_PROPOSED",
    "PROPOSAL_STATE_REJECTED",
]
