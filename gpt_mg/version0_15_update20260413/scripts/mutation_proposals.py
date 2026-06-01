#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


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

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        for key in ("target_units", "affected_failure_families", "rollback_units"):
            row[key] = json.dumps(row[key], ensure_ascii=False)
        return row


def proposal_from_advisor(raw: dict[str, Any], *, generation: int) -> MutationProposal:
    return MutationProposal(
        proposal_id=str(raw.get("proposal_id", f"advisor_g{generation:03d}")),
        source="advisor",
        mutation_family=str(raw.get("mutation_family") or "advisor_guided"),
        operator=str(raw.get("mutation_type") or raw.get("operator") or "add_micro_rule"),
        target_block_id=str(raw.get("target_block_id", "")),
        target_block_family=str(raw.get("target_block_family", "")),
        replacement_text=str(raw.get("proposed_micro_rule") or raw.get("edit_instruction") or ""),
        risk_score=float(raw.get("risk_score") or 0.2),
        affected_failure_families=[str(raw.get("target_block_family", ""))],
        expected_effect=str(raw.get("reason", "")),
        generation=generation,
        accepted=bool(raw.get("accepted", True)),
        rejection_reason=str(raw.get("rejection_reason", "")),
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
