#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scripts.ga_metrics import GenomeMetricBundle, assign_pareto, best_tie_key


@dataclass
class ArchiveState:
    accepted_best: dict[str, Any] | None = None
    global_best_detpass: dict[str, Any] | None = None
    global_best_score: dict[str, Any] | None = None
    compact_best_within_epsilon: dict[str, Any] | None = None
    specialists: dict[str, dict[str, Any]] = field(default_factory=dict)
    pareto_archive: dict[str, dict[str, Any]] = field(default_factory=dict)


def metric_of(item: dict[str, Any]) -> GenomeMetricBundle:
    metric = item.get("redesign_metrics")
    if not isinstance(metric, GenomeMetricBundle):
        raise KeyError("evaluated item is missing redesign_metrics")
    return metric


def better_best(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any] | None:
    if a is None:
        return b
    if b is None:
        return a
    return min([a, b], key=lambda item: best_tie_key(metric_of(item), generation=int(item.get("generation", 0) or 0)))


def update_archives(
    archives: ArchiveState,
    evaluated: list[dict[str, Any]],
    *,
    accepted_best: dict[str, Any] | None,
    generation: int,
    one_row_margin: float,
    enable_group_specialists: bool,
) -> ArchiveState:
    if accepted_best is not None:
        archives.accepted_best = accepted_best
    for item in evaluated:
        item["generation"] = generation
    sorted_by_detpass = sorted(evaluated, key=lambda item: best_tie_key(metric_of(item), generation=generation))
    if sorted_by_detpass:
        archives.global_best_detpass = better_best(archives.global_best_detpass, sorted_by_detpass[0])
    sorted_by_score = sorted(evaluated, key=lambda item: (-metric_of(item).score_main, *best_tie_key(metric_of(item), generation=generation)))
    if sorted_by_score:
        if archives.global_best_score is None or metric_of(sorted_by_score[0]).score_main > metric_of(archives.global_best_score).score_main:
            archives.global_best_score = sorted_by_score[0]

    best_detpass = metric_of(archives.global_best_detpass).validation_det_pass_rate if archives.global_best_detpass else 0.0
    compact_candidates = [
        item for item in evaluated
        if metric_of(item).validation_det_pass_rate >= best_detpass - one_row_margin
        and metric_of(item).avg_prompt_tokens > 0
    ]
    if compact_candidates:
        compact = min(compact_candidates, key=lambda item: (metric_of(item).avg_prompt_tokens, *best_tie_key(metric_of(item), generation=generation)))
        archives.compact_best_within_epsilon = better_compact(archives.compact_best_within_epsilon, compact)

    assign_pareto([metric_of(item) for item in evaluated])
    for item in evaluated:
        metric = metric_of(item)
        if metric.pareto_frontier_member:
            archives.pareto_archive[metric.genome_id] = item

    if enable_group_specialists:
        group_keys = {
            "basic": "basic_detpass",
            "temporal": "temporal_detpass",
            "complex": "complex_detpass",
        }
        for group, attr in group_keys.items():
            champion = max(
                evaluated,
                key=lambda item: (
                    getattr(metric_of(item), attr),
                    metric_of(item).validation_avg_det_score,
                    -metric_of(item).avg_prompt_tokens if metric_of(item).avg_prompt_tokens > 0 else -10**9,
                ),
            )
            existing = archives.specialists.get(group)
            if existing is None or getattr(metric_of(champion), attr) > getattr(metric_of(existing), attr):
                archives.specialists[group] = champion
    return archives


def better_compact(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any] | None:
    if a is None:
        return b
    if b is None:
        return a
    ma = metric_of(a)
    mb = metric_of(b)
    return b if (mb.avg_prompt_tokens, -mb.validation_det_pass_rate, -mb.validation_avg_det_score) < (
        ma.avg_prompt_tokens,
        -ma.validation_det_pass_rate,
        -ma.validation_avg_det_score,
    ) else a


def _add_unique(
    selected: list[dict[str, Any]],
    item: dict[str, Any] | None,
    reason: str,
    seen: set[str],
) -> None:
    if not item:
        return
    genome_id = str((item.get("genome") or {}).get("id", ""))
    if not genome_id or genome_id in seen:
        return
    clone = dict(item)
    clone["elite_reason"] = reason
    selected.append(clone)
    seen.add(genome_id)


def quota_elites(
    evaluated: list[dict[str, Any]],
    archives: ArchiveState,
    *,
    population_size: int,
    category_balance_mode: str,
    one_row_margin: float,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    sorted_det = sorted(evaluated, key=lambda item: best_tie_key(metric_of(item), generation=int(item.get("generation", 0) or 0)))
    sorted_score = sorted(evaluated, key=lambda item: (-metric_of(item).score_main, *best_tie_key(metric_of(item))))
    _add_unique(selected, archives.accepted_best, "accepted_best", seen)
    _add_unique(selected, archives.global_best_detpass, "global_best_DETPass", seen)
    _add_unique(selected, sorted_det[0] if sorted_det else None, "current_DETPass_champion", seen)
    _add_unique(selected, archives.compact_best_within_epsilon, "pareto_compact_elite", seen)
    _add_unique(selected, sorted_score[0] if sorted_score else None, "score_main_champion", seen)
    if category_balance_mode in {"routing", "fitness"}:
        for group in ("basic", "temporal", "complex"):
            _add_unique(selected, archives.specialists.get(group), f"{group}_specialist", seen)
    for item in sorted_det:
        if len(selected) >= max(1, population_size):
            break
        _add_unique(selected, item, "quota_fill_DETPass_order", seen)
    return selected[: max(1, population_size)]


def regression_gate(
    candidate: GenomeMetricBundle,
    accepted: GenomeMetricBundle | None,
    *,
    margin: float,
    category_balance_mode: str,
) -> tuple[bool, str]:
    if accepted is None:
        return True, ""
    if candidate.validation_det_pass_rate < accepted.validation_det_pass_rate - margin:
        return False, "candidate regressed accepted DETPass beyond one-row margin"
    if category_balance_mode in {"guard", "fitness", "routing"}:
        checks = [
            ("basic", candidate.basic_detpass, accepted.basic_detpass),
            ("temporal", candidate.temporal_detpass, accepted.temporal_detpass),
            ("complex", candidate.complex_detpass, accepted.complex_detpass),
        ]
        for name, current, previous in checks:
            if current < previous - margin:
                return False, f"candidate regressed {name} DETPass beyond one-row margin"
    return True, ""
