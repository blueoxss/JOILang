#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


REQUIRED_KEYS = ("name", "cron", "period", "code")


def extract_json_block(text: str) -> str:
    stripped = str(text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1].strip()
    return stripped


def normalize_candidate_dict(value: Any) -> tuple[dict[str, Any], list[str]]:
    if isinstance(value, list):
        value = value[0] if value else {}
    if not isinstance(value, dict):
        return {"name": "", "cron": "", "period": 0, "code": ""}, list(REQUIRED_KEYS)
    missing = [key for key in REQUIRED_KEYS if key not in value]
    period = value.get("period", 0)
    try:
        period = int(period)
    except Exception:
        period = 0
    return (
        {
            "name": str(value.get("name", "") or ""),
            "cron": str(value.get("cron", "") or ""),
            "period": period,
            "code": str(value.get("code") or value.get("script") or ""),
        },
        missing,
    )


def repair_candidate_json_text(content: str) -> dict[str, Any]:
    """Deterministically extract one JOILang JSON candidate without calling an LLM."""
    raw = str(content or "")
    if not raw.strip():
        candidate, missing = normalize_candidate_dict({})
        return {
            "ok": False,
            "error_type": "empty_output",
            "candidate": candidate,
            "before": raw,
            "after": json.dumps(candidate, ensure_ascii=False),
            "repair_applied": False,
            "repair_actions": [],
            "missing_required_keys": missing,
        }

    extracted = extract_json_block(raw)
    actions: list[str] = []
    if extracted != raw.strip():
        actions.append("output_only_json_extract")
    try:
        parsed = json.loads(extracted)
    except json.JSONDecodeError as exc:
        candidate, missing = normalize_candidate_dict({})
        return {
            "ok": False,
            "error_type": "invalid_json",
            "candidate": candidate,
            "before": raw,
            "after": extracted,
            "repair_applied": bool(actions),
            "repair_actions": actions,
            "missing_required_keys": missing,
            "error": str(exc),
        }

    candidate, missing = normalize_candidate_dict(parsed)
    if missing:
        actions.append("fill_missing_required_keys")
    if not candidate.get("code"):
        return {
            "ok": False,
            "error_type": "invalid_json",
            "candidate": candidate,
            "before": raw,
            "after": json.dumps(candidate, ensure_ascii=False),
            "repair_applied": bool(actions),
            "repair_actions": actions,
            "missing_required_keys": missing,
            "error": "candidate is missing non-empty code",
        }
    return {
        "ok": True,
        "error_type": "",
        "candidate": candidate,
        "before": raw,
        "after": json.dumps(candidate, ensure_ascii=False),
        "repair_applied": bool(actions),
        "repair_actions": actions,
        "missing_required_keys": missing,
    }
