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


@dataclass
class MutationProposal:
    proposal_id: str
    source: str
    mutation_family: str
    operator: str
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
    proposal_state: str = PROPOSAL_STATE_PROPOSED
    advisor_batch_id: str = ""
    advisor_proposal_id: str = ""
    category_scope: list[int] = field(default_factory=list)
    group_scope: list[str] = field(default_factory=list)
    priority: int = 0
    regression_risk: float = 0.0
    scheduling_reason: str = ""
    advisor_child_duplicate: bool = False
    duplicate_of: str = ""
    compression_level: str = ""
    selected_block_ids: list[str] = field(default_factory=list)
    expected_token_delta: int = 0
    parent_prompt_tokens: float = 0.0
    child_prompt_tokens: float = 0.0
    measured_prompt_token_delta: float = 0.0
    validation_requirement: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        for key in (
            "target_units",
            "affected_failure_families",
            "rollback_units",
            "category_scope",
            "group_scope",
            "selected_block_ids",
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
    raw_selected_blocks = raw.get("selected_block_ids") or raw.get("block_ids")
    if isinstance(raw_selected_blocks, str):
        raw_selected_blocks = [raw_selected_blocks]
    if not raw_selected_blocks and raw.get("selected_block_id"):
        raw_selected_blocks = [raw.get("selected_block_id")]
    selected_block_ids = [str(value) for value in (raw_selected_blocks or []) if str(value).strip()]
    expected_delta = int(raw.get("expected_token_delta") or raw.get("total_expected_token_delta") or 0)
    return MutationProposal(
        proposal_id=proposal_id,
        source="advisor",
        mutation_family=str(raw.get("mutation_family") or "advisor_guided"),
        operator=str(raw.get("mutation_type") or raw.get("operator") or raw.get("exact_mutation_operator") or "add_micro_rule"),
        target_units=selected_block_ids,
        target_block_id=str(raw.get("target_block_id") or raw.get("selected_block_id") or ""),
        target_block_family=str(raw.get("target_block_family") or raw.get("selected_block_family") or ""),
        replacement_text=str(
            raw.get("proposed_micro_rule")
            or raw.get("edit_instruction")
            or (json.dumps(raw.get("steps"), ensure_ascii=False) if raw.get("steps") else "")
        ),
        estimated_token_delta=expected_delta,
        risk_score=float(raw.get("regression_risk") or raw.get("risk_score") or 0.2),
        affected_failure_families=[str(item) for item in affected if str(item).strip()],
        expected_effect=str(raw.get("expected_effect") or raw.get("reason", "")),
        generation=generation,
        accepted=bool(raw.get("accepted", True)),
        rejection_reason=str(raw.get("rejection_reason", "")),
        proposal_state=str(raw.get("proposal_state") or PROPOSAL_STATE_PROPOSED),
        advisor_batch_id=str(raw.get("advisor_batch_id") or advisor_batch_id),
        advisor_proposal_id=proposal_id,
        category_scope=category_scope,
        group_scope=group_scope,
        priority=int(raw.get("priority") or 0),
        regression_risk=float(raw.get("regression_risk") or 0.0),
        compression_level=str(raw.get("compression_level", "")),
        selected_block_ids=selected_block_ids,
        expected_token_delta=expected_delta,
        parent_prompt_tokens=float(raw.get("parent_prompt_tokens") or 0.0),
        child_prompt_tokens=float(raw.get("child_prompt_tokens") or 0.0),
        measured_prompt_token_delta=float(raw.get("measured_prompt_token_delta") or 0.0),
        validation_requirement=str(raw.get("validation_requirement") or ""),
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
