#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


# Advisor proposal lifecycle states. A proposal must always carry exactly one of
# these; `accepted=True` alone is never sufficient to mean "applied".
PROPOSAL_STATE_PROPOSED = "proposed"
PROPOSAL_STATE_ACCEPTED_APPLIED = "accepted_applied"
PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED = "accepted_not_scheduled"
PROPOSAL_STATE_ACCEPTED_POOL_ONLY = "accepted_pool_only"
PROPOSAL_STATE_REJECTED = "rejected"
PROPOSAL_STATE_FAILED_TO_APPLY = "failed_to_apply"

PROPOSAL_STATES = (
    PROPOSAL_STATE_PROPOSED,
    PROPOSAL_STATE_ACCEPTED_APPLIED,
    PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED,
    PROPOSAL_STATE_ACCEPTED_POOL_ONLY,
    PROPOSAL_STATE_REJECTED,
    PROPOSAL_STATE_FAILED_TO_APPLY,
)

ADVISOR_COMPRESSION_MUTATION_TYPES = {
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class MutationProposal:
    proposal_id: str
    source: str
    mutation_family: str
    operator: str
    mutation_type: str = ""
    target_units: list[str] = field(default_factory=list)
    target_block_id: str = ""
    target_block_family: str = ""
    replacement_text: str = ""
    estimated_token_delta: int = 0
    actual_token_delta: int = 0
    risk_score: float = 0.0
    affected_failure_families: list[str] = field(default_factory=list)
    expected_effect: str = ""
    requires_validation: bool = True
    accepted: bool = False
    rejection_reason: str = ""
    rollback_units: list[str] = field(default_factory=list)
    generation: int = 0
    parent_genome_id: str = ""
    child_genome_id: str = ""
    # --- advisor lifecycle / provenance (used by the cloud-advisor path) ---
    schema_source: str = ""
    proposal_state: str = PROPOSAL_STATE_PROPOSED
    advisor_batch_id: str = ""
    advisor_proposal_id: str = ""
    raw_response_path: str = ""
    advisor_prompt_path: str = ""
    category_scope: list[int] = field(default_factory=list)
    group_scope: list[str] = field(default_factory=list)
    priority: int = 0
    regression_risk: float = 0.0
    scheduling_reason: str = ""
    advisor_child_duplicate: bool = False
    duplicate_of: str = ""
    compression_level: str = ""
    compression_phase: str = ""
    selected_compression_target: str = ""
    selected_block_id: str = ""
    selected_block_ids: list[str] = field(default_factory=list)
    block_family: str = ""
    block_token_before: int = 0
    block_token_after_estimate: int = 0
    expected_token_delta: int = 0
    measured_prompt_token_delta: float = 0.0
    measured_prompt_token_delta_pct: float = 0.0
    fallback_reason: str = ""
    largest_token_component: str = ""
    preserved_content: list[str] = field(default_factory=list)
    removable_content: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["mutation_type"] = row.get("mutation_type") or row.get("operator", "")
        row["operator"] = row.get("operator") or row.get("mutation_type", "")
        for key in (
            "target_units",
            "affected_failure_families",
            "rollback_units",
            "category_scope",
            "group_scope",
            "selected_block_ids",
            "preserved_content",
            "removable_content",
        ):
            row[key] = json.dumps(row[key], ensure_ascii=False)
        return row


def proposal_from_advisor(
    raw: dict[str, Any],
    *,
    generation: int,
    advisor_batch_id: str = "",
) -> MutationProposal:
    affected = raw.get("affected_failure_families")
    if not affected:
        affected = [str(raw.get("target_block_family", ""))]
    category_scope = [int(value) for value in (raw.get("category_scope") or []) if str(value).strip().lstrip("-").isdigit()]
    group_scope = [str(value) for value in (raw.get("group_scope") or []) if str(value).strip()]
    proposal_id = str(raw.get("proposal_id", f"advisor_g{generation:03d}"))
    operator = str(
        raw.get("exact_mutation_operator")
        or raw.get("operator")
        or raw.get("mutation_type")
        or ("" if raw.get("rejection_reason") else "add_micro_rule")
    )
    mutation_family = str(raw.get("mutation_family") or "")
    if not mutation_family:
        mutation_family = "compression" if operator in ADVISOR_COMPRESSION_MUTATION_TYPES else "advisor_guided"
    selected_block_id = str(raw.get("selected_block_id") or raw.get("target_block_id") or "")
    selected_block_ids = [
        str(value)
        for value in (raw.get("selected_block_ids") or raw.get("block_ids") or raw.get("target_units") or [])
        if str(value).strip()
    ]
    compression_level = str(raw.get("compression_level") or "")
    if mutation_family == "compression" and not compression_level:
        if operator == "multi_block_compression_plan":
            compression_level = "multi_block"
        elif operator in {"global_render_budget_down", "category_example_budget_down", "service_context_render_budget_down"}:
            compression_level = "global_budget"
        elif selected_block_id and selected_block_id != "genome":
            compression_level = "block"
        else:
            compression_level = "micro"
    expected_token_delta = _safe_int(raw.get("expected_token_delta") or raw.get("total_expected_token_delta") or 0)
    return MutationProposal(
        proposal_id=proposal_id,
        source="advisor",
        mutation_family=mutation_family,
        operator=operator,
        mutation_type=str(raw.get("mutation_type") or operator),
        target_units=selected_block_ids,
        target_block_id=selected_block_id,
        target_block_family=str(raw.get("selected_block_family") or raw.get("target_block_family") or ""),
        replacement_text=str(raw.get("proposed_micro_rule") or raw.get("edit_instruction") or ""),
        estimated_token_delta=expected_token_delta,
        risk_score=_safe_float(raw.get("regression_risk") or raw.get("risk_score") or 0.2),
        affected_failure_families=[str(item) for item in affected if str(item).strip()],
        expected_effect=str(raw.get("expected_effect") or raw.get("reason", "")),
        generation=generation,
        accepted=bool(raw.get("accepted", True)),
        rejection_reason=str(raw.get("rejection_reason", "")),
        schema_source=str(raw.get("schema_source") or ""),
        proposal_state=str(raw.get("proposal_state") or PROPOSAL_STATE_PROPOSED),
        advisor_batch_id=str(raw.get("advisor_batch_id") or advisor_batch_id),
        advisor_proposal_id=proposal_id,
        raw_response_path=str(raw.get("raw_response_path") or ""),
        advisor_prompt_path=str(raw.get("advisor_prompt_path") or ""),
        category_scope=category_scope,
        group_scope=group_scope,
        priority=_safe_int(raw.get("priority") or 0),
        regression_risk=_safe_float(raw.get("regression_risk") or 0.0),
        compression_level=compression_level,
        compression_phase=str(raw.get("compression_phase") or ""),
        selected_compression_target=str(raw.get("selected_compression_target") or selected_block_id or ",".join(selected_block_ids)),
        selected_block_id=selected_block_id,
        selected_block_ids=selected_block_ids,
        block_family=str(raw.get("selected_block_family") or raw.get("block_family") or raw.get("target_block_family") or ""),
        block_token_before=_safe_int(raw.get("original_token_estimate") or raw.get("block_token_before") or 0),
        block_token_after_estimate=_safe_int(raw.get("proposed_token_estimate_after") or raw.get("block_token_after_estimate") or 0),
        expected_token_delta=expected_token_delta,
        measured_prompt_token_delta=_safe_float(raw.get("measured_prompt_token_delta") or 0.0),
        measured_prompt_token_delta_pct=_safe_float(raw.get("measured_prompt_token_delta_pct") or 0.0),
        fallback_reason=str(raw.get("fallback_reason") or ""),
        largest_token_component=str(raw.get("largest_token_component") or ""),
        preserved_content=[str(item) for item in (raw.get("preserved_content") or [])],
        removable_content=[str(item) for item in (raw.get("removable_content") or [])],
    )


def validate_proposal(proposal: MutationProposal, *, valid_blocks: set[str], core_blocks: set[str]) -> tuple[bool, str]:
    text = json.dumps(proposal.to_row(), ensure_ascii=False).lower()
    if any(term in text for term in ("retrieval top-k", "retrieval_topk", "retrieval mode", "service-context construction")):
        return False, "proposal attempted to mutate retrieval policy"
    if proposal.target_block_id and proposal.target_block_id not in valid_blocks:
        return False, "proposal targets unknown block"
    if proposal.target_block_id in core_blocks and proposal.operator in {"drop_optional_block", "remove_core_block", "block_deactivation"}:
        return False, "proposal attempted to remove a core block"
    if "(#" in proposal.replacement_text or ")." in proposal.replacement_text:
        return False, "proposal appears to generate JOILang code"
    return True, ""
