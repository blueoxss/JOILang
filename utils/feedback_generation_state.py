#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from collections.abc import Mapping
from typing import Any


GENERATION_FAILURE_CLASSES = {
    "generation_empty_output",
    "generation_runtime_error",
    "generation_cuda_oom",
    "generation_timeout",
    "candidate_extraction_failure",
}

INVALID_JSON_CLASSES = {
    "invalid_json.non_json_text",
    "invalid_json.markdown_fence",
    "invalid_json.malformed_json",
    "invalid_json.truncated_json",
}

SCHEMA_FAILURE_CLASSES = {
    "schema_missing_required_keys",
    "schema_invalid_field_type",
}

OUTPUT_SCHEMA_MUTATION_CLASSES = INVALID_JSON_CLASSES | SCHEMA_FAILURE_CLASSES

SEMANTIC_DIFF_ALLOWED_CLASSES = {
    "valid_json_empty_behavior_failure",
    "valid_json_nonempty_gt_mismatch",
    "valid_json_nonempty",
}

REQUIRED_KEYS = {"name", "cron", "period"}


def model_get(row: Mapping[str, Any], model_key: str, key: str, default: Any = "") -> Any:
    return row.get(f"{model_key}__{key}", row.get(key, default))


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        try:
            return value != value
        except Exception:
            return False
    return str(value).strip().lower() in {"", "none", "null", "nan"}


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    text = str(value or "").strip()
    if not text:
        return []
    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(text)
            if isinstance(parsed, list):
                return parsed
            if parsed not in (None, ""):
                return [parsed]
        except Exception:
            continue
    return [text]


def strip_markdown_fence(raw: str) -> tuple[str, bool]:
    text = str(raw or "").strip()
    if not text.startswith("```"):
        return text, False
    stripped = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    stripped = re.sub(r"```$", "", stripped).strip()
    return stripped, True


def parse_json_status(raw: Any) -> dict[str, Any]:
    if _blank(raw):
        return {
            "raw_candidate_present": False,
            "json_valid": False,
            "json_error_type": "empty_raw_candidate",
            "parsed_json": None,
            "had_markdown_fence": False,
            "normalized_raw": "",
        }
    text = str(raw).strip()
    stripped, had_fence = strip_markdown_fence(text)
    try:
        parsed = json.loads(stripped)
        return {
            "raw_candidate_present": True,
            "json_valid": True,
            "json_error_type": "markdown_fence" if had_fence else "",
            "parsed_json": parsed,
            "had_markdown_fence": had_fence,
            "normalized_raw": stripped,
        }
    except Exception as exc:
        head = stripped[:1]
        if had_fence:
            error_type = "markdown_fence"
        elif head not in {"{", "["}:
            error_type = "non_json_text"
        elif stripped.count("{") > stripped.count("}") or stripped.count("[") > stripped.count("]"):
            error_type = "truncated_json"
        else:
            error_type = "malformed_json"
        return {
            "raw_candidate_present": True,
            "json_valid": False,
            "json_error_type": error_type,
            "json_error": str(exc),
            "parsed_json": None,
            "had_markdown_fence": had_fence,
            "normalized_raw": stripped,
        }


def _candidate_from_value(value: Any) -> str:
    if _blank(value):
        return ""
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        for item in value:
            candidate = _candidate_from_value(item)
            if candidate:
                return candidate
        return ""
    return str(value).strip()


def get_raw_candidate(row: Mapping[str, Any], model_key: str = "") -> str:
    keys = [
        "raw_candidate",
        "raw_model_output",
        "generated_candidate_json",
        "candidate_json",
        "candidate",
        "candidates",
        "model_response",
        "response",
        "output",
    ]
    for key in keys:
        values = []
        if model_key:
            values.append(row.get(f"{model_key}__{key}"))
        values.append(row.get(key))
        for value in values:
            if key == "candidates":
                for item in _coerce_list(value):
                    candidate = _candidate_from_value(item)
                    if candidate:
                        return candidate
            else:
                candidate = _candidate_from_value(value)
                if candidate:
                    return candidate
    output_code = model_get(row, model_key, "output_code")
    if isinstance(output_code, str) and output_code.strip().upper().startswith("INVALID JSON:"):
        return output_code.split(":", 1)[1].strip()
    output_fields = {
        "name": model_get(row, model_key, "output_name"),
        "cron": model_get(row, model_key, "output_cron"),
        "period": model_get(row, model_key, "output_period"),
        "code": output_code,
    }
    period = str(output_fields.get("period") or "").strip()
    has_nonempty_behavior = (
        not _blank(output_fields.get("name"))
        or not _blank(output_fields.get("cron"))
        or not _blank(output_fields.get("code"))
        or (not _blank(period) and period not in {"0", "-1"})
    )
    if has_nonempty_behavior:
        return json.dumps(output_fields, ensure_ascii=False)
    return ""


def _script_value(obj: Mapping[str, Any]) -> Any:
    return obj.get("code", obj.get("script", ""))


def behavior_fields_from_json(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, Mapping):
        return {"name": "", "cron": "", "period": "", "code": ""}
    return {
        "name": obj.get("name", ""),
        "cron": obj.get("cron", ""),
        "period": obj.get("period", ""),
        "code": _script_value(obj),
    }


def is_behavior_empty_fields(fields: Mapping[str, Any]) -> bool:
    code_empty = _blank(fields.get("code"))
    cron_empty = _blank(fields.get("cron"))
    period_value = fields.get("period")
    period_empty = _blank(period_value) or str(period_value).strip() in {"0", "-1"}
    return bool(code_empty and cron_empty and period_empty)


def is_parsed_behavior_empty(row: Mapping[str, Any], model_key: str, parsed_json: Any | None = None) -> bool:
    if isinstance(parsed_json, Mapping):
        return is_behavior_empty_fields(behavior_fields_from_json(parsed_json))
    fields = {
        "code": model_get(row, model_key, "output_code"),
        "cron": model_get(row, model_key, "output_cron"),
        "period": model_get(row, model_key, "output_period"),
    }
    return is_behavior_empty_fields(fields)


def _gt_candidates(row: Mapping[str, Any]) -> list[Any]:
    candidates: list[Any] = []
    for key in ("gt", "ground_truth_json", "ground_truth_json_list"):
        value = row.get(key)
        if key == "ground_truth_json_list":
            candidates.extend(_coerce_list(value))
        elif not _blank(value):
            candidates.append(value)
    numbered = sorted(
        (key for key in row.keys() if re.fullmatch(r"gt\d+", str(key).lower())),
        key=lambda key: int(re.search(r"\d+", str(key)).group(0)),
    )
    candidates.extend(row.get(key) for key in numbered if not _blank(row.get(key)))
    if not candidates:
        candidates.append(
            {
                "name": row.get("gt_name", ""),
                "cron": row.get("gt_cron", ""),
                "period": row.get("gt_period", ""),
                "code": row.get("gt_code", ""),
            }
        )
    return candidates


def _parse_gt_candidate(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value
    if _blank(value):
        return None
    text = str(value).strip()
    text, _had_fence = strip_markdown_fence(text)
    for loader in (json.loads, ast.literal_eval):
        try:
            parsed = loader(text)
            if isinstance(parsed, list):
                return parsed[0] if parsed else None
            return parsed
        except Exception:
            continue
    return None


def is_gt_behavior_empty(row: Mapping[str, Any]) -> bool:
    candidates = _gt_candidates(row)
    parsed_any = False
    for candidate in candidates:
        parsed = _parse_gt_candidate(candidate)
        if isinstance(parsed, Mapping):
            parsed_any = True
            if not is_behavior_empty_fields(behavior_fields_from_json(parsed)):
                return False
    if parsed_any:
        return True
    return is_behavior_empty_fields(
        {
            "code": row.get("gt_code", ""),
            "cron": row.get("gt_cron", ""),
            "period": row.get("gt_period", ""),
        }
    )


def _generation_error_type(row: Mapping[str, Any], model_key: str) -> str:
    for key in ("generation_error_type", "error_type", "worker_error_type", "exception_type"):
        value = model_get(row, model_key, key)
        if not _blank(value):
            return str(value).strip()
    for key in ("generation_error", "error", "worker_error", "exception"):
        value = model_get(row, model_key, key)
        if not _blank(value):
            return str(value).strip()
    return ""


def is_generation_runtime_failure(row: Mapping[str, Any], model_key: str) -> bool:
    return classify_runtime_failure(row, model_key)[0] != ""


def classify_runtime_failure(row: Mapping[str, Any], model_key: str) -> tuple[str, str]:
    error_text = _generation_error_type(row, model_key)
    blob = " ".join(
        str(model_get(row, model_key, key, ""))
        for key in ("generation_error_type", "error_type", "generation_error", "error", "status")
    ).lower()
    if "candidate_extraction_failure" in blob or "extraction" in blob:
        return "candidate_extraction_failure", error_text or "candidate_extraction_failure"
    if _truthy(model_get(row, model_key, "generation_oom_flag")) or "oom" in blob or "out of memory" in blob or "cuda" in blob:
        return "generation_cuda_oom", error_text or "cuda_oom"
    if _truthy(model_get(row, model_key, "timeout")) or "timeout" in blob or "timed out" in blob:
        return "generation_timeout", error_text or "timeout"
    if error_text:
        return "generation_runtime_error", error_text
    return "", ""


def _schema_status(parsed: Any) -> tuple[str, list[str]]:
    if not isinstance(parsed, Mapping):
        return "schema_invalid_field_type", []
    keys = set(parsed.keys())
    missing = sorted(REQUIRED_KEYS - keys)
    if "code" not in keys and "script" not in keys:
        missing.append("code_or_script")
    if missing:
        return "schema_missing_required_keys", missing
    if not isinstance(parsed.get("name", ""), str):
        return "schema_invalid_field_type", []
    if not isinstance(parsed.get("cron", ""), str):
        return "schema_invalid_field_type", []
    code = _script_value(parsed)
    if code is not None and not isinstance(code, str):
        return "schema_invalid_field_type", []
    return "", []


def _advisor_route_for_class(state_class: str) -> tuple[str, str, bool]:
    mapping = {
        "generation_cuda_oom": ("Prompt_Budget", "reduce_prompt_size_or_runtime_config", True),
        "generation_timeout": ("Runtime_Health", "reduce_prompt_size_or_retry_policy", True),
        "generation_runtime_error": ("Generation_Health", "inspect_worker_runtime_error", True),
        "generation_empty_output": ("Generation_Health", "inspect_raw_output_worker_logs_prompt_length", True),
        "candidate_extraction_failure": ("Parser_Extraction", "inspect_raw_output_and_extraction_regex", True),
        "invalid_json.markdown_fence": ("Output_Schema", "json_only_rule", False),
        "invalid_json.non_json_text": ("Output_Schema", "json_only_rule", False),
        "invalid_json.malformed_json": ("Output_Schema", "strict_parseable_json_rule", False),
        "invalid_json.truncated_json": ("Output_Schema", "strict_parseable_json_rule", False),
        "schema_missing_required_keys": ("Output_Schema", "required_keys_rule", False),
        "schema_invalid_field_type": ("Output_Schema", "required_field_type_rule", False),
        "valid_json_empty_behavior_match": ("No_Mutation", "no_mutation", True),
        "valid_json_empty_behavior_failure": ("Skeleton", "require_non_empty_behavior_for_action_command", True),
        "valid_json_nonempty_gt_mismatch": ("DET_Helper", "semantic_gt_comparison", False),
        "valid_json_nonempty": ("DET_Helper", "semantic_gt_comparison", False),
    }
    return mapping.get(state_class, ("DET_Helper", "semantic_gt_comparison", False))


def classify_generation_state(row: Mapping[str, Any], model_key: str = "") -> dict[str, Any]:
    runtime_class, runtime_error_type = classify_runtime_failure(row, model_key)
    raw = get_raw_candidate(row, model_key)
    parse = parse_json_status(raw)
    gt_empty = is_gt_behavior_empty(row)
    json_valid = bool(parse["json_valid"])

    if runtime_class:
        state_class = runtime_class
        parsed_empty = True
        json_valid = False
    elif not parse["raw_candidate_present"]:
        if gt_empty and (_truthy(model_get(row, model_key, "det_pass")) or str(model_get(row, model_key, "det_score")).strip() in {"1", "1.0", "100", "100.0"}):
            state_class = "valid_json_empty_behavior_match"
            parsed_empty = True
            json_valid = True
        else:
            state_class = "generation_empty_output"
            parsed_empty = True
            json_valid = False
    elif parse["had_markdown_fence"]:
        state_class = "invalid_json.markdown_fence"
        parsed_empty = True
        json_valid = bool(parse["json_valid"])
    elif not parse["json_valid"]:
        error_type = str(parse.get("json_error_type") or "malformed_json")
        state_class = f"invalid_json.{error_type}"
        parsed_empty = True
        json_valid = False
    else:
        schema_class, missing_keys = _schema_status(parse["parsed_json"])
        if schema_class:
            state_class = schema_class
            parsed_empty = True
            json_valid = True
        else:
            missing_keys = []
            parsed_empty = is_parsed_behavior_empty(row, model_key, parse["parsed_json"])
            if parsed_empty and gt_empty:
                state_class = "valid_json_empty_behavior_match"
            elif parsed_empty:
                state_class = "valid_json_empty_behavior_failure"
            else:
                state_class = "valid_json_nonempty"

    target_family, mutation_policy, suppress_output_schema = _advisor_route_for_class(state_class)
    allow_output_schema = (
        state_class in OUTPUT_SCHEMA_MUTATION_CLASSES
        and parse["raw_candidate_present"]
        and not runtime_class
        and not suppress_output_schema
    )
    allow_semantic_diff = state_class in SEMANTIC_DIFF_ALLOWED_CLASSES
    skip_cloud = state_class in (
        GENERATION_FAILURE_CLASSES
        | INVALID_JSON_CLASSES
        | SCHEMA_FAILURE_CLASSES
        | {"valid_json_empty_behavior_match"}
    )
    return {
        "class": state_class,
        "raw_candidate_present": bool(parse["raw_candidate_present"]),
        "json_valid": bool(json_valid),
        "json_error_type": str(parse.get("json_error_type") or ""),
        "schema_missing_keys": missing_keys if "missing_keys" in locals() else [],
        "parsed_fields_empty": bool(parsed_empty),
        "gt_empty": bool(gt_empty),
        "skip_cloud_judge": bool(skip_cloud),
        "allow_output_schema_mutation": bool(allow_output_schema),
        "allow_semantic_diff": bool(allow_semantic_diff),
        "output_schema_suppressed": bool(suppress_output_schema or not allow_output_schema),
        "not_evaluated_reason": state_class if state_class not in {"valid_json_nonempty"} else "",
        "raw_candidate_excerpt": str(raw or "")[:500],
        "runtime_error_type": runtime_error_type,
        "advisor_target_family": target_family,
        "advisor_mutation_policy": mutation_policy,
        "suppressed_mutations": ["Output_Schema"] if not allow_output_schema else [],
    }


def component_score_policy(row: Mapping[str, Any], model_key: str = "", state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    state = dict(state or classify_generation_state(row, model_key))

    def _score(key: str) -> float | None:
        value = model_get(row, model_key, key)
        try:
            if value is None or str(value).strip() == "":
                return None
            return float(value)
        except Exception:
            return None

    state_class = str(state.get("class") or "")
    if state_class in GENERATION_FAILURE_CLASSES or state_class in INVALID_JSON_CLASSES or state_class in SCHEMA_FAILURE_CLASSES:
        return {
            "gt_similarity": 0.0,
            "gt_service_coverage": None,
            "gt_service_precision": None,
            "gt_receiver_coverage": None,
            "dataflow_score": None,
            "numeric_grounding": None,
            "enum_grounding": None,
            "not_evaluated_reason": state_class,
        }
    if state_class == "valid_json_empty_behavior_match":
        return {
            "gt_similarity": 1.0,
            "gt_service_coverage": None,
            "gt_service_precision": None,
            "gt_receiver_coverage": None,
            "dataflow_score": None,
            "numeric_grounding": None,
            "enum_grounding": None,
            "not_evaluated_reason": "empty_behavior_expected",
        }
    if state_class == "valid_json_empty_behavior_failure":
        return {
            "gt_similarity": 0.0,
            "gt_service_coverage": 0.0,
            "gt_service_precision": None,
            "gt_receiver_coverage": 0.0,
            "dataflow_score": None,
            "numeric_grounding": None,
            "enum_grounding": None,
            "not_evaluated_reason": "valid_json_empty_behavior_failure",
        }
    return {
        "gt_similarity": _score("det_gt_similarity"),
        "gt_service_coverage": _score("det_gt_service_coverage"),
        "gt_service_precision": _score("det_gt_service_precision"),
        "gt_receiver_coverage": _score("det_gt_receiver_coverage"),
        "dataflow_score": _score("det_dataflow_score"),
        "numeric_grounding": _score("det_numeric_grounding"),
        "enum_grounding": _score("det_enum_grounding"),
        "not_evaluated_reason": "",
    }


def generation_failure_diagnostic(state: Mapping[str, Any]) -> str:
    state_class = str(state.get("class") or "generation_empty_output")
    if state_class == "valid_json_empty_behavior_match":
        return "No-op match: valid empty JSON was expected because the GT behavior is empty."
    if state_class in INVALID_JSON_CLASSES or state_class in SCHEMA_FAILURE_CLASSES:
        return f"Parse/schema failure: `{state_class}`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics."
    return (
        "Generation failure: no valid raw candidate was produced. Semantic GT-vs-output diagnostics are skipped. "
        "Inspect generation_error_type, generation_oom_flag, timeout, worker logs, prompt length, raw model output, "
        "and model config before applying prompt-level semantic mutations."
    )


def root_cause_summary_for_state(state: Mapping[str, Any]) -> dict[str, Any]:
    state_class = str(state.get("class") or "")
    target_family, mutation_policy, _suppress = _advisor_route_for_class(state_class)
    return {
        "root_cause": state_class,
        "target_block_family": target_family,
        "mutation_policy": mutation_policy,
        "output_schema_suppressed": not bool(state.get("allow_output_schema_mutation")),
    }
