#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from typing import Any


SERVICE_CALL_RE = re.compile(r"\([^)]*\)\.([A-Za-z_][A-Za-z0-9_]*)")
RECEIVER_RE = re.compile(r"\(([^)]*)\)\.")


def parse_json_object(value: Any, *, label: str) -> dict[str, Any]:
    if isinstance(value, list):
        if not value:
            raise ValueError(f"{label} is an empty list")
        value = value[0]
    if isinstance(value, dict):
        return value
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is empty")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if isinstance(parsed, list):
        if not parsed:
            raise ValueError(f"{label} is an empty JSON list")
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def parse_official_gt(row: dict[str, Any]) -> dict[str, Any]:
    if "gt" not in row or not str(row.get("gt") or "").strip():
        raise ValueError("official ground truth column 'gt' is missing or empty")
    return parse_json_object(row.get("gt"), label="gt")


def normalize_candidate(candidate: Any) -> dict[str, Any]:
    parsed = parse_json_object(candidate, label="generated candidate")
    return {
        "name": str(parsed.get("name", "")),
        "cron": str(parsed.get("cron", "")),
        "period": parsed.get("period", 0),
        "code": str(parsed.get("code") or parsed.get("script") or ""),
    }


def gt_code(gt_json: dict[str, Any]) -> str:
    return str(gt_json.get("code") or gt_json.get("script") or "")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))


def similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def extract_services(code: str) -> list[str]:
    return SERVICE_CALL_RE.findall(str(code or ""))


def extract_receivers(code: str) -> list[str]:
    return [normalize_text(item) for item in RECEIVER_RE.findall(str(code or ""))]


def compare_bool(left: Any, right: Any) -> bool:
    return normalize_text(left) == normalize_text(right)


def strict_det_evaluate_row(
    *,
    row: dict[str, Any],
    candidate: Any,
    row_no: int | str,
    genome_id: str = "base",
    candidate_index: int = 0,
    det_threshold: float = 70.0,
) -> dict[str, Any]:
    failure_reasons: list[str] = []
    gt_json: dict[str, Any] = {}
    generated_json: dict[str, Any] = {}
    try:
        gt_json = parse_official_gt(row)
    except Exception as exc:
        failure_reasons.append("missing_official_gt")
        gt_json = {"_error": str(exc)}
    try:
        generated_json = normalize_candidate(candidate)
    except Exception as exc:
        failure_reasons.append("invalid_json")
        generated_json = {"_error": str(exc), "name": "", "cron": "", "period": "", "code": ""}

    required_missing = [key for key in ("name", "cron", "period", "code") if key not in generated_json]
    if required_missing:
        failure_reasons.append("missing_required_key:" + ",".join(required_missing))

    reference_code = gt_code(gt_json)
    generated_code = str(generated_json.get("code") or "")
    if not reference_code:
        failure_reasons.append("missing_gt_code")
    if not generated_code:
        failure_reasons.append("missing_generated_code")

    cron_match = compare_bool(gt_json.get("cron", ""), generated_json.get("cron", ""))
    period_match = compare_bool(gt_json.get("period", ""), generated_json.get("period", ""))
    if not cron_match:
        failure_reasons.append("cron_mismatch")
    if not period_match:
        failure_reasons.append("period_mismatch")

    code_sim = similarity(reference_code, generated_code) if reference_code and generated_code else 0.0
    code_match = code_sim >= 0.995
    gt_exact = cron_match and period_match and code_match
    if not code_match:
        failure_reasons.append("gt_mismatch")

    ref_services = Counter(extract_services(reference_code))
    gen_services = Counter(extract_services(generated_code))
    service_valid = all(gen_services.get(service, 0) >= count for service, count in ref_services.items())
    if ref_services and not service_valid:
        failure_reasons.append("gt_service_coverage")

    ref_receivers = set(extract_receivers(reference_code))
    gen_receivers = set(extract_receivers(generated_code))
    receiver_valid = ref_receivers.issubset(gen_receivers) if ref_receivers else True
    if not receiver_valid:
        failure_reasons.append("gt_receiver_coverage")

    schedule_score = 1.0 if cron_match and period_match else (0.5 if cron_match or period_match else 0.0)
    service_score = 1.0 if service_valid else 0.0
    receiver_score = 1.0 if receiver_valid else 0.0
    det_score = 100.0 * (0.45 * code_sim + 0.20 * schedule_score + 0.20 * service_score + 0.15 * receiver_score)
    if "invalid_json" in failure_reasons or "missing_official_gt" in failure_reasons:
        det_score = 0.0
    det_pass = det_score >= float(det_threshold) and not any(
        reason in failure_reasons for reason in {"invalid_json", "missing_official_gt", "missing_generated_code"}
    )

    unique_reasons = []
    for reason in failure_reasons:
        if reason not in unique_reasons:
            unique_reasons.append(reason)
    return {
        "row_no": row_no,
        "category": row.get("category", ""),
        "genome_id": genome_id,
        "candidate_index": candidate_index,
        "det_score": round(det_score, 4),
        "det_pass": bool(det_pass),
        "gt_exact": bool(gt_exact),
        "gt_similarity": round(code_sim, 6),
        "schedule_match": bool(cron_match and period_match),
        "cron_match": bool(cron_match),
        "period_match": bool(period_match),
        "code_match": bool(code_match),
        "service_valid": bool(service_valid),
        "receiver_valid": bool(receiver_valid),
        "failure_reasons": unique_reasons,
        "diff_summary": {
            "gt_services": sorted(ref_services),
            "generated_services": sorted(gen_services),
            "gt_receivers": sorted(ref_receivers),
            "generated_receivers": sorted(gen_receivers),
        },
        "gt_code": reference_code,
        "generated_code": generated_code,
        "gt_json": gt_json,
        "generated_json": generated_json,
    }
