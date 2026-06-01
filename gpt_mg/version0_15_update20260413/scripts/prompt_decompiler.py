#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from scripts.mutation_proposals import MutationProposal


@dataclass
class PromptUnit:
    unit_id: str
    text_original: str
    text_normalized: str
    unit_type: str
    family: str
    intent_signature: str
    token_cost: int
    criticality: float
    removable: bool
    compressible: bool
    protected: bool
    dependencies: list[str] = field(default_factory=list)
    examples_linked: list[str] = field(default_factory=list)
    failure_families: list[str] = field(default_factory=list)
    active_failure_support: float = 0.0
    redundancy_group: str = ""
    utility_score: float = 0.0
    removal_risk: float = 0.0
    lifecycle_state: str = "active"

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PromptArtifact:
    prompt_hash: str
    units: list[PromptUnit]


SPLIT_RE = re.compile(r"\n(?=(?:#{1,6}\s+|[-*]\s+|\d+[.)]\s+|[A-Z][A-Z _-]{4,}:))")


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip()).lower()


def _family(text: str) -> str:
    lowered = text.lower()
    if "json" in lowered or "schema" in lowered or "return exactly" in lowered:
        return "Output_Schema"
    if "service" in lowered or "canonical" in lowered or "device" in lowered:
        return "Service_Mapping"
    if "cron" in lowered or "period" in lowered or "delay" in lowered or "temporal" in lowered:
        return "Temporal_Rule"
    if "example" in lowered or "few-shot" in lowered:
        return "FewShot"
    if "repair" in lowered:
        return "Repair_Clause"
    if "reason" in lowered or "skeleton" in lowered or "state" in lowered:
        return "Skeleton"
    return "General"


def _unit_type(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") or stripped.startswith("{"):
        return "schema_or_code_block"
    if re.match(r"^#{1,6}\s+", stripped):
        return "heading"
    if re.match(r"^[-*]\s+", stripped):
        return "bullet_rule"
    if re.match(r"^\d+[.)]\s+", stripped):
        return "numbered_rule"
    return "paragraph"


def _protected(text: str, family: str) -> bool:
    lowered = text.lower()
    protected_terms = (
        "json",
        "return exactly",
        "canonical",
        "service_list",
        "service list",
        "schema",
        "do not include reasoning",
    )
    return family in {"Output_Schema", "Service_Mapping"} and any(term in lowered for term in protected_terms)


def decompile_prompt(prompt: str, *, active_failure_families: list[str] | None = None) -> PromptArtifact:
    active_failure_families = active_failure_families or []
    chunks = [chunk.strip() for chunk in SPLIT_RE.split(str(prompt or "")) if chunk.strip()]
    units: list[PromptUnit] = []
    seen_norm: dict[str, str] = {}
    for idx, chunk in enumerate(chunks, start=1):
        normalized = _normalize_text(chunk)
        family = _family(chunk)
        protected = _protected(chunk, family)
        duplicate_of = seen_norm.get(normalized, "")
        if not duplicate_of:
            seen_norm[normalized] = f"u{idx:04d}"
        token_cost = max(1, len(chunk.split()))
        support = 1.0 if family in active_failure_families else 0.0
        criticality = 1.0 if protected else 0.5 + support
        removable = not protected and bool(duplicate_of)
        compressible = not protected and token_cost > 10
        units.append(
            PromptUnit(
                unit_id=f"u{idx:04d}",
                text_original=chunk,
                text_normalized=normalized,
                unit_type=_unit_type(chunk),
                family=family,
                intent_signature=hashlib.sha1(f"{family}:{normalized[:80]}".encode("utf-8")).hexdigest()[:12],
                token_cost=token_cost,
                criticality=criticality,
                removable=removable,
                compressible=compressible,
                protected=protected,
                failure_families=[family] if support else [],
                active_failure_support=support,
                redundancy_group=duplicate_of,
                utility_score=round(criticality - (0.25 if duplicate_of else 0.0), 4),
                removal_risk=round(criticality + (0.5 if protected else 0.0), 4),
            )
        )
    prompt_hash = hashlib.sha1(str(prompt or "").encode("utf-8")).hexdigest()[:16]
    return PromptArtifact(prompt_hash=prompt_hash, units=units)


def compression_proposals_from_artifact(
    artifact: PromptArtifact,
    *,
    generation: int,
    parent_genome_id: str,
    max_proposals: int = 4,
) -> list[MutationProposal]:
    proposals: list[MutationProposal] = []
    duplicate_units = [unit for unit in artifact.units if unit.removable]
    compressible_units = [unit for unit in artifact.units if unit.compressible and not unit.protected]
    for unit in duplicate_units[:max_proposals]:
        proposals.append(
            MutationProposal(
                proposal_id=f"cloudless_g{generation:03d}_{len(proposals)+1:02d}",
                source="cloudless",
                mutation_family="compression",
                operator="prune_stale_micro_rules",
                target_units=[unit.unit_id],
                target_block_family=unit.family,
                estimated_token_delta=-unit.token_cost,
                risk_score=unit.removal_risk,
                expected_effect="Remove duplicate low-risk prompt unit.",
                generation=generation,
                parent_genome_id=parent_genome_id,
            )
        )
    for unit in compressible_units[: max(0, max_proposals - len(proposals))]:
        proposals.append(
            MutationProposal(
                proposal_id=f"cloudless_g{generation:03d}_{len(proposals)+1:02d}",
                source="cloudless",
                mutation_family="compression",
                operator="template_compress_rule_family",
                target_units=[unit.unit_id],
                target_block_family=unit.family,
                estimated_token_delta=-max(1, unit.token_cost // 3),
                risk_score=unit.removal_risk,
                expected_effect="Compress verbose guidance unit into compact canonical wording.",
                generation=generation,
                parent_genome_id=parent_genome_id,
            )
        )
    return proposals
