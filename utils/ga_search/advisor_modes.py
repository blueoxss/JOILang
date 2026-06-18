#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


VALID_ADVISOR_MODES = {"none", "local", "cloud", "hybrid"}


def validate_advisor_mode(mode: str | None) -> str:
    normalized = str(mode or "none").strip().lower()
    if normalized not in VALID_ADVISOR_MODES:
        raise ValueError(f"unsupported advisor mode '{mode}'. Expected one of: {sorted(VALID_ADVISOR_MODES)}")
    return normalized


def required_inputs_for_mode(mode: str) -> list[str]:
    mode = validate_advisor_mode(mode)
    if mode == "local":
        return ["local_det_report or strict_results_dir/local_det_failure_report.json"]
    if mode == "cloud":
        return ["cloud_judge_csv"]
    if mode == "hybrid":
        return ["advisor_rich_feedback or local/strict input plus cloud_judge_csv"]
    return []


def describe_advisor_mode(mode: str) -> dict[str, Any]:
    mode = validate_advisor_mode(mode)
    descriptions = {
        "none": {
            "primary_signal": "base_prompt",
            "cloud_is_auxiliary": True,
            "api_required": False,
            "description": "No advisor feedback is attached; only base search input artifacts are produced.",
        },
        "local": {
            "primary_signal": "strict_det",
            "cloud_is_auxiliary": True,
            "api_required": False,
            "description": "Use local strict DET failure report as deterministic advisor evidence.",
        },
        "cloud": {
            "primary_signal": "cloud_semantic",
            "cloud_is_auxiliary": True,
            "api_required": False,
            "description": "Use cloud semantic judge CSV as auxiliary diagnostic evidence only.",
        },
        "hybrid": {
            "primary_signal": "strict_det_plus_cloud",
            "cloud_is_auxiliary": True,
            "api_required": False,
            "description": "Use strict DET as primary signal and cloud judge reasoning as auxiliary explanation.",
        },
    }
    return {"advisor_mode": mode, **descriptions[mode], "required_inputs": required_inputs_for_mode(mode)}
