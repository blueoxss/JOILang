#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from .schemas import BLOCK_TO_DEFAULT_FAMILY, FAMILY_TO_DEFAULT_BLOCK, utc_now
except ImportError:
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from schemas import BLOCK_TO_DEFAULT_FAMILY, FAMILY_TO_DEFAULT_BLOCK, utc_now


IMPORTANT_REASONS = {
    "semantic",
    "gt_mismatch",
    "numeric_grounding",
    "unknown_service",
    "gt_service_coverage",
    "gt_receiver_coverage",
    "arg_type",
    "enum_grounding",
    "dataflow",
    "extraneous",
    "service_match",
    "generation_empty_output",
    "generation_runtime_error",
    "generation_cuda_oom",
    "generation_timeout",
    "candidate_extraction_failure",
    "valid_json_empty_behavior_failure",
}

FAILURE_CLUSTER_MAP = {
    "unknown_service": ("Service_Mapping", "Canonical_Service_Name"),
    "service_match": ("Service_Mapping", "Canonical_Service_Name"),
    "gt_service_coverage": ("Service_Mapping",),
    "numeric_grounding": ("Temporal_Rule", "Cron_Period_Planning"),
    "time_period": ("Temporal_Rule", "Cron_Period_Planning"),
    "temporal_error": ("Temporal_Rule", "Cron_Period_Planning"),
    "semantic": ("Skeleton", "DET_Helper"),
    "gt_mismatch": ("Skeleton", "DET_Helper"),
    "gt_receiver_coverage": ("Receiver_Tag_Preservation", "Owner_Device_Rule"),
    "dataflow": ("Dataflow",),
    "arg_type": ("Enum_Grounding",),
    "enum_grounding": ("Enum_Grounding",),
    "extraneous": ("Minimality", "Output_Schema"),
    "generation_empty_output": ("Generation_Health",),
    "generation_runtime_error": ("Generation_Health",),
    "generation_cuda_oom": ("Prompt_Budget", "Runtime_Health"),
    "generation_timeout": ("Runtime_Health", "Prompt_Budget"),
    "candidate_extraction_failure": ("Parser_Extraction",),
    "invalid_json.non_json_text": ("Output_Schema",),
    "invalid_json.markdown_fence": ("Output_Schema",),
    "invalid_json.malformed_json": ("Output_Schema",),
    "invalid_json.truncated_json": ("Output_Schema",),
    "schema_missing_required_keys": ("Output_Schema",),
    "schema_invalid_field_type": ("Output_Schema",),
    "valid_json_empty_behavior_match": ("No_Mutation",),
    "valid_json_empty_behavior_failure": ("Intent_Fulfillment", "Skeleton"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a compressed prompt mutation advisor prompt.")
    parser.add_argument("--advisor-rich-feedback", required=True)
    parser.add_argument("--prompt-version", default="version0_13")
    parser.add_argument("--model-key", default="gpt41_mini")
    parser.add_argument("--out", required=True)
    parser.add_argument("--top-rows", type=int, default=20)
    parser.add_argument("--representatives-per-cluster", type=int, default=3)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "pass"}:
        return True
    if text in {"0", "false", "no", "fail"}:
        return False
    return None


def base_reason(reason: Any) -> str:
    token = str(reason or "").strip()
    if token.startswith("unknown_service:"):
        return "unknown_service"
    if ":" in token:
        token = token.split(":", 1)[0]
    return token


def get_priority(row: dict[str, Any]) -> float:
    priority = row.get("advisor_priority") or {}
    return float(priority.get("priority_score") or 0.0)


def get_priority_level(row: dict[str, Any]) -> str:
    return str((row.get("advisor_priority") or {}).get("priority_level") or "").lower()


def row_failure_reasons(row: dict[str, Any]) -> list[str]:
    root = row.get("root_cause_summary") if isinstance(row.get("root_cause_summary"), dict) else {}
    root_cause = str(root.get("root_cause") or "").strip()
    if root_cause and root_cause != "valid_json_nonempty":
        return [root_cause]
    strict = row.get("strict_det") or {}
    reasons = strict.get("failure_reasons") or []
    return [str(item) for item in reasons if str(item).strip()]


def row_clusters(row: dict[str, Any]) -> list[str]:
    families: list[str] = []
    root = row.get("root_cause_summary") if isinstance(row.get("root_cause_summary"), dict) else {}
    root_family = str(root.get("target_block_family") or "").strip()
    if root_family and root_family != "DET_Helper":
        families.append(root_family)
    for reason in row_failure_reasons(row):
        for family in FAILURE_CLUSTER_MAP.get(base_reason(reason), ("DET_Helper",)):
            if family == "Output_Schema" and family in set(row.get("suppressed_mutations") or []):
                continue
            if family not in families:
                families.append(family)
    return families or ["DET_Helper"]


def row_is_primary_candidate(row: dict[str, Any]) -> bool:
    strict = row.get("strict_det") or {}
    diagnostics = row.get("local_det_diagnostics") or {}
    det_pass = as_bool(strict.get("det_pass"))
    priority_level = get_priority_level(row)
    reasons = {base_reason(item) for item in row_failure_reasons(row)}
    concrete = diagnostics.get("concrete_diagnostics") or []
    mutations = diagnostics.get("recommended_mutations") or []
    return (
        det_pass is False
        and priority_level in {"high", "medium"}
        and (bool(reasons.intersection(IMPORTANT_REASONS)) or bool((row.get("root_cause_summary") or {}).get("target_block_family")))
        and bool(concrete)
        and bool(mutations)
    )


def row_auxiliary_boost(row: dict[str, Any]) -> float:
    boost = 0.0
    evidence_quality = row.get("evidence_quality") if isinstance(row.get("evidence_quality"), dict) else {}
    if evidence_quality.get("effective_feedback_mode") == "strict_only_fallback":
        return boost
    lang = row.get("lang_judge") or {}
    gpt = row.get("gpt_judge") or {}
    if lang.get("valid_score") is False and gpt.get("valid_score") is False:
        return boost
    for key in ("time_period", "device_service", "semantic_intent"):
        val = as_float(lang.get(key))
        if val is not None and val < 0.8:
            boost += 0.03
    overall_gpt = as_float(gpt.get("overall_gpt"))
    if overall_gpt is not None and overall_gpt < 0.8:
        boost += 0.03
    return boost


def selection_score(row: dict[str, Any]) -> float:
    return get_priority(row) + row_auxiliary_boost(row)


def short_text(value: Any, limit: int = 900) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit] + " ... <truncated>"


def compact_reasoning(value: Any, limit: int = 900) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, val in value.items():
            out[str(key)] = short_text(val, limit=300)
        return out
    if isinstance(value, list):
        return [short_text(item, limit=250) for item in value[:6]]
    return short_text(value, limit=limit)


def compact_mutation(mutation: Any) -> dict[str, Any] | str:
    if not isinstance(mutation, dict):
        return short_text(mutation, 500)
    return {
        "failure_reason": mutation.get("failure_reason", ""),
        "target_block_id": mutation.get("target_block_id", ""),
        "target_block_family": mutation.get("target_block_family", ""),
        "suggested_mutation_type": mutation.get("suggested_mutation_type", ""),
        "micro_rule": short_text(mutation.get("micro_rule", ""), 600),
    }


def compact_row(row: dict[str, Any], *, include_code: bool) -> dict[str, Any]:
    strict = row.get("strict_det") or {}
    diag = row.get("local_det_diagnostics") or {}
    lang = row.get("lang_judge") or {}
    gpt = row.get("gpt_judge") or {}
    code = row.get("code_comparison") or {}
    compact = {
        "row_no": row.get("row_no", ""),
        "category": row.get("category", ""),
        "priority": row.get("advisor_priority", {}),
        "command_eng": short_text(row.get("command_eng", ""), 700),
        "command_kor": short_text(row.get("command_kor", ""), 700),
        "failure_clusters": row_clusters(row),
        "generation_state": row.get("generation_state", {}),
        "generation_health": row.get("generation_health", {}),
        "evidence_quality": row.get("evidence_quality", {}),
        "root_cause_summary": row.get("root_cause_summary", {}),
        "suppressed_mutations": row.get("suppressed_mutations", []),
        "strict_det": {
            "det_score": strict.get("det_score"),
            "det_pass": strict.get("det_pass"),
            "gt_exact": strict.get("gt_exact"),
            "failure_reasons": strict.get("failure_reasons") or [],
            "component_scores": strict.get("component_scores") or {},
        },
        "local_det_diagnostics": {
            "concrete_diagnostics": [short_text(item, 700) for item in (diag.get("concrete_diagnostics") or [])[:8]],
            "automatic_explanations": [short_text(item, 500) for item in (diag.get("automatic_explanations") or [])[:6]],
            "recommended_mutations": [
                compact_mutation(item)
                for item in (diag.get("recommended_mutations") or [])[:8]
            ],
        },
        "cloud_auxiliary": {
            "lang": {
                "available": lang.get("available", False),
                "valid_score": lang.get("valid_score", False),
                "status": lang.get("status", ""),
                "skip_reason": lang.get("skip_reason", ""),
                "overall_lang": lang.get("overall_lang"),
                "semantic_intent": lang.get("semantic_intent"),
                "conditions": lang.get("conditions"),
                "time_period": lang.get("time_period"),
                "device_service": lang.get("device_service"),
                "reasoning_summary": compact_reasoning(lang.get("reasoning")),
            },
            "gpt": {
                "available": gpt.get("available", False),
                "valid_score": gpt.get("valid_score", False),
                "status": gpt.get("status", ""),
                "skip_reason": gpt.get("skip_reason", ""),
                "overall_gpt": gpt.get("overall_gpt"),
                "reasoning_summary": compact_reasoning(gpt.get("reasoning")),
                "reconverted": gpt.get("reconverted") or {},
            },
        },
    }
    if include_code:
        compact["code_comparison"] = {
            "gt_code": short_text(code.get("gt_code", ""), 2200),
            "output_code": short_text(code.get("output_code", ""), 2200),
            "gt_cron": code.get("gt_cron", ""),
            "gt_period": code.get("gt_period", ""),
            "output_cron": code.get("output_cron", ""),
            "output_period": code.get("output_period", ""),
        }
    return compact


def select_rows(rows: list[dict[str, Any]], top_rows: int, representatives_per_cluster: int) -> list[dict[str, Any]]:
    primary = [row for row in rows if row_is_primary_candidate(row)]
    fallback = rows if rows else []
    ranked = sorted(primary or fallback, key=selection_score, reverse=True)
    selected: dict[str, dict[str, Any]] = {}
    for row in ranked[: max(0, top_rows)]:
        selected[str(row.get("row_no", len(selected)))] = row

    by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ranked:
        for family in row_clusters(row):
            by_cluster[family].append(row)
    for family_rows in by_cluster.values():
        for row in sorted(family_rows, key=selection_score, reverse=True)[: representatives_per_cluster]:
            selected[str(row.get("row_no", len(selected)))] = row
    return sorted(selected.values(), key=selection_score, reverse=True)


def build_failure_clusters(rows: list[dict[str, Any]], representatives_per_cluster: int) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}
    for row in rows:
        for family in row_clusters(row):
            entry = clusters.setdefault(
                family,
                {
                    "cluster_id": family,
                    "target_block_family": family,
                    "target_block_id": FAMILY_TO_DEFAULT_BLOCK.get(family, "06"),
                    "rows": [],
                    "failure_reason_counts": Counter(),
                    "mean_priority": 0.0,
                    "strict_det_primary_signal": [],
                    "cloud_auxiliary_signal": [],
                },
            )
            entry["rows"].append(row)
            for reason in row_failure_reasons(row):
                entry["failure_reason_counts"][base_reason(reason)] += 1
    out = []
    for entry in clusters.values():
        rows_sorted = sorted(entry["rows"], key=selection_score, reverse=True)
        priorities = [get_priority(row) for row in rows_sorted]
        entry["mean_priority"] = round(sum(priorities) / len(priorities), 6) if priorities else 0.0
        entry["representative_rows"] = [
            compact_row(row, include_code=False)
            for row in rows_sorted[:representatives_per_cluster]
        ]
        entry["row_nos"] = [str(row.get("row_no", "")) for row in rows_sorted]
        entry["failure_reason_counts"] = dict(entry["failure_reason_counts"].most_common())
        entry["strict_det_primary_signal"] = [
            {
                "row_no": row.get("row_no", ""),
                "failure_reasons": row_failure_reasons(row),
                "diagnostics": (row.get("local_det_diagnostics") or {}).get("concrete_diagnostics", [])[:3],
            }
            for row in rows_sorted[:representatives_per_cluster]
        ]
        entry["cloud_auxiliary_signal"] = [
            {
                "row_no": row.get("row_no", ""),
                "lang_scores": {
                    key: (row.get("lang_judge") or {}).get(key)
                    for key in ("overall_lang", "semantic_intent", "time_period", "device_service", "conditions")
                },
                "overall_gpt": (row.get("gpt_judge") or {}).get("overall_gpt"),
            }
            for row in rows_sorted[:representatives_per_cluster]
        ]
        del entry["rows"]
        out.append(entry)
    return sorted(out, key=lambda item: item["mean_priority"], reverse=True)


def load_prompt_structure() -> tuple[dict[str, Any], dict[str, str]]:
    fallback = {
        "core_blocks": ["01", "02"],
        "optional_blocks": ["03", "05", "06"],
        "block_order": ["01", "02", "03", "05", "06"],
        "note": "fallback prompt structure; ga_block_model import failed",
    }
    fallback_families = dict(BLOCK_TO_DEFAULT_FAMILY)
    repo_root = Path(__file__).resolve().parents[2]
    v15_root = repo_root / "gpt_mg" / "version0_15_update20260413"
    if str(v15_root) not in sys.path:
        sys.path.insert(0, str(v15_root))
    try:
        from utils import ga_block_model
        return (
            {
                "core_blocks": list(getattr(ga_block_model, "CORE_BLOCKS", ("01", "02"))),
                "optional_blocks": list(getattr(ga_block_model, "OPTIONAL_BLOCKS", ("03", "05", "06"))),
                "block_order": list(getattr(ga_block_model, "BLOCK_ORDER", ("01", "02", "03", "05", "06"))),
                "compatibility_note": (
                    "Existing renderer keeps 01/02 hard core; dynamic core decisions are represented "
                    "as candidate genome blocks and block_params.micro_rules."
                ),
            },
            dict(getattr(ga_block_model, "BLOCK_FAMILIES", fallback_families)),
        )
    except Exception:
        return fallback, fallback_families


def build_summary(feedback: dict[str, Any], selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    reason_counts: Counter[str] = Counter()
    cluster_counts: Counter[str] = Counter()
    det_scores = []
    for row in selected_rows:
        strict = row.get("strict_det") or {}
        score = as_float(strict.get("det_score"))
        if score is not None:
            det_scores.append(score)
        for reason in row_failure_reasons(row):
            reason_counts[base_reason(reason)] += 1
        for cluster in row_clusters(row):
            cluster_counts[cluster] += 1
    return {
        "source_summary": feedback.get("summary", {}),
        "selected_row_count": len(selected_rows),
        "selected_mean_det_score": round(sum(det_scores) / len(det_scores), 6) if det_scores else None,
        "selected_failure_reason_counts": dict(reason_counts.most_common()),
        "selected_cluster_counts": dict(cluster_counts.most_common()),
        "selection_policy": {
            "primary": "strict DET failed rows with high/medium advisor priority, concrete diagnostics, and recommended mutations",
            "auxiliary_boost": "low lang sub-scores or low GPT score increase selection priority only as diagnostic context",
        },
    }


def system_prompt() -> str:
    return (
        "You are a feedback advisor for JOILang prompt optimization. "
        "You output valid JSON only. You do not generate JOILang code and you do not rewrite whole prompt blocks."
    )


def user_prompt() -> str:
    return """
You are a feedback advisor for JOILang prompt optimization.

Your task is not to generate JOILang code.
Your task is not to rewrite the entire prompt.
Your task is to propose minimal, targeted prompt mutations that improve future JOILang generation.

You are given:
1. strict DET failure reasons,
2. concrete mismatch diagnostics,
3. Lang judge multi-criteria scores,
4. GPT semantic judge reasoning,
5. current prompt block/core/optional structure,
6. recommended mutation hints from the local DET report.

Rules:
- Treat strict DET failure reasons as the primary signal.
- Use cloud judge reasoning only as auxiliary explanation.
- Do not use cloud judge scores as official benchmark scores.
- If evidence_quality.effective_feedback_mode is strict_only_fallback, do not use cloud scores to prioritize patches.
- Respect generation_state and root_cause_summary before semantic mismatch diagnostics.
- For generation_empty_output, generation_cuda_oom, generation_timeout, generation_runtime_error, or candidate_extraction_failure, route advice to Generation_Health, Prompt_Budget, Runtime_Health, or Parser_Extraction; do not propose Output_Schema or service/semantic rules unless raw JSON text exists.
- For valid_json_empty_behavior_match, propose no prompt mutation.
- For invalid_json.* or schema_missing_required_keys, Output_Schema patches are allowed only when output_schema_suppressed is false.
- Never treat skipped/error/missing cloud judge scores as zero-quality semantic evidence.
- Do not rewrite the entire prompt.
- Prefer small micro-rules that target recurring failure patterns.
- Preserve existing high-performing behavior.
- If evidence is weak or only one row supports a change, mark the patch as low confidence.
- Include evidence rows for each patch.
- Include expected effect, risk, token cost, regression risk, and validation scope.
- Include dynamic core/optional decision.
- Include 5 to 6 concise review cycles.
- Include predicted user questions and answers in the iteration audit.
- Output valid JSON only.

Return schema must include:
- advisor_meta
- compressed_feedback_summary
- dynamic_criteria
- core_optional_decision
- prompt_patches
- do_not_change
- iteration_audit
- validation_plan
- final_decision

The prompt_patches section must be actionable by apply_prompt_patches.py.

Valid operations:
append_micro_rule, strengthen_existing_rule, replace_sentence, delete_conflicting_rule,
promote_gene_to_dynamic_core, demote_gene_to_optional, suppress_gene,
activate_optional_block, deactivate_optional_block, diversify_micro_rules.

Valid target_block_id: 01, 02, 03, 05, 06.

Dynamic core/optional decision criteria:
- hard_core: JSON contract, schema authority, no hallucinated services, canonical service grounding, required output keys.
- dynamic_core: repeated cluster, strict DET and cloud judge agree, specific diagnostics, high expected strict DET improvement, low regression risk.
- optional: moderate evidence, non-trivial token cost, category-specific use, diversity branch.
- suppress_or_do_not_change: weak evidence, high risk, redundant rule, likely harm to passing rows.

Review cycles:
Perform 5 to 6 concise cycles. Each cycle should tighten criteria, evaluate patches, identify weak patches,
revise patch list, predict user questions or objections, answer them, and assign a 0-100 score.
If score reaches 90 early, tighten criteria and continue.

Expected user questions to include:
1. Why is this patch applied to advisor/mutation rather than final generation prompt?
2. If strict DET and cloud judge disagree, which one is trusted?
3. Could this micro-rule damage v13's existing high performance?
4. Does this increase prompt tokens too much?
5. Is this overfitting one row?
6. Should this be dynamic core or optional?
7. Which block or genome field will be modified?
8. Which evaluation should be rerun after applying this patch?
9. How does this patch increase population diversity?
10. How can this be rolled back if strict DET gets worse?

Return JSON only. Do not include markdown fences.
""".strip()


def build_prompt_payload(args: argparse.Namespace) -> dict[str, Any]:
    feedback_path = Path(args.advisor_rich_feedback)
    feedback = read_json(feedback_path)
    rows = feedback.get("rows", []) if isinstance(feedback, dict) else []
    if not isinstance(rows, list):
        rows = []
    selected_rows = select_rows(rows, args.top_rows, args.representatives_per_cluster)
    selected_row_ids = {str(row.get("row_no", "")) for row in selected_rows[:5]}
    compressed_rows = [
        compact_row(row, include_code=str(row.get("row_no", "")) in selected_row_ids)
        for row in selected_rows
    ]
    clusters = build_failure_clusters(selected_rows, args.representatives_per_cluster)
    prompt_structure, block_families = load_prompt_structure()
    evidence_packet = {
        "metadata": {
            "created_at": utc_now(),
            "advisor_rich_feedback": str(feedback_path),
            "prompt_version": args.prompt_version,
            "model_key": args.model_key,
            "top_rows": args.top_rows,
            "representatives_per_cluster": args.representatives_per_cluster,
            "source_metadata": feedback.get("metadata", {}),
        },
        "baseline_summary": feedback.get("summary", {}),
        "compressed_feedback_summary": build_summary(feedback, selected_rows),
        "current_prompt_structure": prompt_structure,
        "current_block_families": block_families,
        "selected_high_priority_rows": compressed_rows,
        "failure_clusters": clusters,
    }
    return {
        "system_prompt": system_prompt(),
        "user_prompt": user_prompt() + "\n\nEVIDENCE_PACKET_JSON:\n" + json.dumps(evidence_packet, ensure_ascii=False, indent=2),
        "evidence_packet": evidence_packet,
        "metadata": {
            "created_at": utc_now(),
            "builder": "utils/prompt_advisor/build_advisor_prompt.py",
            "advisor_rich_feedback": str(feedback_path),
            "selected_rows": len(compressed_rows),
            "failure_clusters": len(clusters),
        },
    }


def main() -> int:
    args = parse_args()
    payload = build_prompt_payload(args)
    write_json(Path(args.out), payload)
    print(f"Wrote {args.out}")
    print(
        "Advisor prompt summary: "
        f"rows={payload['metadata']['selected_rows']}, "
        f"clusters={payload['metadata']['failure_clusters']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
