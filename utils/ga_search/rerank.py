#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def candidate_rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(_truthy(row.get("det_pass"))),
        -_float(row.get("det_score")),
        -int(_truthy(row.get("gt_exact"))),
        _float(row.get("generation_prompt_tokens_total"), 0.0),
        _float(row.get("latency_sec"), 0.0),
        str(row.get("genome_id") or ""),
        int(_float(row.get("candidate_index"), 0.0)),
    )


def rerank_rows(eval_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(eval_rows, key=candidate_rank_key)


def best_row(eval_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    ranked = rerank_rows(eval_rows)
    return ranked[0] if ranked else None


def aggregate_genome_scores(eval_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in eval_rows:
        grouped.setdefault(str(row.get("genome_id") or "base"), []).append(row)
    records = []
    for genome_id, rows in grouped.items():
        avg_det = sum(_float(row.get("det_score")) for row in rows) / len(rows) if rows else 0.0
        pass_rate = sum(1 for row in rows if _truthy(row.get("det_pass"))) / len(rows) if rows else 0.0
        exact_rate = sum(1 for row in rows if _truthy(row.get("gt_exact"))) / len(rows) if rows else 0.0
        prompt_tokens = sum(_float(row.get("generation_prompt_tokens_total")) for row in rows) / len(rows) if rows else 0.0
        latency = sum(_float(row.get("latency_sec")) for row in rows) / len(rows) if rows else 0.0
        records.append(
            {
                "genome_id": genome_id,
                "rows": len(rows),
                "avg_det_score": avg_det,
                "det_pass_rate": pass_rate,
                "gt_exact_rate": exact_rate,
                "avg_prompt_tokens": prompt_tokens,
                "avg_latency_sec": latency,
                "fitness": avg_det + 10.0 * pass_rate + 5.0 * exact_rate - 0.0001 * prompt_tokens - 0.01 * latency,
            }
        )
    return sorted(records, key=lambda item: (-float(item["fitness"]), item["genome_id"]))
