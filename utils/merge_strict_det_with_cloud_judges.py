#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.feedback_generation_state import (
    classify_generation_state,
    component_score_policy,
    root_cause_summary_for_state,
)


STRICT_REQUIRED_FILES = [
    "row_comparison.csv",
    "failure_reason_summary.csv",
    "local_det_failure_report.json",
]

STRICT_ROW_FIELDS = [
    "row_no",
    "category",
    "command_eng",
    "command_kor",
    "gt_cron",
    "gt_period",
    "gt_code",
    "output_cron",
    "output_period",
    "output_code",
    "det_score",
    "det_pass",
    "det_gt_exact",
    "det_gt_similarity",
    "det_gt_service_coverage",
    "det_gt_service_precision",
    "det_gt_receiver_coverage",
    "det_dataflow_score",
    "det_numeric_grounding",
    "det_enum_grounding",
    "failure_reasons",
]

CLOUD_FIELDS = [
    "overall_lang",
    "ls_semantic_intent",
    "ls_conditions",
    "ls_time_period",
    "ls_device_service",
    "ls_judge_reasoning",
    "overall_gpt",
    "gpt_judge_reasoning",
    "gpt_reconverted_reference_sentence",
    "gpt_reconverted_sentence",
    "gpt_reconverted_same",
    "gpt_reconverted_score",
    "gpt_reconverted_reasoning",
    "llm_prompt_tokens",
    "llm_completion_tokens",
    "llm_total_tokens",
    "response_time",
    "report_time",
]

CSV_COLUMNS = [
    "row_no",
    "category",
    "command_eng",
    "command_kor",
    "strict_det_score",
    "strict_det_pass",
    "strict_gt_exact",
    "strict_failure_reasons",
    "concrete_diagnostics",
    "recommended_mutations",
    "overall_lang",
    "ls_semantic_intent",
    "ls_conditions",
    "ls_time_period",
    "ls_device_service",
    "ls_judge_reasoning",
    "overall_gpt",
    "gpt_judge_reasoning",
    "priority_score",
    "priority_level",
    "generation_state_class",
    "evidence_quality",
    "root_cause_summary",
    "suppressed_mutations",
    "gt_code",
    "output_code",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge official strict DET artifacts with auxiliary cloud semantic "
            "judge CSVs into advisor rich feedback."
        )
    )
    parser.add_argument("--strict-results-dir", required=True)
    parser.add_argument("--cloud-judge-csv", required=True)
    parser.add_argument("--model-key", default="gpt41_mini")
    parser.add_argument("--join-key", default="auto")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--include-pass", action="store_true")
    return parser.parse_args()


def die(message: str, code: int = 2) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: csv_cell(row.get(col, "")) for col in columns})


def csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def normalize_join_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return ""
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except Exception:
        pass
    return text


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def normalize_score(value: Any) -> float | None:
    score = as_float(value)
    if score is None:
        return None
    if score > 1.0:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "pass"}:
        return True
    if text in {"0", "false", "no", "n", "fail"}:
        return False
    return None


def safe_json_or_literal(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return default
    for loader in (json.loads, ast.literal_eval):
        try:
            return loader(text)
        except Exception:
            continue
    return default


def parse_list_like(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    parsed = safe_json_or_literal(value, None)
    if isinstance(parsed, list):
        return parsed
    if parsed not in (None, ""):
        return [parsed]
    text = str(value or "").strip()
    if not text:
        return []
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def parse_reasoning(value: Any) -> Any:
    parsed = safe_json_or_literal(value, None)
    if parsed is not None:
        return parsed
    return str(value or "").strip()


def base_reason(reason: str) -> str:
    token = str(reason or "").strip()
    if token.startswith("unknown_service:"):
        return "unknown_service"
    return token.split(":", 1)[0] if ":" in token else token


def model_get(row: dict[str, str], model_key: str, key: str, default: str = "") -> str:
    return str(row.get(f"{model_key}__{key}", row.get(key, default)) or "")


def ensure_required_inputs(strict_dir: Path, model_key: str) -> None:
    missing = [name for name in STRICT_REQUIRED_FILES if not (strict_dir / name).exists()]
    if "local_det_failure_report.json" in missing:
        die(
            "Required strict DET report missing: "
            f"{strict_dir / 'local_det_failure_report.json'}\n\n"
            "Create it with:\n"
            "python utils/export_local_det_failure_report.py \\\n"
            f"  --results-dir {strict_dir} \\\n"
            f"  --model-key {model_key}"
        )
    if missing:
        die("Missing required strict DET artifact(s): " + ", ".join(missing))


def choose_cloud_join_key(fieldnames: list[str], join_key: str) -> str:
    if join_key != "auto":
        if join_key in {"position", "row_position", "__row_position__"}:
            return "__row_position__"
        if join_key not in fieldnames:
            die(
                f"Requested cloud join key '{join_key}' not found.\n"
                f"Cloud columns: {fieldnames}"
            )
        return join_key
    if "row_no" in fieldnames:
        return "row_no"
    if "index" in fieldnames:
        return "index"
    return "__row_position__"


def index_cloud_rows(
    rows: list[dict[str, str]],
    fieldnames: list[str],
    join_key: str,
) -> tuple[dict[str, dict[str, str]], set[str], int, str]:
    chosen_key = choose_cloud_join_key(fieldnames, join_key)
    indexed: dict[str, dict[str, str]] = {}
    keys: set[str] = set()
    duplicates = 0
    for pos, row in enumerate(rows):
        raw_key = pos if chosen_key == "__row_position__" else row.get(chosen_key, "")
        key = normalize_join_value(raw_key)
        if not key:
            continue
        keys.add(key)
        if key in indexed:
            duplicates += 1
            continue
        indexed[key] = row
    return indexed, keys, duplicates, chosen_key


def duplicate_key_count(rows: list[dict[str, str]], key_name: str) -> int:
    counts: Counter[str] = Counter()
    for pos, row in enumerate(rows):
        raw = pos if key_name == "__row_position__" else row.get(key_name, "")
        key = normalize_join_value(raw)
        if key:
            counts[key] += 1
    return sum(1 for count in counts.values() if count > 1)


def assess_join_quality(
    *,
    strict_rows: list[dict[str, str]],
    cloud_rows: list[dict[str, str]],
    strict_keys: set[str],
    cloud_keys: set[str],
    joined_keys: set[str],
    chosen_join_key: str,
    cloud_duplicates: int,
) -> dict[str, Any]:
    strict_duplicates = duplicate_key_count(strict_rows, "row_no")
    row_position_join = chosen_join_key == "__row_position__"
    ordered_ok = bool(row_position_join and len(strict_rows) == len(cloud_rows) and not strict_duplicates and not cloud_duplicates)
    if strict_duplicates or cloud_duplicates:
        quality = "bad"
        usable = False
        mode = "strict_only_fallback"
        reason = "duplicate_join_key"
    elif row_position_join and not ordered_ok:
        quality = "bad"
        usable = False
        mode = "strict_only_fallback"
        reason = "unverified_index_join"
    elif len(joined_keys) == len(strict_keys) and len(strict_keys) > 0:
        quality = "good"
        usable = True
        mode = "hybrid"
        reason = "row_no_match" if chosen_join_key == "row_no" else "verified_index_fallback"
    elif joined_keys:
        quality = "partial"
        usable = True
        mode = "cloud_only_auxiliary"
        reason = "partial_join"
    else:
        quality = "bad"
        usable = False
        mode = "strict_only_fallback"
        reason = "missing_join"
    return {
        "join_quality": quality,
        "join_reason": reason,
        "cloud_feedback_usable_for_priority": usable,
        "effective_feedback_mode": mode,
        "chosen_join_key": chosen_join_key,
        "strict_duplicate_join_keys": strict_duplicates,
        "cloud_duplicate_join_keys": cloud_duplicates,
        "joined_rows": len(joined_keys),
        "strict_only_rows": len(strict_keys - cloud_keys),
        "cloud_only_rows": len(cloud_keys - strict_keys),
    }


def load_failure_report(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows", []) if isinstance(data, dict) else []
    by_row: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = normalize_join_value(row.get("row_no"))
        if key:
            by_row[key] = row
    return by_row, data if isinstance(data, dict) else {}


def load_top_failure_reasons(path: Path, model_key: str) -> list[dict[str, Any]]:
    rows, _ = read_csv(path)
    out = []
    for row in rows:
        if row.get("model_key") and row.get("model_key") != model_key:
            continue
        count = as_float(row.get("count")) or 0.0
        out.append({"failure_reason": row.get("failure_reason", ""), "count": int(count)})
    return sorted(out, key=lambda item: item["count"], reverse=True)


def collect_top_mutation_blocks(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in report_rows:
        for mutation in parse_list_like(row.get("recommended_mutations", [])):
            if not isinstance(mutation, dict):
                continue
            block = (
                mutation.get("target_block_family")
                or mutation.get("target_block_id")
                or mutation.get("suggested_mutation_type")
                or "unknown"
            )
            counts[str(block)] += 1
    return [{"mutation_block": key, "count": count} for key, count in counts.most_common()]


def component_scores(strict_row: dict[str, str], model_key: str) -> dict[str, float | None]:
    return component_score_policy(strict_row, model_key)


def mutation_present(report_row: dict[str, Any]) -> bool:
    return bool(parse_list_like(report_row.get("recommended_mutations", [])))


def compute_priority(
    det_score: Any,
    det_pass: bool | None,
    overall_lang: Any,
    overall_gpt: Any,
    has_mutations: bool,
    use_cloud_scores: bool = True,
) -> dict[str, Any]:
    det_norm = normalize_score(det_score)
    lang_norm = normalize_score(overall_lang) if use_cloud_scores else None
    gpt_norm = normalize_score(overall_gpt) if use_cloud_scores else None
    if det_norm is None:
        det_norm = 0.0

    w_det = 0.45
    w_lang = 0.20
    w_gpt = 0.20
    w_mut = 0.15
    missing = []
    if lang_norm is None:
        w_det += w_lang
        w_lang = 0.0
        missing.append("lang")
    if gpt_norm is None:
        w_det += w_gpt
        w_gpt = 0.0
        missing.append("gpt")

    priority = w_det * (1.0 - det_norm)
    if lang_norm is not None:
        priority += w_lang * (1.0 - lang_norm)
    if gpt_norm is not None:
        priority += w_gpt * (1.0 - gpt_norm)
    priority += w_mut * (1.0 if has_mutations else 0.0)
    if det_pass is False:
        priority += 0.10
    priority = max(0.0, min(1.0, priority))

    if priority >= 0.70:
        level = "high"
    elif priority >= 0.40:
        level = "medium"
    else:
        level = "low"

    reason_bits = [f"strict_det_norm={det_norm:.3f}"]
    if missing:
        reason_bits.append("missing " + "/".join(missing) + " redistributed to strict DET")
    if not use_cloud_scores:
        reason_bits.append("cloud priority disabled by join/status quality; strict_only_fallback")
    if has_mutations:
        reason_bits.append("recommended_mutations present")
    if det_pass is False:
        reason_bits.append("det_pass=false boost applied")

    return {
        "priority_score": round(priority, 6),
        "priority_level": level,
        "reason": "; ".join(reason_bits),
    }


def cloud_available(row: dict[str, str] | None, fields: list[str]) -> bool:
    if not row:
        return False
    return any(str(row.get(field, "")).strip() for field in fields)


def cloud_score_status(
    cloud_row: dict[str, str] | None,
    *,
    score_key: str,
    status_key: str,
    valid_key: str,
    error_key: str,
    skip_key: str,
    reasoning_key: str,
) -> dict[str, Any]:
    if not cloud_row:
        return {
            "available": False,
            "valid_score": False,
            "status": "missing_join",
            "score": None,
            "error_type": "",
            "skip_reason": "missing_join",
        }
    raw_status = str(cloud_row.get(status_key, "") or "").strip()
    raw_valid = as_bool(cloud_row.get(valid_key))
    error_type = str(cloud_row.get(error_key, "") or "").strip()
    skip_reason = str(cloud_row.get(skip_key, "") or "").strip()
    reasoning = str(cloud_row.get(reasoning_key, "") or "").lower()
    score = as_float(cloud_row.get(score_key))
    if raw_valid is True and score is not None:
        status = raw_status or "valid_score"
        valid = True
    elif raw_status:
        status = raw_status
        valid = False
    elif "skipped (empty code)" in reasoning or "empty code" in reasoning:
        status = "empty_code_skipped"
        skip_reason = skip_reason or "empty_code"
        valid = False
    elif "error" in reasoning or error_type:
        status = "judge_runtime_error"
        error_type = error_type or "judge_runtime_error"
        valid = False
    elif score is not None:
        status = "valid_score"
        valid = True
    else:
        status = "missing_or_error"
        valid = False
    return {
        "available": True,
        "valid_score": bool(valid),
        "status": status,
        "score": score if valid else None,
        "error_type": error_type,
        "skip_reason": skip_reason,
    }


def build_advisor_row(
    strict_row: dict[str, str],
    cloud_row: dict[str, str] | None,
    report_row: dict[str, Any],
    model_key: str,
    join_quality: dict[str, Any],
) -> dict[str, Any]:
    failure_reasons = [
        str(reason)
        for reason in parse_list_like(model_get(strict_row, model_key, "failure_reasons"))
        if str(reason).strip()
    ]
    if not failure_reasons:
        failure_reasons = [
            str(reason)
            for reason in parse_list_like(report_row.get("failure_reasons", []))
            if str(reason).strip()
        ]

    det_score = as_float(model_get(strict_row, model_key, "det_score"))
    det_pass = as_bool(model_get(strict_row, model_key, "det_pass"))
    gt_exact = as_bool(model_get(strict_row, model_key, "det_gt_exact"))
    state = classify_generation_state(strict_row, model_key)
    lang_status = cloud_score_status(
        cloud_row,
        score_key="overall_lang",
        status_key="ls_judge_status",
        valid_key="ls_valid_score",
        error_key="ls_error_type",
        skip_key="ls_skip_reason",
        reasoning_key="ls_judge_reasoning",
    )
    gpt_status = cloud_score_status(
        cloud_row,
        score_key="overall_gpt",
        status_key="gpt_judge_status",
        valid_key="gpt_valid_score",
        error_key="gpt_error_type",
        skip_key="gpt_skip_reason",
        reasoning_key="gpt_judge_reasoning",
    )
    use_cloud_priority = bool(join_quality.get("cloud_feedback_usable_for_priority")) and (
        bool(lang_status["valid_score"]) or bool(gpt_status["valid_score"])
    )
    overall_lang = lang_status["score"]
    overall_gpt = gpt_status["score"]
    has_mutations = mutation_present(report_row)
    priority = compute_priority(det_score, det_pass, overall_lang, overall_gpt, has_mutations, use_cloud_scores=use_cloud_priority)

    ls_reasoning = parse_reasoning((cloud_row or {}).get("ls_judge_reasoning", ""))
    gpt_reasoning = parse_reasoning((cloud_row or {}).get("gpt_judge_reasoning", ""))

    return {
        "row_no": strict_row.get("row_no", ""),
        "category": strict_row.get("category", ""),
        "command_eng": strict_row.get("command_eng", ""),
        "command_kor": strict_row.get("command_kor", ""),
        "strict_det": {
            "det_score": det_score,
            "det_pass": det_pass,
            "gt_exact": gt_exact,
            "failure_reasons": failure_reasons,
            "component_scores": component_scores(strict_row, model_key),
        },
        "generation_state": state,
        "generation_health": {
            "output_empty": bool(state.get("parsed_fields_empty")),
            "runtime_error_type": state.get("runtime_error_type", ""),
            "oom_flag": state.get("class") == "generation_cuda_oom",
            "prompt_mutation_allowed": state.get("class") != "valid_json_empty_behavior_match",
        },
        "evidence_quality": {
            "strict_det": "valid",
            "cloud_lang": lang_status["status"],
            "cloud_gpt": gpt_status["status"],
            "join_quality": join_quality.get("join_quality"),
            "effective_feedback_mode": join_quality.get("effective_feedback_mode"),
            "cloud_feedback_usable_for_priority": bool(join_quality.get("cloud_feedback_usable_for_priority")),
        },
        "root_cause_summary": root_cause_summary_for_state(state),
        "suppressed_mutations": state.get("suppressed_mutations", []),
        "code_comparison": {
            "gt_cron": strict_row.get("gt_cron", ""),
            "gt_period": strict_row.get("gt_period", ""),
            "gt_code": strict_row.get("gt_code", ""),
            "output_cron": model_get(strict_row, model_key, "output_cron"),
            "output_period": model_get(strict_row, model_key, "output_period"),
            "output_code": model_get(strict_row, model_key, "output_code"),
        },
        "local_det_diagnostics": {
            "concrete_diagnostics": parse_list_like(report_row.get("concrete_diagnostics", [])),
            "automatic_explanations": parse_list_like(report_row.get("automatic_explanations", [])),
            "resolved_services": parse_list_like(report_row.get("resolved_services", [])),
            "recommended_mutations": parse_list_like(report_row.get("recommended_mutations", [])),
        },
        "lang_judge": {
            "available": cloud_available(
                cloud_row,
                [
                    "overall_lang",
                    "ls_semantic_intent",
                    "ls_conditions",
                    "ls_time_period",
                    "ls_device_service",
                    "ls_judge_reasoning",
                ],
            ),
            "valid_score": lang_status["valid_score"],
            "status": lang_status["status"],
            "error_type": lang_status["error_type"],
            "skip_reason": lang_status["skip_reason"],
            "overall_lang": overall_lang,
            "semantic_intent": as_float((cloud_row or {}).get("ls_semantic_intent")) if lang_status["valid_score"] else None,
            "conditions": as_float((cloud_row or {}).get("ls_conditions")) if lang_status["valid_score"] else None,
            "time_period": as_float((cloud_row or {}).get("ls_time_period")) if lang_status["valid_score"] else None,
            "device_service": as_float((cloud_row or {}).get("ls_device_service")) if lang_status["valid_score"] else None,
            "reasoning": ls_reasoning,
        },
        "gpt_judge": {
            "available": cloud_available(
                cloud_row,
                [
                    "overall_gpt",
                    "gpt_judge_reasoning",
                    "gpt_reconverted_reference_sentence",
                    "gpt_reconverted_sentence",
                    "gpt_reconverted_score",
                    "gpt_reconverted_reasoning",
                ],
            ),
            "valid_score": gpt_status["valid_score"],
            "status": gpt_status["status"],
            "error_type": gpt_status["error_type"],
            "skip_reason": gpt_status["skip_reason"],
            "overall_gpt": overall_gpt,
            "reasoning": gpt_reasoning,
            "reconverted": {
                "reference_sentence": (cloud_row or {}).get("gpt_reconverted_reference_sentence", ""),
                "sentence": (cloud_row or {}).get("gpt_reconverted_sentence", ""),
                "same": as_bool((cloud_row or {}).get("gpt_reconverted_same")),
                "score": as_float((cloud_row or {}).get("gpt_reconverted_score")),
                "reasoning": parse_reasoning((cloud_row or {}).get("gpt_reconverted_reasoning", "")),
            },
        },
        "cloud_usage": {
            key: (as_float((cloud_row or {}).get(key)) if key not in {"response_time", "report_time"} else as_float((cloud_row or {}).get(key)))
            for key in [
                "llm_prompt_tokens",
                "llm_completion_tokens",
                "llm_total_tokens",
                "response_time",
                "report_time",
            ]
        },
        "advisor_priority": priority,
    }


def mean_or_none(values: list[float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return round(mean(clean), 6) if clean else None


def summarize(
    strict_rows: list[dict[str, str]],
    advisor_rows: list[dict[str, Any]],
    failure_summary: list[dict[str, Any]],
    mutation_summary: list[dict[str, Any]],
    model_key: str,
) -> dict[str, Any]:
    det_scores = [as_float(model_get(row, model_key, "det_score")) for row in strict_rows]
    det_failed = sum(1 for row in strict_rows if as_bool(model_get(row, model_key, "det_pass")) is False)
    root_causes = Counter(
        str((row.get("root_cause_summary") or {}).get("root_cause") or "")
        for row in advisor_rows
        if str((row.get("root_cause_summary") or {}).get("root_cause") or "").strip()
    )
    actionable_families = Counter()
    suppressed = Counter()
    for row in advisor_rows:
        for mutation in parse_list_like((row.get("local_det_diagnostics") or {}).get("recommended_mutations", [])):
            if isinstance(mutation, dict):
                family = str(mutation.get("target_block_family") or "").strip()
                if family:
                    actionable_families[family] += 1
        for family in parse_list_like(row.get("suppressed_mutations", [])):
            if str(family).strip():
                suppressed[str(family)] += 1
    return {
        "mean_strict_det_score": mean_or_none(det_scores),
        "strict_det_failed_rows": det_failed,
        "mean_overall_lang": mean_or_none([row["lang_judge"].get("overall_lang") for row in advisor_rows]),
        "mean_overall_gpt": mean_or_none([row["gpt_judge"].get("overall_gpt") for row in advisor_rows]),
        "top_failure_reasons": failure_summary[:20],
        "top_root_causes": [{"root_cause": key, "count": count} for key, count in root_causes.most_common(20)],
        "top_mutation_blocks": mutation_summary[:20],
        "actionable_prompt_mutation_counts": dict(actionable_families.most_common()),
        "suppressed_mutations": dict(suppressed.most_common()),
    }


def failure_cloud_correlation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"lang": [], "gpt": []})
    counts: Counter[str] = Counter()
    for row in rows:
        for reason in row["strict_det"].get("failure_reasons", []):
            key = base_reason(reason)
            counts[key] += 1
            lang = row["lang_judge"].get("overall_lang")
            gpt = row["gpt_judge"].get("overall_gpt")
            if lang is not None:
                buckets[key]["lang"].append(float(lang))
            if gpt is not None:
                buckets[key]["gpt"].append(float(gpt))
    out = []
    for reason, count in counts.most_common():
        out.append(
            {
                "failure_reason": reason,
                "count": count,
                "mean_overall_lang": mean_or_none(buckets[reason]["lang"]),
                "mean_overall_gpt": mean_or_none(buckets[reason]["gpt"]),
            }
        )
    return out


def average_for_reasons(rows: list[dict[str, Any]], reasons: set[str], lang_key: str | None, gpt: bool = False) -> float | None:
    values: list[float | None] = []
    for row in rows:
        row_reasons = {base_reason(reason) for reason in row["strict_det"].get("failure_reasons", [])}
        if not row_reasons.intersection(reasons):
            continue
        if gpt:
            values.append(row["gpt_judge"].get("overall_gpt"))
        elif lang_key:
            values.append(row["lang_judge"].get(lang_key))
    return mean_or_none(values)


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def csv_rows_from_advisor(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        out.append(
            {
                "row_no": row.get("row_no", ""),
                "category": row.get("category", ""),
                "command_eng": row.get("command_eng", ""),
                "command_kor": row.get("command_kor", ""),
                "strict_det_score": row["strict_det"].get("det_score"),
                "strict_det_pass": row["strict_det"].get("det_pass"),
                "strict_gt_exact": row["strict_det"].get("gt_exact"),
                "strict_failure_reasons": row["strict_det"].get("failure_reasons", []),
                "concrete_diagnostics": row["local_det_diagnostics"].get("concrete_diagnostics", []),
                "recommended_mutations": row["local_det_diagnostics"].get("recommended_mutations", []),
                "overall_lang": row["lang_judge"].get("overall_lang"),
                "ls_semantic_intent": row["lang_judge"].get("semantic_intent"),
                "ls_conditions": row["lang_judge"].get("conditions"),
                "ls_time_period": row["lang_judge"].get("time_period"),
                "ls_device_service": row["lang_judge"].get("device_service"),
                "ls_judge_reasoning": row["lang_judge"].get("reasoning"),
                "overall_gpt": row["gpt_judge"].get("overall_gpt"),
                "gpt_judge_reasoning": row["gpt_judge"].get("reasoning"),
                "priority_score": row["advisor_priority"].get("priority_score"),
                "priority_level": row["advisor_priority"].get("priority_level"),
                "generation_state_class": (row.get("generation_state") or {}).get("class", ""),
                "evidence_quality": row.get("evidence_quality", {}),
                "root_cause_summary": row.get("root_cause_summary", {}),
                "suppressed_mutations": row.get("suppressed_mutations", []),
                "gt_code": row["code_comparison"].get("gt_code", ""),
                "output_code": row["code_comparison"].get("output_code", ""),
            }
        )
    return out


def shorten(value: Any, limit: int = 1200) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n... <truncated>"


def mutation_lines(mutations: list[Any]) -> list[str]:
    lines = []
    for item in mutations:
        if not isinstance(item, dict):
            lines.append(str(item))
            continue
        block = item.get("target_block_family") or item.get("target_block_id") or "unknown"
        rule = item.get("micro_rule") or item.get("suggested_mutation_type") or ""
        lines.append(f"{block}: {rule}")
    return lines


def write_markdown(
    path: Path,
    metadata: dict[str, Any],
    summary: dict[str, Any],
    rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
) -> None:
    correlations = failure_cloud_correlation(all_rows)
    lines: list[str] = []
    lines.append("# Hybrid Strict DET + Cloud Semantic Judge Report")
    lines.append("")
    lines.append("## 1. Summary")
    lines.append(f"- total strict rows: {metadata['total_strict_rows']}")
    lines.append(f"- joined cloud rows: {metadata['joined_rows']}")
    lines.append(f"- strict-only rows: {metadata['strict_only_rows']}")
    lines.append(f"- cloud-only rows: {metadata['cloud_only_rows']}")
    lines.append(f"- join quality: {metadata.get('join_quality')} ({metadata.get('join_reason')})")
    lines.append(f"- effective feedback mode: {metadata.get('effective_feedback_mode')}")
    lines.append(f"- strict DET failed rows: {summary['strict_det_failed_rows']}")
    lines.append(f"- mean strict_det_score: {summary['mean_strict_det_score']}")
    lines.append(f"- mean overall_lang: {summary['mean_overall_lang']}")
    lines.append(f"- mean overall_gpt: {summary['mean_overall_gpt']}")
    lines.append("- top failure reasons:")
    for item in summary["top_failure_reasons"][:10]:
        lines.append(f"  - {item.get('failure_reason')}: {item.get('count')}")
    lines.append("- top recommended mutation blocks:")
    for item in summary["top_mutation_blocks"][:10]:
        lines.append(f"  - {item.get('mutation_block')}: {item.get('count')}")
    lines.append("- top root causes:")
    for item in summary.get("top_root_causes", [])[:10]:
        lines.append(f"  - {item.get('root_cause')}: {item.get('count')}")
    lines.append("")
    lines.append("## 2. Failure reason × cloud judge correlation")
    lines.append("")
    lines.append("| failure_reason | count | mean overall_lang | mean overall_gpt |")
    lines.append("|---|---:|---:|---:|")
    for item in correlations[:30]:
        lines.append(
            f"| {item['failure_reason']} | {item['count']} | "
            f"{item['mean_overall_lang']} | {item['mean_overall_gpt']} |"
        )
    lines.append("")
    lines.append("- numeric_grounding ↔ ls_time_period mean: "
                 f"{average_for_reasons(all_rows, {'numeric_grounding'}, 'time_period')}")
    lines.append("- unknown_service/service_match/gt_service_coverage ↔ ls_device_service mean: "
                 f"{average_for_reasons(all_rows, {'unknown_service', 'service_match', 'gt_service_coverage'}, 'device_service')}")
    lines.append("- semantic/gt_mismatch ↔ ls_semantic_intent mean: "
                 f"{average_for_reasons(all_rows, {'semantic', 'gt_mismatch'}, 'semantic_intent')}")
    lines.append("- semantic/gt_mismatch ↔ GPT mean: "
                 f"{average_for_reasons(all_rows, {'semantic', 'gt_mismatch'}, None, gpt=True)}")
    lines.append("- gt_receiver_coverage ↔ conditions mean: "
                 f"{average_for_reasons(all_rows, {'gt_receiver_coverage'}, 'conditions')}")
    lines.append("- gt_receiver_coverage ↔ device_service mean: "
                 f"{average_for_reasons(all_rows, {'gt_receiver_coverage'}, 'device_service')}")
    lines.append("")
    lines.append("## 3. High-priority advisor rows")
    if not rows:
        lines.append("")
        lines.append("No rows selected after filters.")
    for row in rows:
        priority = row["advisor_priority"]
        lines.append("")
        lines.append(
            f"### Row {row.get('row_no')} - {priority.get('priority_level')} "
            f"({priority.get('priority_score')})"
        )
        lines.append(f"- command_eng: {shorten(row.get('command_eng'), 500)}")
        lines.append(f"- command_kor: {shorten(row.get('command_kor'), 500)}")
        lines.append(f"- strict DET failure reasons: {', '.join(row['strict_det'].get('failure_reasons', []))}")
        diagnostics = row["local_det_diagnostics"].get("concrete_diagnostics", [])
        lines.append("- concrete diagnostics:")
        for item in diagnostics[:8]:
            lines.append(f"  - {shorten(item, 500)}")
        lines.append("- Lang judge scores/rationales:")
        lines.append(f"  - overall_lang: {row['lang_judge'].get('overall_lang')}")
        lines.append(f"  - semantic_intent: {row['lang_judge'].get('semantic_intent')}")
        lines.append(f"  - conditions: {row['lang_judge'].get('conditions')}")
        lines.append(f"  - time_period: {row['lang_judge'].get('time_period')}")
        lines.append(f"  - device_service: {row['lang_judge'].get('device_service')}")
        lines.append(f"  - reasoning: {shorten(compact_json(row['lang_judge'].get('reasoning')), 900)}")
        lines.append("- GPT judge:")
        lines.append(f"  - overall_gpt: {row['gpt_judge'].get('overall_gpt')}")
        lines.append(f"  - reasoning: {shorten(row['gpt_judge'].get('reasoning'), 900)}")
        lines.append("- recommended prompt mutation block/micro-rule:")
        for item in mutation_lines(row["local_det_diagnostics"].get("recommended_mutations", []))[:10]:
            lines.append(f"  - {shorten(item, 700)}")
        lines.append("- GT code:")
        lines.append("```")
        lines.append(shorten(row["code_comparison"].get("gt_code", ""), 2000))
        lines.append("```")
        lines.append("- output code:")
        lines.append("```")
        lines.append(shorten(row["code_comparison"].get("output_code", ""), 2000))
        lines.append("```")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    strict_dir = Path(args.strict_results_dir)
    cloud_csv = Path(args.cloud_judge_csv)
    out_dir = Path(args.out_dir)

    if not strict_dir.exists():
        die(f"strict-results-dir not found: {strict_dir}")
    if not cloud_csv.exists():
        die(f"cloud-judge-csv not found: {cloud_csv}")
    ensure_required_inputs(strict_dir, args.model_key)

    strict_rows, strict_columns = read_csv(strict_dir / "row_comparison.csv")
    cloud_rows, cloud_columns = read_csv(cloud_csv)
    failure_summary = load_top_failure_reasons(strict_dir / "failure_reason_summary.csv", args.model_key)
    report_by_row, failure_report = load_failure_report(strict_dir / "local_det_failure_report.json")
    report_rows = failure_report.get("rows", []) if isinstance(failure_report, dict) else []
    mutation_summary = collect_top_mutation_blocks(report_rows)

    strict_by_key = {
        normalize_join_value(row.get("row_no")): row
        for row in strict_rows
        if normalize_join_value(row.get("row_no"))
    }
    strict_keys = set(strict_by_key)
    cloud_by_key, cloud_keys, cloud_duplicates, chosen_join_key = index_cloud_rows(
        cloud_rows,
        cloud_columns,
        args.join_key,
    )
    joined_keys = strict_keys.intersection(cloud_keys)
    join_quality = assess_join_quality(
        strict_rows=strict_rows,
        cloud_rows=cloud_rows,
        strict_keys=strict_keys,
        cloud_keys=cloud_keys,
        joined_keys=joined_keys,
        chosen_join_key=chosen_join_key,
        cloud_duplicates=cloud_duplicates,
    )
    if not joined_keys:
        print(
            "Warning: join produced 0 rows; continuing with strict_only_fallback. "
            f"strict row key=row_no, cloud join key={chosen_join_key}",
            file=sys.stderr,
        )

    all_advisor_rows: list[dict[str, Any]] = []
    for strict_row in strict_rows:
        key = normalize_join_value(strict_row.get("row_no"))
        report_row = report_by_row.get(key, {})
        all_advisor_rows.append(
            build_advisor_row(
                strict_row=strict_row,
                cloud_row=cloud_by_key.get(key),
                report_row=report_row,
                model_key=args.model_key,
                join_quality=join_quality,
            )
        )

    selected_rows = [
        row
        for row in all_advisor_rows
        if args.include_pass or row["strict_det"].get("det_pass") is not True
    ]
    selected_rows.sort(key=lambda row: row["advisor_priority"].get("priority_score", 0.0), reverse=True)
    if args.max_rows and args.max_rows > 0:
        selected_rows = selected_rows[: args.max_rows]

    metadata = {
        "strict_results_dir": str(strict_dir),
        "cloud_judge_csv": str(cloud_csv),
        "model_key": args.model_key,
        "join_key": chosen_join_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_strict_rows": len(strict_rows),
        "joined_rows": len(joined_keys),
        "strict_only_rows": len(strict_keys - cloud_keys),
        "cloud_only_rows": len(cloud_keys - strict_keys),
        "cloud_duplicate_join_keys": cloud_duplicates,
        "strict_duplicate_join_keys": join_quality.get("strict_duplicate_join_keys"),
        "join_quality": join_quality.get("join_quality"),
        "join_reason": join_quality.get("join_reason"),
        "cloud_feedback_usable_for_priority": join_quality.get("cloud_feedback_usable_for_priority"),
        "effective_feedback_mode": join_quality.get("effective_feedback_mode"),
        "join_quality_details": join_quality,
        "output_rows": len(selected_rows),
        "include_pass": bool(args.include_pass),
    }
    summary = summarize(strict_rows, all_advisor_rows, failure_summary, mutation_summary, args.model_key)
    payload = {"metadata": metadata, "summary": summary, "rows": selected_rows}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "advisor_rich_feedback.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_csv(out_dir / "hybrid_strict_cloud_report.csv", csv_rows_from_advisor(selected_rows), CSV_COLUMNS)
    write_markdown(out_dir / "hybrid_strict_cloud_report.md", metadata, summary, selected_rows, all_advisor_rows)

    print(f"Wrote {out_dir / 'advisor_rich_feedback.json'}")
    print(f"Wrote {out_dir / 'hybrid_strict_cloud_report.csv'}")
    print(f"Wrote {out_dir / 'hybrid_strict_cloud_report.md'}")
    print(
        "Join summary: "
        f"joined={metadata['joined_rows']}, "
        f"strict_only={metadata['strict_only_rows']}, "
        f"cloud_only={metadata['cloud_only_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
