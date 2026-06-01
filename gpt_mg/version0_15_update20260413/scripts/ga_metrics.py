#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any


DET_PASS_THRESHOLD = 70.0


def category_group(category: str | int | None) -> str:
    token = str(category or "").strip()
    if token in {"1", "2"}:
        return "basic"
    if token in {"3", "4", "5"}:
        return "temporal"
    if token in {"6", "7", "8"}:
        return "complex"
    return "unknown"


@dataclass
class GenomeMetricBundle:
    genome_id: str
    validation_det_pass_rate: float
    validation_avg_det_score: float
    avg_prompt_tokens: float
    avg_latency_sec: float
    det_score_variance: float
    basic_detpass: float
    temporal_detpass: float
    complex_detpass: float
    min_group_detpass: float
    harmonic_group_detpass: float
    category_gap: float
    token_penalty: float
    latency_penalty: float
    variance_penalty: float
    regression_penalty: float
    category_balance_score: float
    schema_robustness_score: float
    compression_gain: float
    pareto_rank: int
    pareto_frontier_member: bool
    score_accuracy: float
    score_efficiency: float
    score_balanced: float
    score_deployment: float
    score_main: float
    prompt_hash: str
    block_signature: str
    rule_signature: str
    unavailable_metrics: str = ""

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["pareto_frontier_member"] = bool(row["pareto_frontier_member"])
        return row


def one_row_margin(row_count: int, explicit: float | None = None) -> float:
    if explicit is not None and explicit > 0:
        return float(explicit)
    return round(100.0 / max(1, int(row_count or 1)), 6)


def stable_genome_signature(genome: dict[str, Any]) -> tuple[str, str, str]:
    blocks = [str(item) for item in genome.get("blocks", []) or []]
    block_params = genome.get("block_params", {}) or {}
    params = genome.get("params", {}) or {}
    block_signature = ",".join(blocks)
    rules: list[str] = []
    for block_id in sorted(block_params):
        for rule in block_params.get(block_id, {}).get("micro_rules", []) or []:
            rules.append(f"{block_id}:{str(rule).strip()}")
    rule_signature = hashlib.sha1("\n".join(sorted(rules)).encode("utf-8")).hexdigest()[:16]
    payload = {
        "blocks": blocks,
        "block_params": block_params,
        "params": {
            key: params.get(key)
            for key in sorted(params)
            if key not in {"model"}
        },
    }
    prompt_hash = hashlib.sha1(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return prompt_hash, block_signature, rule_signature


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _avg(values: list[float]) -> float:
    return round(statistics.fmean(values), 6) if values else 0.0


def _variance(values: list[float]) -> float:
    return round(statistics.pvariance(values), 6) if len(values) > 1 else 0.0


def _harmonic(values: list[float]) -> float:
    positives = [max(0.000001, value) for value in values if value >= 0]
    if not positives:
        return 0.0
    return round(len(positives) / sum(1.0 / value for value in positives), 6)


def _pass_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    passed = 0
    for row in rows:
        score = _float(row.get("det_score"))
        if _bool(row.get("det_gt_exact")) or score >= DET_PASS_THRESHOLD:
            passed += 1
    return round((passed / len(rows)) * 100.0, 6)


def _schema_robustness(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 100.0
    schema_failures = 0
    schema_reasons = {
        "invalid_json",
        "schema_missing_keys",
        "unknown_service",
        "service_match",
        "arg_type",
        "enum_grounding",
    }
    for row in rows:
        reasons = row.get("failure_reasons") or []
        if isinstance(reasons, str):
            reasons = [reasons]
        bases = {str(reason).split(":", 1)[0] for reason in reasons}
        if bases & schema_reasons:
            schema_failures += 1
    return round(100.0 - (schema_failures / len(rows)) * 100.0, 6)


def _generation_values(metrics: dict[str, Any], key: str) -> list[float]:
    rows = list((metrics.get("generation_summary") or {}).get("rows") or [])
    values: list[float] = []
    for row in rows:
        value = _float(row.get(key), math.nan)
        if not math.isnan(value):
            values.append(value)
    return values


def token_penalty(
    tokens: float,
    *,
    token_budget: int | None,
    accepted_tokens: float | None,
    mode: str,
) -> float:
    mode = str(mode or "off")
    penalties: list[float] = []
    if mode in {"budget", "hybrid"} and token_budget and token_budget > 0:
        penalties.append(max(0.0, (tokens - token_budget) / token_budget))
    if mode in {"accepted", "hybrid"} and accepted_tokens and accepted_tokens > 0:
        penalties.append(max(0.0, (tokens / accepted_tokens) - 1.0))
    return round(max(penalties) if penalties else 0.0, 6)


def compression_gain(
    tokens: float,
    parent_tokens: float | None,
    *,
    detpass: float,
    parent_detpass: float | None,
    margin: float,
) -> float:
    if not parent_tokens or parent_tokens <= 0:
        return 0.0
    if parent_detpass is not None and detpass < parent_detpass - margin:
        return 0.0
    return round(max(0.0, (parent_tokens - tokens) / parent_tokens), 6)


def compression_acceptance_decision(
    *,
    parent_detpass: float,
    child_detpass: float,
    parent_tokens: float,
    child_tokens: float,
    margin: float,
    min_token_reduction: float,
    critical_regression_pass: bool = True,
) -> tuple[bool, str, float]:
    if parent_tokens <= 0 or child_tokens <= 0:
        return False, "token count unavailable for compression acceptance", 0.0
    token_reduction = max(0.0, (parent_tokens - child_tokens) / parent_tokens)
    if token_reduction < min_token_reduction:
        return False, "token reduction below compression acceptance threshold", round(token_reduction, 6)
    if child_detpass < parent_detpass - margin:
        return False, "DETPass drop exceeds one-row compression margin", round(token_reduction, 6)
    if not critical_regression_pass:
        return False, "critical regression guard failed", round(token_reduction, 6)
    return True, "", round(token_reduction, 6)


def regression_penalty(
    current: dict[str, float],
    accepted: dict[str, float] | None,
    *,
    margin: float,
) -> float:
    if not accepted:
        return 0.0
    keys = [
        "validation_det_pass_rate",
        "basic_detpass",
        "temporal_detpass",
        "complex_detpass",
    ]
    penalty = 0.0
    for key in keys:
        penalty += max(0.0, float(accepted.get(key, 0.0)) - float(current.get(key, 0.0)) - margin)
    return round(penalty, 6)


def metrics_from_evaluation(
    evaluation: dict[str, Any],
    *,
    token_budget: int | None = None,
    token_penalty_mode: str = "off",
    accepted_metrics: GenomeMetricBundle | None = None,
    parent_metrics: GenomeMetricBundle | None = None,
    fitness_avgdet_weight: float = 0.20,
    fitness_token_weight: float = 2.0,
    fitness_regression_weight: float = 2.0,
    fitness_variance_weight: float = 0.05,
    fitness_category_weight: float = 0.05,
    row_margin: float | None = None,
) -> GenomeMetricBundle:
    genome = evaluation.get("genome") or {}
    validation = evaluation.get("validation_metrics") or {}
    rows = list(validation.get("rows") or [])
    scores = [_float(row.get("det_score")) for row in rows]
    detpass = _pass_rate(rows)
    avgdet = _float(validation.get("avg_det_score"), _avg(scores))
    variance = _float(validation.get("variance"), _variance(scores))
    prompt_tokens = _avg(_generation_values(validation, "generation_prompt_tokens_total"))
    latency = _avg(_generation_values(validation, "generation_llm_latency_sec"))
    by_group = {"basic": [], "temporal": [], "complex": []}
    for row in rows:
        group = category_group(row.get("category"))
        if group in by_group:
            by_group[group].append(row)
    group_rates = {
        key: _pass_rate(value) if value else detpass
        for key, value in by_group.items()
    }
    group_values = list(group_rates.values())
    min_group = min(group_values) if group_values else detpass
    harmonic = _harmonic(group_values)
    category_gap = round(max(group_values) - min(group_values), 6) if group_values else 0.0
    category_balance = round((min_group + harmonic) / 2.0, 6)
    schema_score = _schema_robustness(rows)
    margin = one_row_margin(len(rows), row_margin)
    accepted_row = accepted_metrics.to_row() if accepted_metrics else None
    parent_row = parent_metrics.to_row() if parent_metrics else None
    token_pen = token_penalty(
        prompt_tokens,
        token_budget=token_budget,
        accepted_tokens=(accepted_metrics.avg_prompt_tokens if accepted_metrics else None),
        mode=token_penalty_mode,
    )
    comp_gain = compression_gain(
        prompt_tokens,
        parent_metrics.avg_prompt_tokens if parent_metrics else None,
        detpass=detpass,
        parent_detpass=(parent_metrics.validation_det_pass_rate if parent_metrics else None),
        margin=margin,
    )
    current_row = {
        "validation_det_pass_rate": detpass,
        "basic_detpass": group_rates["basic"],
        "temporal_detpass": group_rates["temporal"],
        "complex_detpass": group_rates["complex"],
    }
    reg_pen = regression_penalty(current_row, accepted_row, margin=margin)
    latency_pen = 0.0
    var_pen = variance / 100.0
    score_accuracy = round(detpass + fitness_avgdet_weight * avgdet, 6)
    score_efficiency = round(100.0 - (fitness_token_weight * 100.0 * token_pen) - latency_pen, 6)
    score_balanced = round(score_accuracy + fitness_category_weight * category_balance - fitness_variance_weight * var_pen, 6)
    score_deployment = round(score_accuracy - fitness_token_weight * token_pen - fitness_regression_weight * reg_pen, 6)
    score_main = round(
        detpass
        + fitness_avgdet_weight * avgdet
        + fitness_category_weight * category_balance
        + min(5.0, comp_gain * 10.0)
        - fitness_token_weight * token_pen
        - fitness_variance_weight * var_pen
        - fitness_regression_weight * reg_pen,
        6,
    )
    prompt_hash, block_signature, rule_signature = stable_genome_signature(genome)
    unavailable = []
    if prompt_tokens <= 0:
        unavailable.append("avg_prompt_tokens")
    if latency <= 0:
        unavailable.append("avg_latency_sec")
    if not rows:
        unavailable.append("validation_rows")
    return GenomeMetricBundle(
        genome_id=str(genome.get("id", "")),
        validation_det_pass_rate=detpass,
        validation_avg_det_score=avgdet,
        avg_prompt_tokens=prompt_tokens,
        avg_latency_sec=latency,
        det_score_variance=variance,
        basic_detpass=group_rates["basic"],
        temporal_detpass=group_rates["temporal"],
        complex_detpass=group_rates["complex"],
        min_group_detpass=round(min_group, 6),
        harmonic_group_detpass=harmonic,
        category_gap=category_gap,
        token_penalty=token_pen,
        latency_penalty=latency_pen,
        variance_penalty=round(var_pen, 6),
        regression_penalty=reg_pen,
        category_balance_score=category_balance,
        schema_robustness_score=schema_score,
        compression_gain=comp_gain,
        pareto_rank=999,
        pareto_frontier_member=False,
        score_accuracy=score_accuracy,
        score_efficiency=score_efficiency,
        score_balanced=score_balanced,
        score_deployment=score_deployment,
        score_main=score_main,
        prompt_hash=prompt_hash,
        block_signature=block_signature,
        rule_signature=rule_signature,
        unavailable_metrics="|".join(unavailable),
    )


def best_tie_key(metric: GenomeMetricBundle, *, generation: int = 0) -> tuple[float, float, float, float, int, str]:
    latency = metric.avg_latency_sec if metric.avg_latency_sec > 0 else 10**9
    tokens = metric.avg_prompt_tokens if metric.avg_prompt_tokens > 0 else 10**9
    return (
        -metric.validation_det_pass_rate,
        -metric.validation_avg_det_score,
        tokens,
        latency,
        generation,
        metric.genome_id,
    )


def _dominates(a: GenomeMetricBundle, b: GenomeMetricBundle) -> bool:
    a_tokens = a.avg_prompt_tokens if a.avg_prompt_tokens > 0 else 10**12
    b_tokens = b.avg_prompt_tokens if b.avg_prompt_tokens > 0 else 10**12
    no_worse = (
        a.validation_det_pass_rate >= b.validation_det_pass_rate
        and a.validation_avg_det_score >= b.validation_avg_det_score
        and a_tokens <= b_tokens
    )
    strictly = (
        a.validation_det_pass_rate > b.validation_det_pass_rate
        or a.validation_avg_det_score > b.validation_avg_det_score
        or a_tokens < b_tokens
    )
    return no_worse and strictly


def assign_pareto(metrics: list[GenomeMetricBundle]) -> list[GenomeMetricBundle]:
    for metric in metrics:
        dominated_by = [other for other in metrics if other is not metric and _dominates(other, metric)]
        metric.pareto_rank = 1 if not dominated_by else 2
        metric.pareto_frontier_member = not dominated_by
    return metrics


def pareto_rows(
    metrics: list[GenomeMetricBundle],
    *,
    generation: int,
    model_key: str,
    previous_frontier_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    previous_frontier_ids = previous_frontier_ids or set()
    rows: list[dict[str, Any]] = []
    for metric in assign_pareto(metrics):
        dominated_by = ""
        if not metric.pareto_frontier_member:
            dominators = [other.genome_id for other in metrics if other is not metric and _dominates(other, metric)]
            dominated_by = dominators[0] if dominators else ""
        rows.append(
            {
                "generation": generation,
                "genome_id": metric.genome_id,
                "model_key": model_key,
                "det": metric.validation_avg_det_score,
                "det_pass_rate": metric.validation_det_pass_rate,
                "sdet": metric.validation_avg_det_score,
                "avg_prompt_tokens": metric.avg_prompt_tokens,
                "warm_latency_p50": metric.avg_latency_sec,
                "peak_vram_gb": "",
                "oom_count": "",
                "failure_rate": round(100.0 - metric.validation_det_pass_rate, 6),
                "is_pareto_frontier": metric.pareto_frontier_member,
                "newly_discovered_frontier": metric.pareto_frontier_member and metric.genome_id not in previous_frontier_ids,
                "dominated_by": dominated_by,
                "pareto_rank": metric.pareto_rank,
                "knee_candidate": "",
                "pareto_status": "partial_metrics" if metric.unavailable_metrics else "full_metrics",
            }
        )
    return rows


def pareto_summary(rows: list[dict[str, Any]], *, generation: int, model_key: str) -> dict[str, Any]:
    frontier = [row for row in rows if row.get("is_pareto_frontier")]
    if not frontier:
        return {
            "generation": generation,
            "model_key": model_key,
            "new_frontier": 0,
            "frontier_size": 0,
            "best_det": 0.0,
            "best_det_genome_id": "",
            "best_tokens": 0.0,
            "best_tokens_genome_id": "",
            "knee_candidate": "",
            "pareto_status": "partial_metrics",
            "oom_resolved": "",
            "overbudget_children": "",
        }
    best_det = max(frontier, key=lambda row: (float(row.get("det_pass_rate") or 0.0), float(row.get("det") or 0.0)))
    token_candidates = [row for row in frontier if float(row.get("avg_prompt_tokens") or 0.0) > 0]
    best_tokens = min(token_candidates, key=lambda row: float(row.get("avg_prompt_tokens") or 0.0)) if token_candidates else frontier[0]
    knee = max(
        frontier,
        key=lambda row: float(row.get("det_pass_rate") or 0.0) - 0.01 * float(row.get("avg_prompt_tokens") or 0.0),
    )
    for row in frontier:
        row["knee_candidate"] = knee.get("genome_id", "")
    return {
        "generation": generation,
        "model_key": model_key,
        "new_frontier": sum(1 for row in frontier if row.get("newly_discovered_frontier")),
        "frontier_size": len(frontier),
        "best_det": best_det.get("det_pass_rate", 0.0),
        "best_det_genome_id": best_det.get("genome_id", ""),
        "best_tokens": best_tokens.get("avg_prompt_tokens", 0.0),
        "best_tokens_genome_id": best_tokens.get("genome_id", ""),
        "knee_candidate": knee.get("genome_id", ""),
        "pareto_status": "full_metrics" if all(row.get("pareto_status") == "full_metrics" for row in frontier) else "partial_metrics",
        "oom_resolved": "",
        "overbudget_children": "",
    }
