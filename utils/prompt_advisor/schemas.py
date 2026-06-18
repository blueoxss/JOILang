#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any


VALID_OPERATIONS = {
    "append_micro_rule",
    "strengthen_existing_rule",
    "replace_sentence",
    "delete_conflicting_rule",
    "promote_gene_to_dynamic_core",
    "demote_gene_to_optional",
    "suppress_gene",
    "activate_optional_block",
    "deactivate_optional_block",
    "diversify_micro_rules",
}

VALID_TARGET_BLOCK_IDS = {"01", "02", "03", "05", "06"}

VALID_BLOCK_FAMILIES = {
    "Core_System",
    "Service_Mapping",
    "Output_Schema",
    "Repair_Clause",
    "DET_Helper",
    "Temporal_Rule",
    "Skeleton",
    "Owner_Device_Rule",
    "Dataflow",
    "Enum_Grounding",
    "Minimality",
    "Receiver_Tag_Preservation",
    "Canonical_Service_Name",
    "Cron_Period_Planning",
    "Event_Trigger_Skeleton",
}

FAMILY_TO_DEFAULT_BLOCK = {
    "Core_System": "01",
    "Service_Mapping": "02",
    "Canonical_Service_Name": "02",
    "Owner_Device_Rule": "02",
    "Receiver_Tag_Preservation": "02",
    "Enum_Grounding": "02",
    "Output_Schema": "03",
    "Minimality": "03",
    "Repair_Clause": "05",
    "DET_Helper": "06",
    "Temporal_Rule": "06",
    "Cron_Period_Planning": "06",
    "Skeleton": "06",
    "Event_Trigger_Skeleton": "06",
    "Dataflow": "06",
}

BLOCK_TO_DEFAULT_FAMILY = {
    "01": "Core_System",
    "02": "Service_Mapping",
    "03": "Output_Schema",
    "05": "Repair_Clause",
    "06": "DET_Helper",
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}
TOKEN_COST_ORDER = {"low": 0, "medium": 1, "high": 2}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def deep_copy_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def slugify(value: Any, default: str = "item") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or default


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def as_str_list(value: Any) -> list[str]:
    return [str(item) for item in as_list(value) if str(item).strip()]


def clamp_priority(value: Any, default: int = 50) -> int:
    try:
        score = int(round(float(value)))
    except Exception:
        score = default
    return max(0, min(100, score))


def normalize_level(value: Any, default: str = "medium") -> str:
    text = str(value or "").strip().lower()
    return text if text in {"low", "medium", "high"} else default


def normalize_operation(value: Any) -> str:
    op = str(value or "").strip()
    if op in VALID_OPERATIONS:
        return op
    return "append_micro_rule"


def normalize_block_family(value: Any, fallback_block_id: str = "06") -> str:
    family = str(value or "").strip()
    if family in VALID_BLOCK_FAMILIES:
        return family
    return BLOCK_TO_DEFAULT_FAMILY.get(fallback_block_id, "DET_Helper")


def normalize_block_id(value: Any, fallback_family: str = "DET_Helper") -> str:
    block_id = str(value or "").strip().zfill(2)
    if block_id in VALID_TARGET_BLOCK_IDS:
        return block_id
    return FAMILY_TO_DEFAULT_BLOCK.get(fallback_family, "06")


def ensure_target_gene_id(value: Any, block_id: str, family: str) -> str:
    text = str(value or "").strip()
    if text:
        return text
    return f"{block_id}:{family}"


def default_advisor_meta(source: str = "deterministic") -> dict[str, Any]:
    return {
        "created_at": utc_now(),
        "source": source,
        "schema_version": "prompt_advisor.v1",
    }


def prompt_patch_schema() -> dict[str, Any]:
    return {
        "patch_id": "",
        "target_block_family": "",
        "target_block_id": "",
        "target_gene_id": "",
        "operation": "",
        "priority": 0,
        "patch_text": "",
        "evidence_rows": [],
        "evidence_failure_reasons": [],
        "strict_det_basis": {},
        "cloud_judge_basis": {},
        "expected_effect": "",
        "risk": "medium",
        "token_cost": "medium",
        "regression_risk": "medium",
        "validation_scope": "",
        "success_criteria": [],
        "core_optional_decision": "",
        "dynamic_core": False,
        "optional": False,
        "suppress_or_do_not_change": False,
    }


def normalize_patch(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    patch = copy.deepcopy(prompt_patch_schema())
    if isinstance(raw, dict):
        patch.update(raw)
    family = normalize_block_family(patch.get("target_block_family"), str(patch.get("target_block_id") or "06"))
    block_id = normalize_block_id(patch.get("target_block_id"), family)
    operation = normalize_operation(patch.get("operation"))
    patch["target_block_family"] = family
    patch["target_block_id"] = block_id
    patch["target_gene_id"] = ensure_target_gene_id(patch.get("target_gene_id"), block_id, family)
    patch["operation"] = operation
    patch["priority"] = clamp_priority(patch.get("priority"), default=60)
    patch["patch_text"] = str(patch.get("patch_text") or "").strip()
    patch["evidence_rows"] = as_str_list(patch.get("evidence_rows"))
    patch["evidence_failure_reasons"] = as_str_list(patch.get("evidence_failure_reasons"))
    patch["strict_det_basis"] = patch.get("strict_det_basis") if isinstance(patch.get("strict_det_basis"), dict) else {}
    patch["cloud_judge_basis"] = patch.get("cloud_judge_basis") if isinstance(patch.get("cloud_judge_basis"), dict) else {}
    patch["expected_effect"] = str(patch.get("expected_effect") or "").strip()
    patch["risk"] = normalize_level(patch.get("risk"))
    patch["token_cost"] = normalize_level(patch.get("token_cost"))
    patch["regression_risk"] = normalize_level(patch.get("regression_risk"))
    patch["validation_scope"] = str(patch.get("validation_scope") or "").strip()
    patch["success_criteria"] = as_str_list(patch.get("success_criteria"))
    decision = str(patch.get("core_optional_decision") or "").strip().lower()
    if decision not in {"hard_core", "dynamic_core", "optional", "suppress_or_do_not_change"}:
        if patch.get("suppress_or_do_not_change"):
            decision = "suppress_or_do_not_change"
        elif patch.get("dynamic_core"):
            decision = "dynamic_core"
        elif patch.get("optional"):
            decision = "optional"
        else:
            decision = "dynamic_core" if patch["priority"] >= 75 and patch["regression_risk"] != "high" else "optional"
    patch["core_optional_decision"] = decision
    patch["dynamic_core"] = decision == "dynamic_core"
    patch["optional"] = decision == "optional"
    patch["suppress_or_do_not_change"] = decision == "suppress_or_do_not_change"
    if not patch["patch_id"]:
        patch["patch_id"] = f"patch_{index:03d}_{slugify(family)}"
    if not patch["patch_text"]:
        patch["patch_text"] = (
            f"When handling {family}, add a minimal self-check before final JSON output."
        )
    if not patch["expected_effect"]:
        patch["expected_effect"] = f"Reduce recurring {family} strict DET failures."
    if not patch["validation_scope"]:
        patch["validation_scope"] = "Rerun strict DET on evidence rows and related category rows."
    if not patch["success_criteria"]:
        patch["success_criteria"] = ["strict DET score improves without new invalid JSON failures"]
    return patch


def prompt_patches_output_schema() -> dict[str, Any]:
    return {
        "advisor_meta": default_advisor_meta(),
        "compressed_feedback_summary": {},
        "dynamic_criteria": {},
        "core_optional_decision": {
            "hard_core": [],
            "dynamic_core": [],
            "optional": [],
            "suppress_or_do_not_change": [],
        },
        "prompt_patches": [],
        "do_not_change": [],
        "iteration_audit": [],
        "validation_plan": {},
        "final_decision": {},
    }


def normalize_patches_output(raw: dict[str, Any], source: str = "advisor") -> dict[str, Any]:
    out = prompt_patches_output_schema()
    if isinstance(raw, dict):
        out.update(raw)
    meta = out.get("advisor_meta") if isinstance(out.get("advisor_meta"), dict) else {}
    meta.setdefault("created_at", utc_now())
    meta.setdefault("source", source)
    meta.setdefault("schema_version", "prompt_advisor.v1")
    out["advisor_meta"] = meta
    decision = out.get("core_optional_decision")
    if not isinstance(decision, dict):
        decision = {}
    out["core_optional_decision"] = {
        "hard_core": as_str_list(decision.get("hard_core")),
        "dynamic_core": as_str_list(decision.get("dynamic_core")),
        "optional": as_str_list(decision.get("optional")),
        "suppress_or_do_not_change": as_str_list(decision.get("suppress_or_do_not_change")),
    }
    out["prompt_patches"] = [
        normalize_patch(item, index=i)
        for i, item in enumerate(as_list(out.get("prompt_patches")))
        if isinstance(item, dict)
    ]
    out["do_not_change"] = as_str_list(out.get("do_not_change"))
    out["iteration_audit"] = as_list(out.get("iteration_audit"))
    out["compressed_feedback_summary"] = (
        out.get("compressed_feedback_summary")
        if isinstance(out.get("compressed_feedback_summary"), dict)
        else {}
    )
    out["dynamic_criteria"] = out.get("dynamic_criteria") if isinstance(out.get("dynamic_criteria"), dict) else {}
    out["validation_plan"] = out.get("validation_plan") if isinstance(out.get("validation_plan"), dict) else {}
    out["final_decision"] = out.get("final_decision") if isinstance(out.get("final_decision"), dict) else {}
    return out


def candidate_genome_record_schema() -> dict[str, Any]:
    return {
        "candidate_id": "",
        "source_patch_ids": [],
        "mutation_intent": "",
        "diversity_family": "",
        "genome": {},
        "expected_effect": "",
        "risk": "medium",
        "token_cost": "medium",
        "validation_scope": "",
    }


def make_iteration_audit(score_start: int = 90) -> list[dict[str, Any]]:
    questions = [
        "Why is this patch applied to advisor/mutation rather than final generation prompt?",
        "If strict DET and cloud judge disagree, which one is trusted?",
        "Could this micro-rule damage v13's existing high performance?",
        "Does this increase prompt tokens too much?",
        "Is this overfitting one row?",
        "Should this be dynamic core or optional?",
        "Which block or genome field will be modified?",
        "Which evaluation should be rerun after applying this patch?",
        "How does this patch increase population diversity?",
        "How can this be rolled back if strict DET gets worse?",
    ]
    answers = [
        "The advisor evidence is converted into micro-rule patches so final generation prompts stay controlled.",
        "Strict DET is primary; cloud reasoning is auxiliary explanation only.",
        "Each patch carries regression risk and validation scope to protect passing behavior.",
        "Token cost is labeled and high-cost patches are isolated from conservative candidates.",
        "Single-row evidence is low confidence and should become optional or diversity-only.",
        "Repeated low-risk clusters can be dynamic core; narrower evidence stays optional.",
        "Only compatible genome fields such as blocks and block_params.micro_rules are changed.",
        "Rerun strict DET first, then inspect cloud diagnostics for semantic explanations.",
        "Different candidates combine different clusters, risks, and optional blocks.",
        "Remove the patch id from the candidate genome or rerun from the unchanged base genome.",
    ]
    cycles = []
    for i in range(6):
        cycles.append(
            {
                "cycle": i + 1,
                "criteria_update": (
                    "Tighten evidence threshold, token discipline, regression protection, and validation scope."
                    if i else
                    "Start from strict DET failures, concrete diagnostics, and minimal prompt mutation scope."
                ),
                "patch_review_summary": "Reject broad rewrites; keep only targeted micro-rules with evidence rows.",
                "weak_patch_filter": "Mark one-row or cloud-only support as low confidence.",
                "predicted_user_q": questions[i] if i < len(questions) else questions[-1],
                "answer": answers[i] if i < len(answers) else answers[-1],
                "score": min(100, score_start + i * 2),
            }
        )
    return cycles


def make_minimal_patches_output(
    patches: list[dict[str, Any]],
    *,
    source: str,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_patches_output(
        {
            "advisor_meta": default_advisor_meta(source=source),
            "compressed_feedback_summary": summary or {},
            "dynamic_criteria": {
                "primary_signal": "strict DET",
                "auxiliary_signal": "cloud semantic judge reasoning",
                "micro_rule_policy": "minimal targeted mutations only",
            },
            "core_optional_decision": {
                "hard_core": ["Core_System", "Service_Mapping", "Output_Schema"],
                "dynamic_core": [],
                "optional": ["DET_Helper", "Temporal_Rule", "Skeleton"],
                "suppress_or_do_not_change": [],
            },
            "prompt_patches": patches,
            "do_not_change": [
                "Do not attach advisor_rich_feedback.json to final generation prompts.",
                "Do not rewrite entire prompt blocks.",
                "Do not treat cloud judge scores as official benchmark metrics.",
            ],
            "iteration_audit": make_iteration_audit(),
            "validation_plan": {
                "primary": "Run strict DET on evidence rows, then full 280-row benchmark if improved.",
                "secondary": "Run cloud semantic judges for explanation drift only.",
            },
            "final_decision": {
                "status": "ready_for_population_generation",
                "reason": "Patches are scoped to genome micro-rules and optional block activation.",
            },
        },
        source=source,
    )
    families = sorted({patch["target_block_family"] for patch in normalized["prompt_patches"]})
    normalized["core_optional_decision"]["dynamic_core"] = [
        family for family in families if family in {"Service_Mapping", "Temporal_Rule", "Skeleton", "DET_Helper"}
    ]
    normalized["core_optional_decision"]["optional"] = [
        family for family in families if family not in set(normalized["core_optional_decision"]["dynamic_core"])
    ]
    return normalized
