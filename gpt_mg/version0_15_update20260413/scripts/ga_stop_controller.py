#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ControllerDecision:
    generation_phase: str
    plateau_type: str
    next_action: str
    stop_candidate: bool
    stop_reason: str
    pareto_archive_delta: int
    unique_prompt_hash_count: int
    disruptive_attempt_count: int
    advisor_triggered: bool

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _window(rows: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    return rows[-max(1, size):]


def decide_next_action(
    progress_rows: list[dict[str, Any]],
    *,
    generation: int,
    max_generations: int,
    min_generations: int,
    plateau_window: int,
    target_detpass: float,
    pareto_archive_delta: int,
    unique_prompt_hash_count: int,
    population_size: int,
    advisor_enabled: bool,
    advisor_trigger_mode: str,
    disruptive_attempt_count: int,
    disruptive_max_attempts: int,
) -> ControllerDecision:
    if generation >= max_generations:
        return ControllerDecision(
            generation_phase="FINAL_SELECTION",
            plateau_type="max_generation_reached",
            next_action="stop_and_finalize",
            stop_candidate=True,
            stop_reason="max generations reached",
            pareto_archive_delta=pareto_archive_delta,
            unique_prompt_hash_count=unique_prompt_hash_count,
            disruptive_attempt_count=disruptive_attempt_count,
            advisor_triggered=False,
        )
    recent = _window(progress_rows, plateau_window)
    if generation < min_generations or len(recent) < plateau_window:
        return ControllerDecision(
            generation_phase="ACCURACY_SEARCH",
            plateau_type="warming_up",
            next_action="continue_accuracy",
            stop_candidate=False,
            stop_reason="",
            pareto_archive_delta=pareto_archive_delta,
            unique_prompt_hash_count=unique_prompt_hash_count,
            disruptive_attempt_count=disruptive_attempt_count,
            advisor_triggered=False,
        )
    dets = [float(row.get("best_so_far_DETPass") or row.get("validation_det_pass_rate") or 0.0) for row in recent]
    raw_dets = [float(row.get("raw_generation_best_DETPass") or row.get("validation_det_pass_rate") or 0.0) for row in recent]
    avgdets = [float(row.get("validation_avg_det_score") or row.get("avg_det_score") or 0.0) for row in recent]
    tokens = [float(row.get("avg_prompt_tokens") or 0.0) for row in recent if float(row.get("avg_prompt_tokens") or 0.0) > 0]
    det_delta = max(dets) - min(dets)
    avgdet_delta = max(avgdets) - min(avgdets)
    token_delta = (max(tokens) - min(tokens)) if len(tokens) > 1 else 0.0
    diversity_ratio = unique_prompt_hash_count / max(1, population_size)
    saturated = max(dets) >= target_detpass
    advisor_triggered = False
    if diversity_ratio < 0.5:
        phase = "DISRUPTIVE_SEARCH"
        plateau = "diversity_collapse"
        action = "increase_diversity_temporarily"
    elif det_delta < 0.0001 and avgdet_delta > 0.05:
        phase = "ROBUSTNESS_STABILIZATION"
        plateau = "detpass_plateau_avgdet_improving"
        action = "continue_accuracy"
    elif saturated and token_delta < 1.0:
        phase = "COMPRESSION_SEARCH"
        plateau = "saturated_accuracy_plateau"
        action = "switch_compression"
    elif det_delta < 0.0001:
        phase = "ROBUSTNESS_STABILIZATION"
        plateau = "accuracy_plateau"
        action = "switch_robustness"
        if advisor_enabled and advisor_trigger_mode in {"on_plateau", "on_failure_plateau"}:
            action = "trigger_advisor_if_enabled"
            advisor_triggered = True
    elif len(set(raw_dets)) > 1 and max(dets) == min(dets):
        phase = "ROBUSTNESS_STABILIZATION"
        plateau = "regression_oscillation"
        action = "switch_robustness"
    elif saturated:
        phase = "COMPRESSION_SEARCH"
        plateau = "token_plateau" if token_delta < 1.0 else "accuracy_target_reached"
        action = "switch_compression"
    else:
        phase = "ACCURACY_SEARCH"
        plateau = "none"
        action = "continue_accuracy"

    stop_candidate = False
    stop_reason = ""
    if (
        phase == "COMPRESSION_SEARCH"
        and pareto_archive_delta <= 0
        and disruptive_attempt_count >= disruptive_max_attempts
        and generation >= min_generations
    ):
        stop_candidate = True
        stop_reason = "stable Pareto archive after compression/disruptive attempts"
        action = "stop_and_finalize"
        phase = "FINAL_SELECTION"
    return ControllerDecision(
        generation_phase=phase,
        plateau_type=plateau,
        next_action=action,
        stop_candidate=stop_candidate,
        stop_reason=stop_reason,
        pareto_archive_delta=pareto_archive_delta,
        unique_prompt_hash_count=unique_prompt_hash_count,
        disruptive_attempt_count=disruptive_attempt_count,
        advisor_triggered=advisor_triggered,
    )
