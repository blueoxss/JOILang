#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from typing import Any


SERVICE_CALL_RE = re.compile(r"\([^)]*\)\.([A-Za-z_][A-Za-z0-9_]*)")
SERVICE_CALL_WITH_ARGS_RE = re.compile(r"\([^)]*\)\.([A-Za-z_][A-Za-z0-9_]*)\(([^()]*)\)")
RECEIVER_RE = re.compile(r"\(([^)]*)\)\.")
NUMERIC_RE = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?")
STRING_ARG_RE = re.compile(r"['\"]([^'\"]+)['\"]")


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


def extract_numeric_literals(code: str) -> list[str]:
    return NUMERIC_RE.findall(str(code or ""))


def extract_string_args(code: str) -> list[str]:
    return [normalize_text(item).lower() for item in STRING_ARG_RE.findall(str(code or ""))]


def coverage_score(reference_items: list[str], generated_items: list[str]) -> float:
    if not reference_items:
        return 1.0
    ref_counter = Counter(reference_items)
    gen_counter = Counter(generated_items)
    covered = sum(min(count, gen_counter.get(item, 0)) for item, count in ref_counter.items())
    return covered / sum(ref_counter.values())


def precision_score(reference_items: list[str], generated_items: list[str]) -> float:
    if not generated_items:
        return 1.0 if not reference_items else 0.0
    ref_counter = Counter(reference_items)
    gen_counter = Counter(generated_items)
    matched = sum(min(count, ref_counter.get(item, 0)) for item, count in gen_counter.items())
    return matched / sum(gen_counter.values())


def dataflow_heuristic_score(reference_code: str, generated_code: str) -> float:
    ref_assignments = len(re.findall(r"\b(?:var|let|const)\s+[A-Za-z_][A-Za-z0-9_]*\s*=", reference_code or ""))
    gen_assignments = len(re.findall(r"\b(?:var|let|const)\s+[A-Za-z_][A-Za-z0-9_]*\s*=", generated_code or ""))
    if ref_assignments == 0:
        return 1.0
    if gen_assignments >= ref_assignments:
        return 1.0
    return gen_assignments / ref_assignments


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

    ref_service_list = extract_services(reference_code)
    gen_service_list = extract_services(generated_code)
    ref_services = Counter(ref_service_list)
    gen_services = Counter(gen_service_list)
    service_coverage = coverage_score(ref_service_list, gen_service_list)
    service_precision = precision_score(ref_service_list, gen_service_list)
    service_valid = service_coverage >= 0.999 and service_precision >= 0.5
    if ref_services and service_coverage < 0.999:
        failure_reasons.append("gt_service_coverage")
    if gen_services and service_precision < 0.999:
        failure_reasons.append("unknown_service")

    ref_receiver_list = extract_receivers(reference_code)
    gen_receiver_list = extract_receivers(generated_code)
    ref_receivers = set(ref_receiver_list)
    gen_receivers = set(gen_receiver_list)
    receiver_coverage = coverage_score(ref_receiver_list, gen_receiver_list)
    receiver_valid = receiver_coverage >= 0.999
    if not receiver_valid:
        failure_reasons.append("gt_receiver_coverage")

    numeric_grounding = coverage_score(extract_numeric_literals(reference_code), extract_numeric_literals(generated_code))
    if numeric_grounding < 0.999:
        failure_reasons.append("numeric_grounding")
    enum_grounding = coverage_score(extract_string_args(reference_code), extract_string_args(generated_code))
    if enum_grounding < 0.999:
        failure_reasons.append("enum_grounding")
    dataflow_score = dataflow_heuristic_score(reference_code, generated_code)
    if dataflow_score < 0.999:
        failure_reasons.append("dataflow")

    schedule_score = 1.0 if cron_match and period_match else (0.5 if cron_match or period_match else 0.0)
    det_score = 100.0 * (
        0.30 * code_sim
        + 0.15 * schedule_score
        + 0.15 * service_coverage
        + 0.10 * service_precision
        + 0.10 * receiver_coverage
        + 0.10 * numeric_grounding
        + 0.05 * enum_grounding
        + 0.05 * dataflow_score
    )
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
        "gt_service_coverage": round(service_coverage, 6),
        "gt_service_precision": round(service_precision, 6),
        "gt_receiver_coverage": round(receiver_coverage, 6),
        "dataflow_score": round(dataflow_score, 6),
        "numeric_grounding": round(numeric_grounding, 6),
        "enum_grounding": round(enum_grounding, 6),
        "failure_reasons": unique_reasons,
        "diff_summary": {
            "gt_services": sorted(ref_services),
            "generated_services": sorted(gen_services),
            "gt_receivers": sorted(ref_receivers),
            "generated_receivers": sorted(gen_receivers),
            "gt_numeric_literals": extract_numeric_literals(reference_code),
            "generated_numeric_literals": extract_numeric_literals(generated_code),
            "gt_string_args": extract_string_args(reference_code),
            "generated_string_args": extract_string_args(generated_code),
        },
        "gt_code": reference_code,
        "generated_code": generated_code,
        "gt_json": gt_json,
        "generated_json": generated_json,
    }
