#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from .advisor_modes import describe_advisor_mode, validate_advisor_mode
    from .artifacts import utc_now, write_json
except ImportError:
    from advisor_modes import describe_advisor_mode, validate_advisor_mode  # type: ignore
    from artifacts import utc_now, write_json  # type: ignore


FAILURE_TO_FAMILY = {
    "unknown_service": "Service_Mapping",
    "service_match": "Service_Mapping",
    "gt_service_coverage": "Service_Mapping",
    "numeric_grounding": "Temporal_Rule",
    "time_period": "Temporal_Rule",
    "temporal_error": "Temporal_Rule",
    "semantic": "Skeleton",
    "gt_mismatch": "DET_Helper",
    "gt_receiver_coverage": "Receiver_Tag_Preservation",
    "receiver": "Receiver_Tag_Preservation",
    "dataflow": "Dataflow",
    "arg_type": "Enum_Grounding",
    "enum_grounding": "Enum_Grounding",
    "extraneous": "Minimality",
    "invalid_json": "Output_Schema",
    "precondition": "Skeleton",
    "conditions": "Owner_Device_Rule",
    "device_service": "Service_Mapping",
    "semantic_intent": "Skeleton",
    "gpt_semantic": "Skeleton",
}

FAMILY_TO_INTENT = {
    "Service_Mapping": "service_repair",
    "Temporal_Rule": "temporal_repair",
    "Skeleton": "skeleton_repair",
    "DET_Helper": "skeleton_repair",
    "Receiver_Tag_Preservation": "receiver_repair",
    "Owner_Device_Rule": "receiver_repair",
    "Dataflow": "dataflow_repair",
    "Enum_Grounding": "service_repair",
    "Minimality": "minimality_repair",
    "Output_Schema": "minimality_repair",
}

CLOUD_SCORE_COLUMNS = [
    "overall_lang",
    "ls_semantic_intent",
    "ls_conditions",
    "ls_time_period",
    "ls_device_service",
    "overall_gpt",
    "gpt_reconverted_score",
]

CLOUD_REASONING_COLUMNS = [
    "ls_judge_reasoning",
    "gpt_judge_reasoning",
    "gpt_reconverted_reasoning",
]


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def safe_json_loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def str_list(value: Any) -> list[str]:
    return [str(item) for item in as_list(value) if str(item).strip()]


def base_reason(reason: Any) -> str:
    token = str(reason or "").strip()
    if not token:
        return ""
    if token.startswith("unknown_service:"):
        return "unknown_service"
    return token.split(":", 1)[0]


def to_float(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def normalize_score(value: Any) -> float | None:
    score = to_float(value)
    if score is None:
        return None
    if score > 1.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def row_no_from_row(row: dict[str, Any], fallback: int) -> str:
    for key in ("row_no", "index", "row_index"):
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return str(fallback)


def _failure_cluster(failure_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    family = FAILURE_TO_FAMILY.get(failure_type, "DET_Helper")
    return {
        "cluster_id": f"{family.lower()}::{failure_type}",
        "failure_types": [failure_type],
        "rows": [str(row.get("row_no")) for row in rows if str(row.get("row_no") or "").strip()],
        "recommended_block_family": family,
        "mutation_intent": FAMILY_TO_INTENT.get(family, "diversity"),
        "row_count": len(rows),
    }


def _cluster_rows(high_priority_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in high_priority_rows:
        reasons = row.get("local_failure_reasons") or row.get("cloud_failure_dimensions") or ["gt_mismatch"]
        for reason in str_list(reasons):
            grouped[base_reason(reason) or "gt_mismatch"].append(row)
    return [_failure_cluster(reason, rows) for reason, rows in sorted(grouped.items())]


def _base_packet(mode: str, source_files: dict[str, Any], primary_signal: str) -> dict[str, Any]:
    mode_info = describe_advisor_mode(mode)
    return {
        "advisor_mode": mode,
        "created_at": utc_now(),
        "source_files": source_files,
        "primary_signal": primary_signal,
        "official_score_policy": {
            "primary_metric": "strict_det",
            "cloud_is_auxiliary": True,
            "cloud_score_is_official": False,
        },
        "mode_description": mode_info,
        "global_summary": {},
        "failure_clusters": [],
        "high_priority_rows": [],
    }


def resolve_local_report_path(local_det_report: str | None, strict_results_dir: str | None) -> Path:
    if local_det_report:
        path = Path(local_det_report)
        if path.exists():
            return path
        raise FileNotFoundError(f"local DET report not found: {path}")
    if strict_results_dir:
        path = Path(strict_results_dir) / "local_det_failure_report.json"
        if path.exists():
            return path
        raise FileNotFoundError(
            "local_det_failure_report.json not found. Generate it explicitly, for example:\n"
            f"python utils/export_local_det_failure_report.py --results-dir {strict_results_dir} --model-key <model-key>"
        )
    raise FileNotFoundError("advisor-mode local requires --local-det-report or --strict-results-dir")


def build_local_evidence(
    *,
    local_det_report: str | None = None,
    strict_results_dir: str | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    path = resolve_local_report_path(local_det_report, strict_results_dir)
    report = read_json(path)
    rows = report.get("rows", []) if isinstance(report, dict) else []
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows if isinstance(rows, list) else [], start=1):
        if not isinstance(row, dict):
            continue
        reasons = [base_reason(item) for item in str_list(row.get("failure_reasons"))]
        normalized_rows.append(
            {
                "row_no": row_no_from_row(row, index),
                "command_eng": row.get("command_eng", ""),
                "command_kor": row.get("command_kor", ""),
                "gt_code": row.get("gt_code", ""),
                "output_code": row.get("output_code", ""),
                "local_failure_reasons": [item for item in reasons if item],
                "local_concrete_diagnostics": str_list(row.get("concrete_diagnostics")),
                "cloud_scores": {},
                "cloud_reasoning": "",
                "recommended_prompt_mutations": as_list(row.get("recommended_mutations")),
            }
        )
    reason_counter = Counter(
        reason
        for row in normalized_rows
        for reason in row.get("local_failure_reasons", [])
    )
    normalized_rows.sort(
        key=lambda item: (
            -len(item.get("recommended_prompt_mutations") or []),
            -len(item.get("local_concrete_diagnostics") or []),
            str(item.get("row_no")),
        )
    )
    packet = _base_packet(
        "local",
        {"local_det_report": str(path), "strict_results_dir": strict_results_dir or ""},
        "strict_det",
    )
    packet["global_summary"] = {
        "row_count": report.get("metadata", {}).get("row_count", len(rows)) if isinstance(report, dict) else len(rows),
        "failure_count": len(normalized_rows),
        "top_failure_reasons": reason_counter.most_common(20),
        "top_cloud_failure_dimensions": [],
        "available_diagnostics": any(row.get("local_concrete_diagnostics") for row in normalized_rows),
    }
    packet["high_priority_rows"] = normalized_rows[: max(1, top_k)]
    packet["failure_clusters"] = _cluster_rows(packet["high_priority_rows"])
    return packet


def _cloud_failure_dimensions(row: dict[str, str]) -> list[str]:
    dims = []
    dimension_map = {
        "ls_semantic_intent": "semantic_intent",
        "ls_conditions": "conditions",
        "ls_time_period": "time_period",
        "ls_device_service": "device_service",
        "overall_gpt": "gpt_semantic",
    }
    for column, dimension in dimension_map.items():
        score = normalize_score(row.get(column))
        if score is not None and score < 0.8:
            dims.append(dimension)
    return dims


def build_cloud_evidence(*, cloud_judge_csv: str | None, top_k: int = 20) -> dict[str, Any]:
    if not cloud_judge_csv:
        raise FileNotFoundError("advisor-mode cloud requires --cloud-judge-csv")
    path = Path(cloud_judge_csv)
    if not path.exists():
        raise FileNotFoundError(f"cloud judge CSV not found: {path}")
    rows = read_csv(path)
    columns = set(rows[0].keys()) if rows else set()
    missing_columns = [
        column for column in [*CLOUD_SCORE_COLUMNS, *CLOUD_REASONING_COLUMNS] if column not in columns
    ]
    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        cloud_scores = {column: normalize_score(row.get(column)) for column in CLOUD_SCORE_COLUMNS if column in row}
        available = [value for value in cloud_scores.values() if value is not None]
        mean_score = sum(available) / len(available) if available else 1.0
        reasoning_parts = [str(row.get(column) or "").strip() for column in CLOUD_REASONING_COLUMNS if row.get(column)]
        dims = _cloud_failure_dimensions(row)
        if dims or mean_score < 0.8:
            normalized_rows.append(
                {
                    "row_no": row_no_from_row(row, index),
                    "command_eng": row.get("command_eng", ""),
                    "command_kor": row.get("command_kor", ""),
                    "gt_code": row.get("gt_code", ""),
                    "output_code": row.get("output_code", ""),
                    "local_failure_reasons": [],
                    "local_concrete_diagnostics": [],
                    "cloud_scores": cloud_scores,
                    "cloud_reasoning": " | ".join(reasoning_parts)[:2000],
                    "cloud_failure_dimensions": dims or ["gpt_semantic"],
                    "recommended_prompt_mutations": [],
                    "_rank_score": mean_score,
                }
            )
    normalized_rows.sort(key=lambda item: (item.get("_rank_score", 1.0), str(item.get("row_no"))))
    for row in normalized_rows:
        row.pop("_rank_score", None)
    dimension_counter = Counter(
        dim for row in normalized_rows for dim in row.get("cloud_failure_dimensions", [])
    )
    packet = _base_packet("cloud", {"cloud_judge_csv": str(path)}, "cloud_semantic")
    packet["global_summary"] = {
        "row_count": len(rows),
        "failure_count": len(normalized_rows),
        "top_failure_reasons": [],
        "top_cloud_failure_dimensions": dimension_counter.most_common(20),
        "missing_columns": missing_columns,
        "cloud_is_auxiliary": True,
    }
    packet["high_priority_rows"] = normalized_rows[: max(1, top_k)]
    packet["failure_clusters"] = _cluster_rows(packet["high_priority_rows"])
    return packet


def _row_from_rich_feedback(row: dict[str, Any], fallback: int) -> dict[str, Any]:
    strict_det = row.get("strict_det") if isinstance(row.get("strict_det"), dict) else {}
    diagnostics = row.get("local_det_diagnostics") if isinstance(row.get("local_det_diagnostics"), dict) else {}
    lang = row.get("lang_judge") if isinstance(row.get("lang_judge"), dict) else {}
    gpt = row.get("gpt_judge") if isinstance(row.get("gpt_judge"), dict) else {}
    reasons = [base_reason(item) for item in str_list(strict_det.get("failure_reasons"))]
    cloud_scores = {
        "overall_lang": normalize_score(lang.get("overall_lang")),
        "ls_semantic_intent": normalize_score(lang.get("semantic_intent")),
        "ls_conditions": normalize_score(lang.get("conditions")),
        "ls_time_period": normalize_score(lang.get("time_period")),
        "ls_device_service": normalize_score(lang.get("device_service")),
        "overall_gpt": normalize_score(gpt.get("overall_gpt")),
    }
    reasoning = []
    for value in (lang.get("reasoning"), gpt.get("reasoning")):
        if isinstance(value, (dict, list)):
            reasoning.append(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
        elif value:
            reasoning.append(str(value))
    code_comparison = row.get("code_comparison") if isinstance(row.get("code_comparison"), dict) else {}
    return {
        "row_no": row_no_from_row(row, fallback),
        "command_eng": row.get("command_eng", ""),
        "command_kor": row.get("command_kor", ""),
        "gt_code": code_comparison.get("gt_code", ""),
        "output_code": code_comparison.get("output_code", ""),
        "local_failure_reasons": [item for item in reasons if item],
        "local_concrete_diagnostics": str_list(diagnostics.get("concrete_diagnostics")),
        "cloud_scores": cloud_scores,
        "cloud_reasoning": " | ".join(reasoning)[:2000],
        "recommended_prompt_mutations": as_list(diagnostics.get("recommended_mutations")),
        "priority_score": row.get("advisor_priority", {}).get("priority_score")
        if isinstance(row.get("advisor_priority"), dict)
        else None,
    }


def build_hybrid_evidence(
    *,
    advisor_rich_feedback: str | None = None,
    local_det_report: str | None = None,
    strict_results_dir: str | None = None,
    cloud_judge_csv: str | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    if advisor_rich_feedback:
        path = Path(advisor_rich_feedback)
        if not path.exists():
            raise FileNotFoundError(f"advisor rich feedback not found: {path}")
        data = read_json(path)
        rows = data.get("rows", []) if isinstance(data, dict) else []
        normalized_rows = [
            _row_from_rich_feedback(row, index)
            for index, row in enumerate(rows if isinstance(rows, list) else [], start=1)
            if isinstance(row, dict)
        ]
        normalized_rows.sort(
            key=lambda item: (
                -(to_float(item.get("priority_score")) or 0.0),
                str(item.get("row_no")),
            )
        )
        reason_counter = Counter(
            reason for row in normalized_rows for reason in row.get("local_failure_reasons", [])
        )
        packet = _base_packet("hybrid", {"advisor_rich_feedback": str(path)}, "strict_det_plus_cloud")
        packet["global_summary"] = {
            "row_count": data.get("metadata", {}).get("total_strict_rows", len(rows)) if isinstance(data, dict) else len(rows),
            "failure_count": len(normalized_rows),
            "top_failure_reasons": reason_counter.most_common(20),
            "top_cloud_failure_dimensions": [],
            "strict_is_primary": True,
            "cloud_is_auxiliary": True,
        }
        packet["high_priority_rows"] = normalized_rows[: max(1, top_k)]
        packet["failure_clusters"] = _cluster_rows(packet["high_priority_rows"])
        return packet

    local_packet = build_local_evidence(
        local_det_report=local_det_report,
        strict_results_dir=strict_results_dir,
        top_k=top_k,
    )
    cloud_packet = build_cloud_evidence(cloud_judge_csv=cloud_judge_csv, top_k=top_k)
    local_by_row = {str(row.get("row_no")): row for row in local_packet.get("high_priority_rows", [])}
    for cloud_row in cloud_packet.get("high_priority_rows", []):
        key = str(cloud_row.get("row_no"))
        if key in local_by_row:
            local_by_row[key]["cloud_scores"] = cloud_row.get("cloud_scores", {})
            local_by_row[key]["cloud_reasoning"] = cloud_row.get("cloud_reasoning", "")
        else:
            local_by_row[key] = cloud_row
    packet = _base_packet(
        "hybrid",
        {
            "local_det_report": local_packet.get("source_files", {}).get("local_det_report", ""),
            "strict_results_dir": strict_results_dir or "",
            "cloud_judge_csv": cloud_judge_csv or "",
        },
        "strict_det_plus_cloud",
    )
    rows = list(local_by_row.values())[: max(1, top_k)]
    packet["high_priority_rows"] = rows
    packet["failure_clusters"] = _cluster_rows(rows)
    packet["global_summary"] = {
        "row_count": local_packet.get("global_summary", {}).get("row_count", 0),
        "failure_count": len(rows),
        "top_failure_reasons": local_packet.get("global_summary", {}).get("top_failure_reasons", []),
        "top_cloud_failure_dimensions": cloud_packet.get("global_summary", {}).get("top_cloud_failure_dimensions", []),
        "strict_is_primary": True,
        "cloud_is_auxiliary": True,
        "join_strategy": "row_no best effort",
    }
    return packet


def build_evidence_packet(
    *,
    advisor_mode: str,
    strict_results_dir: str | None = None,
    local_det_report: str | None = None,
    cloud_judge_csv: str | None = None,
    advisor_rich_feedback: str | None = None,
    top_k: int = 20,
) -> dict[str, Any]:
    mode = validate_advisor_mode(advisor_mode)
    if mode == "none":
        return _base_packet("none", {}, "base_prompt")
    if mode == "local":
        return build_local_evidence(
            local_det_report=local_det_report,
            strict_results_dir=strict_results_dir,
            top_k=top_k,
        )
    if mode == "cloud":
        return build_cloud_evidence(cloud_judge_csv=cloud_judge_csv, top_k=top_k)
    return build_hybrid_evidence(
        advisor_rich_feedback=advisor_rich_feedback,
        local_det_report=local_det_report,
        strict_results_dir=strict_results_dir,
        cloud_judge_csv=cloud_judge_csv,
        top_k=top_k,
    )


def write_evidence_packet(packet: dict[str, Any], out_path: str | Path) -> None:
    write_json(out_path, packet)
