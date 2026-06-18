#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    from .schemas import (
        FAMILY_TO_DEFAULT_BLOCK,
        make_minimal_patches_output,
        normalize_patches_output,
        utc_now,
    )
except ImportError:
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from schemas import (
        FAMILY_TO_DEFAULT_BLOCK,
        make_minimal_patches_output,
        normalize_patches_output,
        utc_now,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the prompt feedback advisor.")
    parser.add_argument("--advisor-prompt", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_openai_api_key() -> str | None:
    return (
        os.environ.get("OPENAI_API_KEY")
        or os.environ.get("JOI_EVAL_OPENAI_API_KEY")
        or os.environ.get("JOI_V15_OPENAI_API_KEY")
    )


def require_openai_api_key() -> str:
    key = get_openai_api_key()
    if not key:
        raise RuntimeError(
            "Feedback Advisor requires OPENAI_API_KEY, JOI_EVAL_OPENAI_API_KEY, "
            "or JOI_V15_OPENAI_API_KEY in the environment."
        )
    return key


def extract_json_object(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        data = json.loads(raw[start : end + 1])
        if isinstance(data, dict):
            return data
    raise ValueError("Advisor response did not contain a valid JSON object.")


def compact_text(value: Any, limit: int = 700) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + " ... <truncated>"


def best_micro_rule_from_cluster(cluster: dict[str, Any]) -> str:
    for row in cluster.get("representative_rows") or []:
        diag = row.get("local_det_diagnostics") or {}
        for mutation in diag.get("recommended_mutations") or []:
            if isinstance(mutation, dict) and mutation.get("micro_rule"):
                return compact_text(mutation.get("micro_rule"), 500)
    family = cluster.get("target_block_family", "DET_Helper")
    return f"Before final JSON, run a targeted self-check for recurring {family} failures."


def patch_operation_for_family(family: str) -> str:
    if family in {"Service_Mapping", "Canonical_Service_Name", "Enum_Grounding", "Owner_Device_Rule", "Receiver_Tag_Preservation"}:
        return "strengthen_existing_rule"
    if family in {"Output_Schema", "Minimality"}:
        return "append_micro_rule"
    if family in {"Temporal_Rule", "Skeleton", "DET_Helper", "Dataflow", "Cron_Period_Planning", "Event_Trigger_Skeleton"}:
        return "append_micro_rule"
    return "append_micro_rule"


def risk_for_cluster(cluster: dict[str, Any]) -> str:
    count = len(cluster.get("row_nos") or [])
    family = cluster.get("target_block_family", "")
    if count <= 1:
        return "medium"
    if family in {"Minimality", "Output_Schema"}:
        return "medium"
    return "low"


def token_cost_for_rule(rule: str) -> str:
    words = len(str(rule or "").split())
    if words <= 18:
        return "low"
    if words <= 38:
        return "medium"
    return "high"


def deterministic_patches_from_prompt(prompt_payload: dict[str, Any]) -> dict[str, Any]:
    evidence = prompt_payload.get("evidence_packet") or {}
    clusters = evidence.get("failure_clusters") or []
    summary = evidence.get("compressed_feedback_summary") or {}
    patches: list[dict[str, Any]] = []
    for idx, cluster in enumerate(clusters[:12]):
        if not isinstance(cluster, dict):
            continue
        family = str(cluster.get("target_block_family") or cluster.get("cluster_id") or "DET_Helper")
        block_id = str(cluster.get("target_block_id") or FAMILY_TO_DEFAULT_BLOCK.get(family, "06"))
        row_nos = [str(item) for item in cluster.get("row_nos", []) if str(item).strip()]
        reason_counts = cluster.get("failure_reason_counts") or {}
        rule = best_micro_rule_from_cluster(cluster)
        risk = risk_for_cluster(cluster)
        priority = 90 - min(idx * 4, 35)
        if len(row_nos) <= 1:
            priority = min(priority, 68)
        decision = "dynamic_core" if priority >= 75 and risk != "high" else "optional"
        patches.append(
            {
                "patch_id": f"patch_{idx:03d}_{family.lower()}",
                "target_block_family": family,
                "target_block_id": block_id,
                "target_gene_id": f"{block_id}:{family}",
                "operation": patch_operation_for_family(family),
                "priority": priority,
                "patch_text": rule,
                "evidence_rows": row_nos[:8],
                "evidence_failure_reasons": list(reason_counts.keys()),
                "strict_det_basis": {
                    "cluster": cluster.get("cluster_id", family),
                    "failure_reason_counts": reason_counts,
                    "representative_diagnostics": cluster.get("strict_det_primary_signal", [])[:3],
                },
                "cloud_judge_basis": {
                    "auxiliary_only": True,
                    "representative_scores": cluster.get("cloud_auxiliary_signal", [])[:3],
                },
                "expected_effect": f"Improve future rows affected by {family} without changing whole prompt blocks.",
                "risk": risk,
                "token_cost": token_cost_for_rule(rule),
                "regression_risk": risk,
                "validation_scope": "Rerun strict DET on evidence rows, then related category rows.",
                "success_criteria": [
                    "strict DET pass rate improves on evidence rows",
                    "no increase in invalid_json or unknown_service failures",
                ],
                "core_optional_decision": decision,
                "dynamic_core": decision == "dynamic_core",
                "optional": decision == "optional",
                "suppress_or_do_not_change": False,
            }
        )
    if not patches:
        patches.append(
            {
                "patch_id": "patch_000_det_helper",
                "target_block_family": "DET_Helper",
                "target_block_id": "06",
                "target_gene_id": "06:DET_Helper",
                "operation": "append_micro_rule",
                "priority": 60,
                "patch_text": "Before final JSON, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding.",
                "evidence_rows": [],
                "evidence_failure_reasons": ["gt_mismatch"],
                "strict_det_basis": {"fallback": "no clusters available"},
                "cloud_judge_basis": {"auxiliary_only": True},
                "expected_effect": "Create a conservative DET-oriented helper candidate.",
                "risk": "medium",
                "token_cost": "medium",
                "regression_risk": "medium",
                "validation_scope": "Rerun strict DET smoke rows before full benchmark.",
                "success_criteria": ["strict DET does not regress"],
                "core_optional_decision": "optional",
                "optional": True,
            }
        )
    return make_minimal_patches_output(patches, source="dry_run_deterministic", summary=summary)


def call_openai(prompt_payload: dict[str, Any], model: str, temperature: float) -> tuple[str, dict[str, Any]]:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise RuntimeError(f"openai package is required for API mode: {exc}") from exc

    key = require_openai_api_key()
    base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    client = OpenAI(api_key=key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": prompt_payload.get("system_prompt", "")},
            {"role": "user", "content": prompt_payload.get("user_prompt", "")},
        ],
        response_format={"type": "json_object"},
    )
    text = response.choices[0].message.content or ""
    usage = getattr(response, "usage", None)
    usage_payload = {}
    if usage is not None:
        usage_payload = {
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return text, usage_payload


def main() -> int:
    args = parse_args()
    prompt_path = Path(args.advisor_prompt)
    out_path = Path(args.out)
    prompt_payload = read_json(prompt_path)
    if args.dry_run:
        patches = deterministic_patches_from_prompt(prompt_payload)
        patches["advisor_meta"]["dry_run"] = True
        patches["advisor_meta"]["advisor_prompt"] = str(prompt_path)
        write_json(out_path, patches)
        print(f"Dry-run: wrote deterministic prompt patch preview to {out_path}")
        print(
            "Dry-run summary: "
            f"patches={len(patches.get('prompt_patches', []))}, "
            f"clusters={len((prompt_payload.get('evidence_packet') or {}).get('failure_clusters') or [])}"
        )
        return 0

    raw_text = ""
    try:
        raw_text, usage = call_openai(prompt_payload, args.model, args.temperature)
        parsed = extract_json_object(raw_text)
        patches = normalize_patches_output(parsed, source="feedback_advisor_api")
        patches["advisor_meta"]["advisor_prompt"] = str(prompt_path)
        patches["advisor_meta"]["model"] = args.model
        patches["advisor_meta"]["temperature"] = args.temperature
        patches["advisor_meta"]["created_at"] = utc_now()
        if usage:
            patches["advisor_meta"]["usage"] = usage
        write_json(out_path, patches)
        print(f"Wrote {out_path}")
        print(f"Prompt patches: {len(patches.get('prompt_patches', []))}")
        return 0
    except Exception as exc:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path = out_path.with_name("raw_response.txt")
        if raw_text:
            raw_path.write_text(raw_text, encoding="utf-8")
            print(f"Saved raw response to {raw_path}", file=sys.stderr)
        print(f"Feedback Advisor failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

