#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from utils.ga_block_model import BLOCK_FAMILIES, get_core_blocks, get_optional_blocks
from utils.pipeline_common import render_block


PROTECTED_BLOCK_IDS = {"01", "02", "03"}
PROTECTED_BLOCK_FAMILIES = {"Core_System", "Service_Mapping", "Output_Schema"}
PROTECTED_CONTENT_MARKERS = (
    "output schema",
    "json object",
    "return exactly",
    "service_list_snippet",
    "pre-mapping",
    "retrieval",
    "canonical_name",
    "clock_delay",
    "wait until",
    "break",
    ":=",
)


def estimate_prompt_tokens(text: str) -> int:
    """Cheap, deterministic token proxy for scheduling and advisor planning."""
    text = str(text or "")
    if not text:
        return 0
    wordish = len(re.findall(r"\w+|[^\s\w]", text, flags=re.UNICODE))
    charish = max(1, round(len(text) / 4))
    return max(1, int(round((wordish + charish) / 2)))


def default_profile_values() -> dict[str, Any]:
    return {
        "row_no": 0,
        "command_eng": "<command>",
        "command_kor": "",
        "command_text": "<command>",
        "connected_devices": "{}",
        "service_list_snippet": "{}",
        "optional_cron": "",
        "optional_period": "0",
        "cron": "",
        "period": "0",
        "candidate_strategy": "minimal",
        "det_diagnostics": "",
        "best_candidate": "",
        "failure_summary": "",
    }


def _count_exemplars(text: str) -> int:
    return len(re.findall(r"^### EXEMPLAR\s+\d+\b", text or "", flags=re.MULTILINE))


def _example_token_estimate(text: str) -> int:
    chunks = re.split(r"(?=^### EXEMPLAR\s+\d+\b)", text or "", flags=re.MULTILINE)
    examples = [chunk for chunk in chunks[1:] if chunk.strip()]
    return sum(estimate_prompt_tokens(chunk) for chunk in examples)


def _block_params(genome: dict[str, Any], block_id: str) -> dict[str, Any]:
    return dict((genome.get("block_params") or {}).get(block_id, {}) or {})


def _is_protected(block_id: str, family: str, body: str) -> bool:
    if block_id in PROTECTED_BLOCK_IDS or family in PROTECTED_BLOCK_FAMILIES:
        return True
    return False


def _safe_mutation_types(block_id: str, row: dict[str, Any]) -> list[str]:
    if not row["compression_allowed"]:
        return []
    safe: list[str] = []
    if int(row.get("few_shot_count") or 0) > 0:
        safe.extend(["reduce_few_shot_count_to_zero", "reduce_few_shot_count"])
    if int(row.get("micro_rule_count") or 0) > 3:
        safe.append("prune_micro_rules_to_top_k")
    if row.get("current_params"):
        safe.append("compact_block_params")
    if row.get("optional_status") == "optional":
        safe.append("drop_optional_block")
    if block_id == "06":
        safe.append("compact_reasoning_skeleton")
    return safe


def profile_prompt_blocks_for_genome(
    genome: dict[str, Any],
    *,
    values: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    values = {**default_profile_values(), **(values or {})}
    core_blocks = set(get_core_blocks())
    optional_blocks = set(get_optional_blocks())
    params = genome.get("params", {}) or {}
    rows: list[dict[str, Any]] = []
    for block_id in [str(item) for item in genome.get("blocks", []) or []]:
        block_params = _block_params(genome, block_id)
        try:
            metadata, body, path = render_block(block_id, values=values, block_params=block_params)
        except Exception as exc:
            metadata, body, path = {}, "", ""
            block_params = {**block_params, "profile_error": str(exc)}
        family = BLOCK_FAMILIES.get(block_id, str(metadata.get("family") or metadata.get("role") or "unknown"))
        protected = _is_protected(block_id, family, body)
        role = str(metadata.get("role") or "")
        few_shot = block_params.get("few_shot_count", params.get("few_shot_count"))
        if few_shot is None:
            few_shot = _count_exemplars(body)
        try:
            few_shot_count = int(few_shot or 0)
        except Exception:
            few_shot_count = 0
        micro_rule_count = len(block_params.get("micro_rules") or [])
        candidate_strategy_count = len(params.get("candidate_strategies") or []) if block_id == "02" else 0
        row = {
            "block_id": block_id,
            "block_family": family,
            "block_role": role,
            "is_core_block": block_id in core_blocks,
            "is_protected_block": protected,
            "char_count": len(body),
            "token_estimate": estimate_prompt_tokens(body),
            "few_shot_count": few_shot_count,
            "example_token_estimate": _example_token_estimate(body),
            "example_selected_by": "few_shot_count" if few_shot_count else "none",
            "removable_examples": max(0, few_shot_count),
            "micro_rule_count": micro_rule_count,
            "candidate_strategy_count": candidate_strategy_count,
            "optional_status": "core" if block_id in core_blocks else "optional" if block_id in optional_blocks else "unknown",
            "current_params": block_params,
            "compression_allowed": not protected,
            "protected_content_markers": [
                marker for marker in PROTECTED_CONTENT_MARKERS if marker in body.lower()
            ],
            "path": str(path),
        }
        row["safe_mutation_types"] = _safe_mutation_types(block_id, row)
        rows.append(row)
    return rows


def prompt_token_breakdown_for_genome(
    genome: dict[str, Any],
    *,
    block_token_breakdown: list[dict[str, Any]] | None = None,
    measured_prompt_tokens: float = 0.0,
) -> dict[str, Any]:
    blocks = block_token_breakdown or profile_prompt_blocks_for_genome(genome)
    by_family = Counter()
    for block in blocks:
        by_family[str(block.get("block_family", "unknown"))] += int(block.get("token_estimate") or 0)
    params = genome.get("params", {}) or {}
    block_params = genome.get("block_params", {}) or {}
    return {
        "estimated_prompt_tokens": sum(int(block.get("token_estimate") or 0) for block in blocks),
        "measured_prompt_tokens": float(measured_prompt_tokens or 0.0),
        "block_count": len(blocks),
        "tokens_by_block_family": dict(by_family),
        "candidate_strategy_count": len(params.get("candidate_strategies") or []),
        "candidate_strategies": list(params.get("candidate_strategies") or []),
        "max_tokens": int(params.get("max_tokens") or 0),
        "micro_rule_count": sum(len((block_params.get(block_id) or {}).get("micro_rules") or []) for block_id in block_params),
        "few_shot_blocks": {
            str(block.get("block_id")): int(block.get("few_shot_count") or 0)
            for block in blocks
            if int(block.get("few_shot_count") or 0) > 0
        },
    }


def reasoning_budget_for_categories(categories: list[Any] | tuple[Any, ...] | None) -> str:
    tokens = {str(item).strip() for item in (categories or []) if str(item).strip()}
    if not tokens:
        return "auto"
    if tokens <= {"1", "2"}:
        return "none"
    if tokens & {"6", "7", "8"}:
        return "cod_4"
    if tokens & {"3", "4", "5"}:
        return "cod_2"
    return "cod_1"


def dump_profile_payload(genome: dict[str, Any], *, measured_prompt_tokens: float = 0.0) -> dict[str, Any]:
    blocks = profile_prompt_blocks_for_genome(genome)
    return {
        "genome_id": str(genome.get("id", "")),
        "block_token_breakdown": blocks,
        "prompt_token_breakdown": prompt_token_breakdown_for_genome(
            genome,
            block_token_breakdown=blocks,
            measured_prompt_tokens=measured_prompt_tokens,
        ),
    }


__all__ = [
    "PROTECTED_BLOCK_IDS",
    "estimate_prompt_tokens",
    "profile_prompt_blocks_for_genome",
    "prompt_token_breakdown_for_genome",
    "reasoning_budget_for_categories",
    "dump_profile_payload",
]
