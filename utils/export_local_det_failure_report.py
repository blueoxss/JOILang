#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


FAILURE_TAXONOMY: dict[str, dict[str, str]] = {
    "invalid_json": {
        "meaning": "생성 결과가 요구 JSON 형식 또는 필수 key 구조를 만족하지 못한 경우입니다.",
        "target_block_id": "03",
        "target_block_family": "Output_Schema",
        "suggested_mutation_type": "strengthen_json_only_rule",
        "micro_rule": "Return exactly one JSON object with required keys only; do not emit markdown, prose, comments, or code fences.",
    },
    "gt_mismatch": {
        "meaning": "JSON은 유효하지만 GT와 최종 동작이 완전히 동일하지 않은 경우입니다. service, receiver, temporal, numeric, enum, dataflow 차이 중 하나 이상이 누적되어 발생합니다.",
        "target_block_id": "06",
        "target_block_family": "DET_Helper",
        "suggested_mutation_type": "add_targeted_repair_hint",
        "micro_rule": "When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.",
    },
    "semantic": {
        "meaning": "GT와 생성 코드의 high-level intent 또는 control-flow 의미가 충분히 일치하지 않는 경우입니다. 조건, trigger, 반복, action 순서, state update 방식 차이가 주요 원인입니다.",
        "target_block_id": "06",
        "target_block_family": "Skeleton",
        "suggested_mutation_type": "strengthen_skeleton_rule",
        "micro_rule": "Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.",
    },
    "extraneous": {
        "meaning": "사용자 command나 GT에 없는 불필요한 action/read/wrapper가 추가된 경우입니다.",
        "target_block_id": "03",
        "target_block_family": "Minimality",
        "suggested_mutation_type": "strengthen_no_unrelated_action_rule",
        "micro_rule": "Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.",
    },
    "gt_receiver_coverage": {
        "meaning": "GT가 요구한 receiver tag, location, group, device target을 생성 코드가 충분히 보존하지 못한 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Owner_Device_Rule",
        "suggested_mutation_type": "strengthen_owner_device_rule",
        "micro_rule": "Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.",
    },
    "gt_service_coverage": {
        "meaning": "GT가 요구한 sensor/action service family를 생성 코드가 충분히 포함하지 못한 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Service_Mapping",
        "suggested_mutation_type": "add_schema_grounding_rule",
        "micro_rule": "Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.",
    },
    "service_match": {
        "meaning": "생성 코드의 service token이 schema 또는 canonical service와 충분히 일치하지 않는 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Service_Mapping",
        "suggested_mutation_type": "add_canonical_service_name_rule",
        "micro_rule": "Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.",
    },
    "unknown_service": {
        "meaning": "생성 코드가 schema에 존재하지 않는 service/member 이름을 사용한 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Service_Mapping",
        "suggested_mutation_type": "add_canonical_service_name_rule",
        "micro_rule": "Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.",
    },
    "numeric_grounding": {
        "meaning": "시간, 주기, 단위, threshold, argument literal이 GT 또는 service descriptor 기준과 다르게 변환된 경우입니다.",
        "target_block_id": "06",
        "target_block_family": "Temporal_Rule",
        "suggested_mutation_type": "add_micro_rule",
        "micro_rule": "Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.",
    },
    "precondition": {
        "meaning": "조건문, 상태 확인, if/wait until guard, trigger condition이 GT의 precondition과 다르게 표현된 경우입니다.",
        "target_block_id": "06",
        "target_block_family": "Skeleton",
        "suggested_mutation_type": "strengthen_precondition_rule",
        "micro_rule": "Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action.",
    },
    "arg_type": {
        "meaning": "function argument의 type, number/string/boolean/enum literal, separator 또는 positional argument 구조가 schema와 다르게 생성된 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Enum_Grounding",
        "suggested_mutation_type": "strengthen_enum_type_rule",
        "micro_rule": "For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema.",
    },
    "dataflow": {
        "meaning": "sensor read 결과가 downstream action/report에 올바르게 전달되지 않거나, GT의 variable binding/read-then-act 구조와 다른 경우입니다.",
        "target_block_id": "06",
        "target_block_family": "Dataflow",
        "suggested_mutation_type": "add_sensor_to_action_flow_rule",
        "micro_rule": "When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path.",
    },
    "enum_grounding": {
        "meaning": "enum argument 또는 enum-valued condition에서 허용 값과 다른 문자열을 사용한 경우입니다.",
        "target_block_id": "02",
        "target_block_family": "Enum_Grounding",
        "suggested_mutation_type": "strengthen_enum_type_rule",
        "micro_rule": "For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it.",
    },
}


DET_SCORE_KEYS = [
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
]

SERVICE_CALL_RE = re.compile(r"\((#[^)]+)\)\.([A-Za-z_][A-Za-z0-9_]*)\s*(\(|=|==|!=|>=|<=|>|<)?")
COMPARISON_RE = re.compile(
    r"(?P<lhs>\([^)]+\)\.[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?P<op>==|!=|>=|<=|>|<)\s*"
    r"(?P<rhs>\"[^\"]*\"|'[^']*'|true|false|-?\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*)"
)
ASSIGNMENT_RE = re.compile(r"(?P<lhs>\([^)]+\)\.[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<rhs>[^=][^\n;}]*)")
DELAY_RE = re.compile(r"delay\s*\(([^)]*)\)", re.IGNORECASE)
WAIT_UNTIL_RE = re.compile(r"wait\s+until\s*\((.*?)\)", re.IGNORECASE | re.DOTALL)
IF_RE = re.compile(r"\bif\s*\((.*?)\)\s*\{", re.IGNORECASE | re.DOTALL)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create local_det_failure_report.md/json/csv from row_comparison.csv and optional <model>_rerank.csv."
    )
    parser.add_argument("--results-dir", required=True, help="Benchmark result directory containing row_comparison.csv")
    parser.add_argument("--model-key", default="gpt41_mini")
    parser.add_argument("--row-comparison", default="")
    parser.add_argument("--rerank-csv", default="")
    parser.add_argument("--include-pass", action="store_true")
    parser.add_argument("--max-rows", type=int, default=0)
    parser.add_argument("--out-prefix", default="local_det_failure_report")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def safe_json_loads(value: Any, default: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except Exception:
        return default


def base_reason(reason: str) -> str:
    token = str(reason or "").strip()
    if token.startswith("unknown_service:"):
        return "unknown_service"
    return token.split(":", 1)[0] if ":" in token else token


def model_get(row: dict[str, str], model_key: str, key: str, default: str = "") -> str:
    return str(row.get(f"{model_key}__{key}", row.get(key, default)) or "")


def boolish(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def shorten(value: Any, limit: int = 3000) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + "\n... <truncated>"


def normalize_token(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def normalize_member(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def canonical_to_member(canonical: str) -> str:
    return normalize_member(canonical)


def load_rerank_by_row(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    return {str(row.get("row_no", "")).strip(): row for row in read_csv(path)}


def infer_reasons(row: dict[str, str], model_key: str, rerank_row: dict[str, str] | None = None) -> list[str]:
    reasons = safe_json_loads(model_get(row, model_key, "failure_reasons"), [])
    if not reasons and rerank_row:
        reasons = safe_json_loads(rerank_row.get("det_failure_reasons", ""), [])
    if not isinstance(reasons, list):
        return []
    return [str(reason) for reason in reasons if str(reason).strip()]


def collect_scores(row: dict[str, str], model_key: str) -> dict[str, str]:
    return {key: model_get(row, model_key, key) for key in DET_SCORE_KEYS}


def parse_services_from_code(code: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for match in SERVICE_CALL_RE.finditer(str(code or "")):
        receiver, member, usage = match.groups()
        out.append(
            {
                "receiver": receiver.strip(),
                "member": member.strip(),
                "member_norm": normalize_member(member),
                "usage": "call" if usage == "(" else ("assignment" if usage == "=" else "value_or_compare"),
                "text": match.group(0).strip(),
            }
        )
    return out


def parse_comparisons(code: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for match in COMPARISON_RE.finditer(str(code or "")):
        lhs = match.group("lhs").strip()
        op = match.group("op").strip()
        rhs = match.group("rhs").strip()
        out.append(
            {
                "lhs": lhs,
                "lhs_norm": normalize_token(lhs),
                "member_norm": normalize_member(lhs.split(".")[-1]),
                "op": op,
                "rhs": rhs,
                "rhs_norm": normalize_token(rhs),
                "text": match.group(0).strip(),
            }
        )
    return out


def parse_assignments(code: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for match in ASSIGNMENT_RE.finditer(str(code or "")):
        full = match.group(0)
        if any(op in full for op in ["==", "!=", ">=", "<="]):
            continue
        lhs = match.group("lhs").strip()
        rhs = match.group("rhs").strip()
        out.append({"lhs": lhs, "lhs_norm": normalize_token(lhs), "rhs": rhs, "text": full.strip()})
    return out


def parse_delays(code: str) -> list[str]:
    return [m.group(1).strip() for m in DELAY_RE.finditer(str(code or ""))]


def parse_wait_until(code: str) -> list[str]:
    return [re.sub(r"\s+", " ", m.group(1).strip()) for m in WAIT_UNTIL_RE.finditer(str(code or ""))]


def parse_if_conditions(code: str) -> list[str]:
    return [re.sub(r"\s+", " ", m.group(1).strip()) for m in IF_RE.finditer(str(code or ""))]


def parse_resolved_services(rerank_row: dict[str, str] | None) -> list[dict[str, Any]]:
    if not rerank_row:
        return []
    parsed = safe_json_loads(rerank_row.get("det_resolved_services", ""), [])
    return parsed if isinstance(parsed, list) else []


def service_label(service: dict[str, Any]) -> str:
    canonical = str(service.get("canonical_name") or "")
    if canonical:
        return canonical
    device = str(service.get("device") or "")
    name = str(service.get("service") or "")
    return f"{device}_{name}" if device or name else ""


def nearest_service_name(name: str, candidates: list[str]) -> str:
    if not candidates:
        return ""
    matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.45)
    return matches[0] if matches else ""


def build_concrete_diagnostics(
    row: dict[str, str],
    *,
    model_key: str,
    reasons: list[str],
    rerank_row: dict[str, str] | None,
) -> list[str]:
    diagnostics: list[str] = []
    gt_code = str(row.get("gt_code", "") or "")
    output_code = model_get(row, model_key, "output_code")
    gt_cron = str(row.get("gt_cron", "") or "")
    gt_period = str(row.get("gt_period", "") or "")
    out_cron = model_get(row, model_key, "output_cron")
    out_period = model_get(row, model_key, "output_period")

    gt_services = parse_services_from_code(gt_code)
    out_services = parse_services_from_code(output_code)
    resolved_services = parse_resolved_services(rerank_row)
    resolved_names = [service_label(s) for s in resolved_services if service_label(s)]
    resolved_members = {canonical_to_member(name) for name in resolved_names}
    gt_members = {s["member_norm"] for s in gt_services}
    out_members = {s["member_norm"] for s in out_services}

    # Schedule-only differences; emit only when actually different or when schedule is encoded in code redundantly.
    if gt_cron != out_cron:
        if gt_cron and not out_cron and out_period and out_period not in {"0", "-1"}:
            diagnostics.append(
                f"Schedule mismatch: GT는 cron `{gt_cron}`로 실행 시점을 표현하지만 output은 cron을 비우고 period `{out_period}`와 코드 내부 Clock guard로 표현했습니다. cron 기반 schedule은 JSON의 cron 필드에 두고 코드 내부 시간 guard는 제거해야 합니다."
            )
        else:
            diagnostics.append(f"Schedule mismatch: cron이 다릅니다. GT=`{gt_cron}` vs output=`{out_cron}`.")
    if str(gt_period) != str(out_period):
        diagnostics.append(f"Schedule mismatch: period가 다릅니다. GT=`{gt_period}` vs output=`{out_period}`.")
    if gt_cron and "clock_" in output_code.lower() and "clock_" not in gt_code.lower():
        diagnostics.append(
            "Extraneous temporal guard: GT는 cron 필드로 시간 범위를 이미 표현하므로 output code 안의 `#Clock` 조건은 중복/불필요한 guard일 가능성이 큽니다."
        )

    # Service coverage and unknown services.
    missing_members = sorted(gt_members - out_members - resolved_members)
    extra_members = sorted(out_members - gt_members - resolved_members)
    if missing_members:
        diagnostics.append(
            "Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: "
            + ", ".join(f"`{m}`" for m in missing_members)
            + "."
        )
    if extra_members:
        diagnostics.append(
            "Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: "
            + ", ".join(f"`{m}`" for m in extra_members)
            + "."
        )
    for reason in reasons:
        if reason.startswith("unknown_service:"):
            unknown = reason.split(":", 1)[1]
            nearest = nearest_service_name(unknown, [s["member"] for s in gt_services] + resolved_names)
            if nearest:
                diagnostics.append(
                    f"Unknown service detail: `{unknown}`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `{nearest}`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다."
                )
            else:
                diagnostics.append(f"Unknown service detail: `{unknown}`는 schema에 없는 member입니다. service_list에서 대응 canonical service를 다시 선택해야 합니다.")

    # Operator/value differences for comparable conditions.
    gt_comparisons = parse_comparisons(gt_code)
    out_comparisons = parse_comparisons(output_code)
    matched_out_indexes: set[int] = set()
    for gt_cmp in gt_comparisons:
        candidates = [
            (idx, out_cmp)
            for idx, out_cmp in enumerate(out_comparisons)
            if out_cmp["member_norm"] == gt_cmp["member_norm"] or out_cmp["lhs_norm"] == gt_cmp["lhs_norm"]
        ]
        if not candidates:
            diagnostics.append(f"Missing condition: GT condition `{gt_cmp['text']}`에 대응되는 output condition을 찾지 못했습니다.")
            continue
        idx, out_cmp = candidates[0]
        matched_out_indexes.add(idx)
        if gt_cmp["op"] != out_cmp["op"] or gt_cmp["rhs_norm"] != out_cmp["rhs_norm"]:
            parts: list[str] = []
            if gt_cmp["op"] != out_cmp["op"]:
                parts.append(f"operator GT `{gt_cmp['op']}` vs output `{out_cmp['op']}`")
            if gt_cmp["rhs_norm"] != out_cmp["rhs_norm"]:
                parts.append(f"value GT `{gt_cmp['rhs']}` vs output `{out_cmp['rhs']}`")
            diagnostics.append(
                f"Condition mismatch: `{gt_cmp['lhs']}` 비교식이 다릅니다 ({'; '.join(parts)}). GT condition `{gt_cmp['text']}` vs output condition `{out_cmp['text']}`."
            )
    for idx, out_cmp in enumerate(out_comparisons):
        if idx in matched_out_indexes:
            continue
        # Clock guards are already reported as schedule issues when cron exists.
        if gt_cron and "clock" in out_cmp["lhs_norm"]:
            continue
        diagnostics.append(f"Extra condition: output에 GT에서 요구하지 않은 조건 `{out_cmp['text']}`가 추가되었습니다.")

    # Delay and control-flow skeleton differences.
    gt_delays = parse_delays(gt_code)
    out_delays = parse_delays(output_code)
    if gt_delays != out_delays:
        diagnostics.append(f"Delay mismatch: GT delay={gt_delays} vs output delay={out_delays}.")
    gt_waits = parse_wait_until(gt_code)
    out_waits = parse_wait_until(output_code)
    if gt_waits != out_waits:
        if gt_waits and not out_waits:
            diagnostics.append(f"Missing wait-until trigger: GT는 `wait until ({gt_waits[0]})` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.")
        elif out_waits and not gt_waits:
            diagnostics.append(f"Unexpected wait-until trigger: output에 GT에 없는 `wait until ({out_waits[0]})`가 있습니다.")
        else:
            diagnostics.append(f"Wait-until condition mismatch: GT={gt_waits} vs output={out_waits}.")

    # Direct assignment to service values instead of action functions.
    assignments = parse_assignments(output_code)
    for assignment in assignments:
        if ")." in assignment["lhs"]:
            diagnostics.append(
                f"Service value assignment: output이 service/value `{assignment['lhs']}`에 직접 `{assignment['rhs']}`를 대입합니다. GT가 action function을 요구하는 경우에는 상태값 대입 대신 schema function call을 사용해야 합니다."
            )

    # If no concrete diff was captured, do not repeat generic pass details.
    if not diagnostics and reasons:
        diagnostics.append(
            "Concrete diff extractor did not isolate a token-level mismatch. Use GT/output code and DET component scores above to inspect the remaining semantic difference."
        )
    return diagnostics


def explain_reason(reason: str, row: dict[str, str], model_key: str, rerank_row: dict[str, str] | None) -> str:
    base = base_reason(reason)
    gt_cron = str(row.get("gt_cron", "") or "")
    gt_period = str(row.get("gt_period", "") or "")
    out_cron = model_get(row, model_key, "output_cron")
    out_period = model_get(row, model_key, "output_period")

    if base == "unknown_service":
        unknown = reason.split(":", 1)[1] if ":" in reason else ""
        return f"`{reason}`: 생성 코드가 현재 service schema에 없는 service/member `{unknown}`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다."
    if base == "numeric_grounding":
        parts: list[str] = []
        if gt_cron != out_cron:
            parts.append(f"cron 불일치: GT=`{gt_cron}` vs output=`{out_cron}`")
        if str(gt_period) != str(out_period):
            parts.append(f"period 불일치: GT=`{gt_period}` vs output=`{out_period}`")
        detail = "; ".join(parts) if parts else "시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다."
        return f"`numeric_grounding`: {detail} cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다."
    if base == "gt_receiver_coverage":
        score = model_get(row, model_key, "det_gt_receiver_coverage")
        return f"`gt_receiver_coverage`: receiver coverage score={score}. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다."
    if base == "gt_service_coverage":
        score = model_get(row, model_key, "det_gt_service_coverage")
        resolved = str((rerank_row or {}).get("det_resolved_services", "") or "")
        return f"`gt_service_coverage`: service coverage score={score}. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services={shorten(resolved, 500)}"
    if base == "semantic":
        sim = model_get(row, model_key, "det_gt_similarity")
        return f"`semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity={sim}. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다."
    if base == "precondition":
        return "`precondition`: if/wait until guard 또는 state precondition이 GT와 다릅니다. 명령의 조건절을 action으로 바꾸거나, mode value를 state check로 오해했는지 확인해야 합니다."
    if base == "dataflow":
        score = model_get(row, model_key, "det_dataflow_score")
        return f"`dataflow`: dataflow score={score}. sensor read 값이 downstream condition/action/report에 GT와 같은 방식으로 전달되지 않았을 가능성이 있습니다."
    if base == "extraneous":
        return "`extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다."
    if base == "arg_type":
        return "`arg_type`: function argument의 type, quoting, separator, positional order가 schema와 다를 수 있습니다. argument_type, argument_bounds, argument_format을 기준으로 literal을 재검증해야 합니다."
    if base == "enum_grounding":
        score = model_get(row, model_key, "det_enum_grounding")
        return f"`enum_grounding`: enum grounding score={score}. 허용 enum 값을 paraphrase하지 말고 descriptor의 allowed value를 그대로 복사해야 합니다."
    if base == "service_match":
        score = model_get(row, model_key, "det_service_match")
        return f"`service_match`: service match score={score}. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다."
    if base == "gt_mismatch":
        sim = model_get(row, model_key, "det_gt_similarity")
        return f"`gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity={sim}. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다."
    info = FAILURE_TAXONOMY.get(base, {})
    return f"`{reason}`: {info.get('meaning', '정의되지 않은 failure reason입니다. GT와 output code를 직접 비교해야 합니다.')}"


def recommend_for_reasons(reasons: list[str]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    recommendations: list[dict[str, str]] = []
    for reason in reasons:
        info = FAILURE_TAXONOMY.get(base_reason(reason))
        if not info:
            continue
        key = (info["target_block_id"], info["target_block_family"], info["micro_rule"])
        if key in seen:
            continue
        seen.add(key)
        recommendations.append(
            {
                "failure_reason": reason,
                "target_block_id": info["target_block_id"],
                "target_block_family": info["target_block_family"],
                "suggested_mutation_type": info["suggested_mutation_type"],
                "micro_rule": info["micro_rule"],
            }
        )
    return recommendations


def build_report_rows(
    rows: list[dict[str, str]],
    *,
    model_key: str,
    rerank_by_row: dict[str, dict[str, str]],
    include_pass: bool,
    max_rows: int,
) -> list[dict[str, Any]]:
    report_rows: list[dict[str, Any]] = []
    for row in rows:
        row_no = str(row.get("row_no", "")).strip()
        if boolish(model_get(row, model_key, "det_pass")) and not include_pass:
            continue
        rerank_row = rerank_by_row.get(row_no, {})
        reasons = infer_reasons(row, model_key, rerank_row)
        if not reasons and not include_pass:
            continue
        resolved_services = str(rerank_row.get("det_resolved_services", "") or "")
        concrete_diagnostics = build_concrete_diagnostics(row, model_key=model_key, reasons=reasons, rerank_row=rerank_row)
        report_rows.append(
            {
                "row_no": row_no,
                "category": row.get("category", row.get("row_category", "")),
                "command_eng": row.get("command_eng", ""),
                "command_kor": row.get("command_kor", ""),
                "failure_reasons": reasons,
                "det_scores": collect_scores(row, model_key),
                "gt": row.get("gt", ""),
                "gt_cron": row.get("gt_cron", ""),
                "gt_period": row.get("gt_period", ""),
                "gt_code": row.get("gt_code", ""),
                "output": model_get(row, model_key, "output"),
                "output_cron": model_get(row, model_key, "output_cron"),
                "output_period": model_get(row, model_key, "output_period"),
                "output_code": model_get(row, model_key, "output_code"),
                "resolved_services": safe_json_loads(resolved_services, resolved_services),
                "concrete_diagnostics": concrete_diagnostics,
                "automatic_explanations": [explain_reason(reason, row, model_key, rerank_row) for reason in reasons],
                "recommended_mutations": recommend_for_reasons(reasons),
            }
        )
        if max_rows and len(report_rows) >= max_rows:
            break
    return report_rows


def md_cell(value: Any) -> str:
    return str(value or "").replace("\n", "<br>").replace("|", "\\|")


def render_markdown(results_dir: Path, model_key: str, report_rows: list[dict[str, Any]], reason_counter: Counter[str]) -> str:
    lines: list[str] = []
    lines.append("# Local DET Failure Report")
    lines.append("")
    lines.append(f"- results_dir: `{results_dir}`")
    lines.append(f"- model_key: `{model_key}`")
    lines.append(f"- analyzed_failure_rows: `{len(report_rows)}`")
    lines.append("")
    lines.append("## 1. Failure taxonomy and prompt mutation mapping")
    lines.append("")
    lines.append("| failure_reason | 설명 | target block | suggested mutation | recommended micro-rule |")
    lines.append("|---|---|---|---|---|")
    for reason, info in FAILURE_TAXONOMY.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    md_cell(reason),
                    md_cell(info["meaning"]),
                    md_cell(f"{info['target_block_id']} / {info['target_block_family']}"),
                    md_cell(info["suggested_mutation_type"]),
                    md_cell(info["micro_rule"]),
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## 2. Failure reason summary")
    lines.append("")
    lines.append("| failure_reason | count |")
    lines.append("|---|---:|")
    for reason, count in reason_counter.most_common():
        lines.append(f"| `{md_cell(reason)}` | {count} |")
    lines.append("")
    lines.append("## 3. Row-level detailed analysis")
    lines.append("")
    for item in report_rows:
        score = item["det_scores"].get("det_score", "")
        reasons = ", ".join(f"`{reason}`" for reason in item["failure_reasons"])
        lines.append(f"### Row {item['row_no']} | category={item['category']} | det_score={score}")
        lines.append("")
        lines.append(f"- command_eng: {item['command_eng']}")
        if item.get("command_kor"):
            lines.append(f"- command_kor: {item['command_kor']}")
        lines.append(f"- failure_reasons: {reasons}")
        lines.append("")
        lines.append("#### Concrete mismatch diagnostics")
        if item.get("concrete_diagnostics"):
            for diagnostic in item["concrete_diagnostics"]:
                lines.append(f"- {diagnostic}")
        else:
            lines.append("- No concrete mismatch was extracted beyond the DET labels.")
        lines.append("")
        lines.append("#### DET component scores")
        lines.append("")
        lines.append("| metric | value |")
        lines.append("|---|---:|")
        for key, value in item["det_scores"].items():
            lines.append(f"| `{key}` | `{md_cell(value)}` |")
        lines.append("")
        lines.append("#### Schedule comparison")
        lines.append("")
        lines.append(f"- GT: cron=`{item['gt_cron']}`, period=`{item['gt_period']}`")
        lines.append(f"- Output: cron=`{item['output_cron']}`, period=`{item['output_period']}`")
        lines.append("")
        lines.append("#### GT code")
        lines.append("```")
        lines.append(shorten(item.get("gt_code", ""), 4000))
        lines.append("```")
        lines.append("")
        lines.append("#### Output code")
        lines.append("```")
        lines.append(shorten(item.get("output_code", ""), 4000))
        lines.append("```")
        lines.append("")
        lines.append("#### Resolved services")
        lines.append("```json")
        lines.append(json.dumps(item.get("resolved_services", ""), ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
        lines.append("#### Failure-label explanation")
        for explanation in item["automatic_explanations"]:
            lines.append(f"- {explanation}")
        lines.append("")
        lines.append("#### Recommended prompt mutation")
        if item["recommended_mutations"]:
            lines.append("| failure | target block | mutation | micro-rule |")
            lines.append("|---|---|---|---|")
            for rec in item["recommended_mutations"]:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            md_cell(rec["failure_reason"]),
                            md_cell(f"{rec['target_block_id']} / {rec['target_block_family']}"),
                            md_cell(rec["suggested_mutation_type"]),
                            md_cell(rec["micro_rule"]),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("- No mapped prompt mutation rule.")
        lines.append("")
    return "\n".join(lines) + "\n"


def flatten_for_csv(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in report_rows:
        scores = item["det_scores"]
        rows.append(
            {
                "row_no": item["row_no"],
                "category": item["category"],
                "command_eng": item["command_eng"],
                "command_kor": item["command_kor"],
                "failure_reasons": json.dumps(item["failure_reasons"], ensure_ascii=False),
                "concrete_diagnostics": "\n".join(item.get("concrete_diagnostics") or []),
                "det_score": scores.get("det_score", ""),
                "det_gt_similarity": scores.get("det_gt_similarity", ""),
                "det_gt_service_coverage": scores.get("det_gt_service_coverage", ""),
                "det_gt_receiver_coverage": scores.get("det_gt_receiver_coverage", ""),
                "det_dataflow_score": scores.get("det_dataflow_score", ""),
                "det_numeric_grounding": scores.get("det_numeric_grounding", ""),
                "det_enum_grounding": scores.get("det_enum_grounding", ""),
                "gt_cron": item["gt_cron"],
                "gt_period": item["gt_period"],
                "output_cron": item["output_cron"],
                "output_period": item["output_period"],
                "automatic_explanation": "\n".join(item["automatic_explanations"]),
                "recommended_mutations": json.dumps(item["recommended_mutations"], ensure_ascii=False),
                "gt_code": item["gt_code"],
                "output_code": item["output_code"],
                "resolved_services": json.dumps(item["resolved_services"], ensure_ascii=False),
            }
        )
    return rows


def export_for_result_dir(
    results_dir: Path,
    *,
    model_key: str = "gpt41_mini",
    row_comparison: Path | None = None,
    rerank_csv: Path | None = None,
    include_pass: bool = False,
    max_rows: int = 0,
    out_prefix: str = "local_det_failure_report",
) -> dict[str, str | int]:
    results_dir = results_dir.expanduser().resolve()
    row_path = row_comparison or results_dir / "row_comparison.csv"
    rerank_path = rerank_csv or results_dir / f"{model_key}_rerank.csv"
    if not row_path.exists():
        raise FileNotFoundError(f"row_comparison.csv not found: {row_path}")

    rows = read_csv(row_path)
    rerank_by_row = load_rerank_by_row(rerank_path)
    report_rows = build_report_rows(
        rows,
        model_key=model_key,
        rerank_by_row=rerank_by_row,
        include_pass=include_pass,
        max_rows=max_rows,
    )
    reason_counter: Counter[str] = Counter()
    for item in report_rows:
        reason_counter.update(item["failure_reasons"])

    md_path = results_dir / f"{out_prefix}.md"
    json_path = results_dir / f"{out_prefix}.json"
    csv_path = results_dir / f"{out_prefix}.csv"

    md_path.write_text(render_markdown(results_dir, model_key, report_rows, reason_counter), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "results_dir": str(results_dir),
                "model_key": model_key,
                "row_count": len(rows),
                "analyzed_failure_rows": len(report_rows),
                "failure_reason_counts": reason_counter.most_common(),
                "failure_taxonomy": FAILURE_TAXONOMY,
                "rows": report_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_csv(csv_path, flatten_for_csv(report_rows))
    return {
        "markdown": str(md_path),
        "json": str(json_path),
        "csv": str(csv_path),
        "failure_rows": len(report_rows),
    }


def main() -> int:
    args = parse_args()
    output = export_for_result_dir(
        Path(args.results_dir),
        model_key=args.model_key,
        row_comparison=Path(args.row_comparison).expanduser() if args.row_comparison else None,
        rerank_csv=Path(args.rerank_csv).expanduser() if args.rerank_csv else None,
        include_pass=bool(args.include_pass),
        max_rows=int(args.max_rows or 0),
        out_prefix=args.out_prefix,
    )
    print("Local DET failure report written:")
    print(f"- {output['markdown']}")
    print(f"- {output['json']}")
    print(f"- {output['csv']}")
    print(f"- failure rows: {output['failure_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
