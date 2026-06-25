#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


REQUIRED_ATOM_FIELDS = {
    "local_id",
    "name",
    "semantic_family",
    "semantic_role",
    "behavior_tags",
    "source_span",
    "content_hash",
    "path",
    "required",
    "mutation_allowed",
    "crossover_enabled",
    "order_group",
    "render_order",
    "lineage",
    "failure_targets",
}

DYNAMIC_OPERATIONS = {
    "activate_atom",
    "deactivate_atom",
    "rewrite_atom",
    "replace_atom_variant",
    "split_atom",
    "merge_atoms",
    "relabel_atom",
    "reorder_atoms",
    "promote_required",
    "demote_optional",
    "attach_micro_rule",
    "remove_micro_rule",
    "create_new_atom",
    "retire_atom",
}

FAILURE_TARGET_MAP: dict[str, dict[str, Any]] = {
    "invalid_json": {
        "semantic_family": "Output_Schema",
        "semantic_role": "json_output_contract",
        "behavior_tags": ["json_only", "required_keys", "valid_json"],
    },
    "missing_generated_code": {
        "semantic_family": "Output_Schema",
        "semantic_role": "non_empty_code_contract",
        "behavior_tags": ["non_empty_code", "parseable_json"],
    },
    "unknown_service": {
        "semantic_family": "Service_Grounding",
        "semantic_role": "canonical_service_name",
        "behavior_tags": ["schema_authority", "canonical_service_name", "no_invented_service"],
    },
    "gt_service_coverage": {
        "semantic_family": "Service_Grounding",
        "semantic_role": "service_coverage",
        "behavior_tags": ["function_service", "value_service", "schema_match"],
    },
    "gt_receiver_coverage": {
        "semantic_family": "Receiver_Grounding",
        "semantic_role": "receiver_tag_preservation",
        "behavior_tags": ["receiver_tag", "connected_device_scope"],
    },
    "cron_mismatch": {
        "semantic_family": "Temporal",
        "semantic_role": "cron_schedule",
        "behavior_tags": ["cron", "schedule"],
    },
    "period_mismatch": {
        "semantic_family": "Temporal",
        "semantic_role": "period_policy",
        "behavior_tags": ["period", "monitoring"],
    },
    "numeric_grounding": {
        "semantic_family": "Argument_Grounding",
        "semantic_role": "numeric_unit_conversion",
        "behavior_tags": ["numeric_value", "unit_conversion", "bounds"],
    },
    "enum_grounding": {
        "semantic_family": "Argument_Grounding",
        "semantic_role": "enum_grounding",
        "behavior_tags": ["enum_value", "allowed_values"],
    },
    "dataflow": {
        "semantic_family": "Dataflow",
        "semantic_role": "read_bind_use",
        "behavior_tags": ["read_bind_use", "variable_scope"],
    },
    "dataflow_score": {
        "semantic_family": "Dataflow",
        "semantic_role": "read_bind_use",
        "behavior_tags": ["read_bind_use", "variable_scope"],
    },
    "loop_policy_error": {
        "semantic_family": "Loop",
        "semantic_role": "loop_constraints",
        "behavior_tags": ["loop_constraints", "break_policy", "no_unsupported_while"],
    },
}

FAMILY_ALIASES = {
    "Service_Mapping": "Service_Grounding",
    "Canonical_Service_Name": "Service_Grounding",
    "Owner_Device_Rule": "Receiver_Grounding",
    "Receiver_Tag_Preservation": "Receiver_Grounding",
    "Enum_Grounding": "Argument_Grounding",
    "Temporal_Rule": "Temporal",
    "Cron_Period_Planning": "Temporal",
    "Skeleton": "Control_Flow",
    "DET_Helper": "DET_Self_Check",
    "Minimality": "Minimality",
    "Output_Schema": "Output_Schema",
    "Dataflow": "Dataflow",
}

FALLBACK_BLOCK_HINTS = {
    "02": {
        "semantic_family": "Service_Grounding",
        "behavior_tags": ["schema_authority", "canonical_service_name", "receiver_tag"],
    },
    "03": {
        "semantic_family": "Output_Schema",
        "behavior_tags": ["json_only", "required_keys", "minimality"],
    },
    "05": {
        "semantic_family": "Repair",
        "behavior_tags": ["repair_contract", "fallback", "retry"],
    },
    "06": {
        "semantic_family": "DET_Self_Check",
        "behavior_tags": ["self_check", "semantic_diff", "validation"],
    },
}


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifest_path_for_generation(base_path: str | Path, generation: int) -> Path:
    return Path(base_path) / "registries" / f"generation_block_space_g{int(generation):03d}.json"


def load_manifest(
    base_path: str | Path | None = None,
    *,
    generation: int | None = None,
    block_space_id: str | None = None,
) -> dict[str, Any]:
    root = Path(base_path) if base_path else package_root()
    candidates: list[Path] = []
    if generation is not None:
        candidates.append(manifest_path_for_generation(root, int(generation)))
    if block_space_id:
        candidates.extend(sorted((root / "registries").glob("generation_block_space_g*.json")))
    if not candidates:
        candidates.append(manifest_path_for_generation(root, 0))
    for path in candidates:
        if not path.exists():
            continue
        manifest = read_json(path)
        if block_space_id and manifest.get("block_space_id") != block_space_id:
            continue
        validate_manifest(manifest)
        return manifest
    raise FileNotFoundError(f"generation block-space manifest not found under {root}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    atoms = manifest.get("atoms")
    if not isinstance(atoms, list) or not atoms:
        raise ValueError("manifest must contain a non-empty atoms list")
    seen: set[str] = set()
    for atom in atoms:
        if not isinstance(atom, dict):
            raise ValueError("manifest atom must be a JSON object")
        missing = sorted(REQUIRED_ATOM_FIELDS - set(atom))
        if missing:
            raise ValueError(f"atom {atom.get('local_id')} missing required metadata: {missing}")
        local_id = str(atom["local_id"])
        if local_id in seen:
            raise ValueError(f"duplicate generation-local atom id: {local_id}")
        seen.add(local_id)


def load_genome(base_path: str | Path | None = None, genome_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(base_path) if base_path else package_root()
    if genome_path:
        path = Path(genome_path)
        if not path.is_absolute():
            path = root / path
    else:
        path = root / "genomes" / "base_genome_g000.json"
    if not path.exists():
        manifest = load_manifest(root, generation=0)
        return make_default_genome(manifest)
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"genome JSON must be an object: {path}")
    return data


def make_default_genome(manifest: dict[str, Any], genome_id: str = "v16_g000_base") -> dict[str, Any]:
    return {
        "genome_id": genome_id,
        "generation": manifest.get("generation", 0),
        "block_space_id": manifest.get("block_space_id", "seg_000"),
        "active_atoms": [
            str(atom["local_id"])
            for atom in sorted(manifest["atoms"], key=lambda item: int(item.get("render_order", 0)))
            if atom.get("required") or atom.get("default_active", True)
        ],
        "atom_params": {},
        "block_variants": {},
        "block_operations": [],
        "metadata": {
            "schema": "v16_dynamic_genome.v1",
            "local_ids_are_generation_specific": True,
        },
    }


def normalize_genome(genome: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(genome if isinstance(genome, dict) else {})
    out.setdefault("genome_id", "v16_dynamic_genome")
    out["generation"] = int(out.get("generation", manifest.get("generation", 0)) or 0)
    out["block_space_id"] = str(out.get("block_space_id") or manifest.get("block_space_id"))
    atom_ids = {str(atom["local_id"]) for atom in manifest["atoms"]}
    required = {str(atom["local_id"]) for atom in manifest["atoms"] if atom.get("required")}
    requested = [str(atom_id) for atom_id in out.get("active_atoms", []) if str(atom_id) in atom_ids]
    active = list(dict.fromkeys([*sorted(required), *requested]))
    if not active:
        active = make_default_genome(manifest)["active_atoms"]
    out["active_atoms"] = active
    out.setdefault("atom_params", {})
    out.setdefault("block_variants", {})
    out.setdefault("block_operations", [])
    out.setdefault("metadata", {})
    out["metadata"]["local_ids_are_generation_specific"] = True
    return out


def atom_text(base_path: str | Path, atom: dict[str, Any]) -> str:
    path = Path(base_path) / str(atom["path"])
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _micro_rule_block(local_id: str, params: dict[str, Any]) -> str:
    rules = [str(rule).strip() for rule in params.get("micro_rules", []) if str(rule).strip()]
    if not rules:
        return ""
    lines = [f"\n[Atom {local_id} generation-local micro-rules]"]
    lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines) + "\n"


def render_from_manifest(
    *,
    base_path: str | Path | None = None,
    manifest: dict[str, Any] | None = None,
    genome: dict[str, Any] | None = None,
    user_input: str = "",
    connected_devices: dict[str, Any] | None = None,
    other_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(base_path) if base_path else package_root()
    manifest = manifest or load_manifest(root, generation=0)
    genome = normalize_genome(genome or make_default_genome(manifest), manifest)
    active = set(str(atom_id) for atom_id in genome.get("active_atoms", []))
    rendered_atoms: list[dict[str, Any]] = []
    prompt_parts: list[str] = []
    for atom in sorted(manifest["atoms"], key=lambda item: int(item.get("render_order", 0))):
        local_id = str(atom["local_id"])
        if not atom.get("required") and local_id not in active:
            continue
        text = atom_text(root, atom)
        params = genome.get("atom_params", {}).get(local_id, {})
        if isinstance(params, dict) and str(params.get("replacement_text") or "").strip():
            text = str(params["replacement_text"]).strip() + "\n"
        if isinstance(params, dict):
            text = text.rstrip() + "\n" + _micro_rule_block(local_id, params)
        prompt_parts.append(text.rstrip())
        rendered_atoms.append(
            {
                "block_id": local_id,
                "atom_id": local_id,
                "family": atom.get("semantic_family"),
                "semantic_family": atom.get("semantic_family"),
                "semantic_role": atom.get("semantic_role"),
                "behavior_tags": atom.get("behavior_tags", []),
                "title": atom.get("name"),
                "order": atom.get("render_order"),
                "source": "generation_block_space_manifest",
                "path": atom.get("path"),
                "content_hash": atom.get("content_hash"),
                "lineage": atom.get("lineage", {}),
                "text": text,
            }
        )

    runtime_context = {
        "command_eng": user_input,
        "connected_devices": connected_devices or {},
        "other_params": other_params or {},
    }
    prompt_parts.append(
        "[V16 Dynamic Runtime Context]\n"
        + json.dumps(runtime_context, ensure_ascii=False, indent=2)
        + "\nReturn exactly one JOI JSON object for command_eng."
    )
    prompt_text = "\n\n---\n\n".join(part for part in prompt_parts if part.strip())
    return {
        "prompt_text": prompt_text,
        "system_prompt": prompt_text,
        "user_prompt": user_input,
        "messages": [
            {"role": "system", "content": prompt_text},
            {"role": "user", "content": user_input},
        ],
        "blocks": rendered_atoms,
        "prompt_manifest": manifest,
        "genome": genome,
        "metadata": {
            "model_id": "gpt_mg.version0_16",
            "block_space_id": manifest.get("block_space_id"),
            "generation": manifest.get("generation"),
            "active_atoms": sorted(active),
            "rendered_atom_paths": [str(item.get("path")) for item in rendered_atoms],
            "semantic_families": sorted({str(item.get("semantic_family")) for item in rendered_atoms}),
            "prompt_chars": len(prompt_text),
            "messages": 2,
            "renderer": "v16_manifest_driven",
        },
    }


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def record_operation(genome: dict[str, Any], operation: dict[str, Any]) -> None:
    genome.setdefault("block_operations", []).append(operation)


def activate_atom(genome: dict[str, Any], atom_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(genome)
    active = list(out.get("active_atoms", []))
    if atom_id not in active:
        active.append(atom_id)
    out["active_atoms"] = active
    record_operation(out, {"op": "activate_atom", "atom_id": atom_id, "reason": reason})
    return out


def deactivate_atom(genome: dict[str, Any], atom_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(genome)
    out["active_atoms"] = [item for item in out.get("active_atoms", []) if item != atom_id]
    record_operation(out, {"op": "deactivate_atom", "atom_id": atom_id, "reason": reason})
    return out


def attach_micro_rule(genome: dict[str, Any], atom_id: str, rule: str, reason: str = "") -> dict[str, Any]:
    out = activate_atom(genome, atom_id, reason=reason)
    params = out.setdefault("atom_params", {}).setdefault(atom_id, {})
    rules = list(params.get("micro_rules") or [])
    if rule and rule not in rules:
        rules.append(rule)
    params["micro_rules"] = rules
    record_operation(out, {"op": "attach_micro_rule", "atom_id": atom_id, "rule": rule, "reason": reason})
    return out


def remove_micro_rule(genome: dict[str, Any], atom_id: str, rule: str, reason: str = "") -> dict[str, Any]:
    out = _copy(genome)
    params = out.setdefault("atom_params", {}).setdefault(atom_id, {})
    params["micro_rules"] = [item for item in params.get("micro_rules", []) if item != rule]
    record_operation(out, {"op": "remove_micro_rule", "atom_id": atom_id, "rule": rule, "reason": reason})
    return out


def rewrite_atom(genome: dict[str, Any], atom_id: str, text: str, reason: str = "") -> dict[str, Any]:
    out = activate_atom(genome, atom_id, reason=reason)
    out.setdefault("atom_params", {}).setdefault(atom_id, {})["replacement_text"] = text
    record_operation(out, {"op": "rewrite_atom", "atom_id": atom_id, "reason": reason})
    return out


def replace_atom_variant(genome: dict[str, Any], atom_id: str, variant: str, reason: str = "") -> dict[str, Any]:
    out = activate_atom(genome, atom_id, reason=reason)
    out.setdefault("block_variants", {})[atom_id] = variant
    record_operation(out, {"op": "replace_atom_variant", "atom_id": atom_id, "variant": variant, "reason": reason})
    return out


def relabel_atom(manifest: dict[str, Any], atom_id: str, semantic_family: str, semantic_role: str, reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    for atom in out["atoms"]:
        if str(atom["local_id"]) == atom_id:
            atom["semantic_family"] = semantic_family
            atom["semantic_role"] = semantic_role
            atom["lineage"] = {"op": "relabel_atom", "parents": [atom_id], "reason": reason}
            break
    validate_manifest(out)
    return out


def reorder_atoms(manifest: dict[str, Any], ordered_ids: list[str], reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    rank = {str(atom_id): idx for idx, atom_id in enumerate(ordered_ids)}
    for atom in out["atoms"]:
        atom["render_order"] = rank.get(str(atom["local_id"]), int(atom.get("render_order", 0)))
        atom.setdefault("lineage", {}).setdefault("notes", []).append({"op": "reorder_atoms", "reason": reason})
    validate_manifest(out)
    return out


def promote_required(manifest: dict[str, Any], atom_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    for atom in out["atoms"]:
        if str(atom["local_id"]) == atom_id:
            atom["required"] = True
            atom.setdefault("lineage", {}).setdefault("notes", []).append({"op": "promote_required", "reason": reason})
    validate_manifest(out)
    return out


def demote_optional(manifest: dict[str, Any], atom_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    for atom in out["atoms"]:
        if str(atom["local_id"]) == atom_id:
            atom["required"] = False
            atom.setdefault("lineage", {}).setdefault("notes", []).append({"op": "demote_optional", "reason": reason})
    validate_manifest(out)
    return out


def retire_atom(manifest: dict[str, Any], atom_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    for atom in out["atoms"]:
        if str(atom["local_id"]) == atom_id:
            atom["retired"] = True
            atom["required"] = False
            atom.setdefault("lineage", {}).setdefault("notes", []).append({"op": "retire_atom", "reason": reason})
    validate_manifest(out)
    return out


def split_atom(manifest: dict[str, Any], atom_id: str, child_ids: list[str], reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    for atom in out["atoms"]:
        if str(atom["local_id"]) == atom_id:
            atom.setdefault("lineage", {}).setdefault("notes", []).append({"op": "split_atom", "children": child_ids, "reason": reason})
    return out


def merge_atoms(manifest: dict[str, Any], parent_ids: list[str], child_id: str, reason: str = "") -> dict[str, Any]:
    out = _copy(manifest)
    out.setdefault("block_operations", []).append({"op": "merge_atoms", "parents": parent_ids, "child": child_id, "reason": reason})
    return out


def create_new_atom(
    manifest: dict[str, Any],
    *,
    base_path: str | Path,
    name: str,
    semantic_family: str,
    semantic_role: str,
    behavior_tags: list[str],
    text: str,
    reason: str,
    failure_targets: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    out = _copy(manifest)
    generation = int(out.get("generation", 0) or 0)
    existing = {str(atom["local_id"]) for atom in out["atoms"]}
    next_index = 0
    while f"{next_index:02d}" in existing:
        next_index += 1
    local_id = f"{next_index:02d}"
    safe_name = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "new_atom"
    rel_path = f"blocks/generated/g{generation:03d}/{local_id}_{safe_name}.md"
    path = Path(base_path) / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    content = text.rstrip() + "\n"
    path.write_text(content, encoding="utf-8")
    atom = {
        "local_id": local_id,
        "name": safe_name,
        "semantic_family": semantic_family,
        "semantic_role": semantic_role,
        "behavior_tags": list(dict.fromkeys(behavior_tags)),
        "source_span": {"start_line": None, "end_line": None},
        "content_hash": sha256_text(content),
        "path": rel_path,
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "rewrite", "split", "retire"],
        "crossover_enabled": True,
        "order_group": semantic_family.lower(),
        "render_order": max(int(atom.get("render_order", 0)) for atom in out["atoms"]) + 1,
        "lineage": {"op": "create_new_atom", "parents": [], "source": "dynamic_patch_adapter", "reason": reason},
        "failure_targets": failure_targets or [],
    }
    out["atoms"].append(atom)
    validate_manifest(out)
    return out, atom


def _base_failure(reason: Any) -> str:
    text = str(reason or "").strip()
    if text.startswith("unknown_service:"):
        return "unknown_service"
    return text.split(":", 1)[0]


def infer_target_selector(patch: dict[str, Any]) -> dict[str, Any]:
    reasons = [
        _base_failure(item)
        for item in patch.get("evidence_failure_reasons", [])
        if str(item).strip()
    ]
    reasons.extend(
        _base_failure(item)
        for item in patch.get("failure_reasons", [])
        if str(item).strip()
    )
    basis = patch.get("strict_det_basis") if isinstance(patch.get("strict_det_basis"), dict) else {}
    for raw in basis.get("top_failure_reasons", []) if isinstance(basis.get("top_failure_reasons"), list) else []:
        if isinstance(raw, (list, tuple)) and raw:
            reasons.append(_base_failure(raw[0]))
        elif isinstance(raw, dict):
            reasons.append(_base_failure(raw.get("failure_reason") or raw.get("root_cause")))
    reasons = list(dict.fromkeys(reason for reason in reasons if reason))

    selector = patch.get("target_selector") if isinstance(patch.get("target_selector"), dict) else {}
    family = str(selector.get("semantic_family") or "").strip()
    role = str(selector.get("semantic_role") or "").strip()
    tags = [str(tag).strip() for tag in selector.get("behavior_tags", []) if str(tag).strip()]
    failure_reason = str(selector.get("failure_reason") or (reasons[0] if reasons else "")).strip()
    if failure_reason in FAILURE_TARGET_MAP:
        mapped = FAILURE_TARGET_MAP[failure_reason]
        family = family or str(mapped["semantic_family"])
        role = role or str(mapped["semantic_role"])
        tags.extend(mapped.get("behavior_tags", []))

    patch_family = str(patch.get("target_block_family") or "").strip()
    if patch_family:
        family = family or FAMILY_ALIASES.get(patch_family, patch_family)
    fallback_block_id = str(patch.get("target_block_id") or selector.get("fallback_block_id") or "").zfill(2)
    if not family and fallback_block_id in FALLBACK_BLOCK_HINTS:
        hint = FALLBACK_BLOCK_HINTS[fallback_block_id]
        family = str(hint["semantic_family"])
        tags.extend(hint["behavior_tags"])

    return {
        "semantic_family": family or "DET_Self_Check",
        "semantic_role": role or re.sub(r"[^a-z0-9_]+", "_", (failure_reason or patch_family or "general").lower()).strip("_"),
        "behavior_tags": list(dict.fromkeys(tag for tag in tags if tag)),
        "failure_reason": failure_reason,
        "fallback_block_id": fallback_block_id,
    }


def _score_atom(selector: dict[str, Any], atom: dict[str, Any]) -> float:
    score = 0.0
    family = str(selector.get("semantic_family") or "")
    if family and family == str(atom.get("semantic_family") or ""):
        score += 0.50
    role = str(selector.get("semantic_role") or "")
    if role and role == str(atom.get("semantic_role") or ""):
        score += 0.20
    selector_tags = set(selector.get("behavior_tags") or [])
    atom_tags = set(atom.get("behavior_tags") or [])
    if selector_tags:
        score += 0.25 * (len(selector_tags & atom_tags) / len(selector_tags))
    failure = str(selector.get("failure_reason") or "")
    if failure and failure in set(atom.get("failure_targets") or []):
        score += 0.20
    if atom.get("required"):
        score += 0.02
    order = int(atom.get("render_order", 0) or 0)
    score += max(0.0, 0.03 - min(order, 30) * 0.001)
    return round(score, 6)


def resolve_selector_to_atom(
    selector: dict[str, Any],
    manifest: dict[str, Any],
    *,
    min_score: float = 0.45,
    tie_delta: float = 0.05,
) -> dict[str, Any]:
    scored = sorted(
        [
            {"atom": atom, "score": _score_atom(selector, atom)}
            for atom in manifest.get("atoms", [])
            if not atom.get("retired")
        ],
        key=lambda item: item["score"],
        reverse=True,
    )
    if not scored or scored[0]["score"] < min_score:
        return {"status": "no_confident_match", "best": scored[:5], "selected_atom": None}
    if len(scored) > 1 and scored[0]["score"] - scored[1]["score"] < tie_delta:
        return {"status": "ambiguous_match", "best": scored[:5], "selected_atom": None}
    return {"status": "resolved", "best": scored[:5], "selected_atom": scored[0]["atom"]}


def _patch_micro_rules(patch: dict[str, Any]) -> list[str]:
    rules: list[str] = []
    for key in ("micro_rules", "proposed_micro_rules", "patch_text", "micro_rule"):
        value = patch.get(key)
        if isinstance(value, list):
            rules.extend(str(item).strip() for item in value if str(item).strip())
        elif str(value or "").strip():
            rules.append(str(value).strip())
    return list(dict.fromkeys(rules))


def apply_dynamic_patch_output(
    *,
    patches_output: dict[str, Any],
    base_path: str | Path | None = None,
    manifest: dict[str, Any] | None = None,
    genome: dict[str, Any] | None = None,
    create_on_unresolved: bool = True,
) -> dict[str, Any]:
    root = Path(base_path) if base_path else package_root()
    manifest = manifest or load_manifest(root, generation=0)
    genome = normalize_genome(genome or make_default_genome(manifest), manifest)
    raw_patches = patches_output.get("prompt_patches", []) if isinstance(patches_output, dict) else []
    applications: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for index, patch in enumerate(raw_patches, start=1):
        if not isinstance(patch, dict):
            unresolved.append({"index": index, "reason": "malformed_patch", "patch": patch})
            continue
        patch_id = str(patch.get("patch_id") or patch.get("proposal_id") or f"patch_{index:03d}")
        selector = infer_target_selector(patch)
        resolution = resolve_selector_to_atom(selector, manifest)
        rules = _patch_micro_rules(patch)
        action = str(patch.get("patch_action") or patch.get("operation") or "attach_micro_rule")
        selected_atom = resolution.get("selected_atom")
        created_atom = None
        accepted = False
        reason = str(resolution["status"])
        if selected_atom:
            atom_id = str(selected_atom["local_id"])
            if action in {"append_micro_rule", "strengthen_existing_rule", "diversify_micro_rules", "attach_micro_rule"}:
                for rule in rules:
                    genome = attach_micro_rule(genome, atom_id, rule, reason=f"advisor_patch:{patch_id}")
                accepted = bool(rules)
            elif action in {"replace_sentence", "rewrite_atom"}:
                genome = rewrite_atom(genome, atom_id, "\n".join(rules), reason=f"advisor_patch:{patch_id}")
                accepted = bool(rules)
            else:
                genome = attach_micro_rule(genome, atom_id, "\n".join(rules), reason=f"advisor_patch:{patch_id}")
                accepted = bool(rules)
        elif create_on_unresolved and rules:
            text = "\n".join(["[Advisor-created dynamic atom]", *[f"- {rule}" for rule in rules]])
            manifest, created_atom = create_new_atom(
                manifest,
                base_path=root,
                name=selector.get("semantic_role") or patch_id,
                semantic_family=str(selector.get("semantic_family") or "DET_Self_Check"),
                semantic_role=str(selector.get("semantic_role") or "advisor_created_atom"),
                behavior_tags=list(selector.get("behavior_tags") or []),
                text=text,
                reason=f"{resolution['status']}; no silent fallback to fixed block {selector.get('fallback_block_id')}",
                failure_targets=[str(selector.get("failure_reason") or "")] if selector.get("failure_reason") else [],
            )
            genome = attach_micro_rule(genome, str(created_atom["local_id"]), " ".join(rules), reason=f"advisor_patch:{patch_id}:create_new_atom")
            accepted = True
            reason = "created_new_atom"
        else:
            unresolved.append({"patch_id": patch_id, "reason": resolution["status"], "selector": selector, "patch": patch})
        applications.append(
            {
                "patch_id": patch_id,
                "source": "dynamic_patch_adapter",
                "fallback_block_id": selector.get("fallback_block_id"),
                "target_selector": selector,
                "resolution_status": reason,
                "accepted": accepted,
                "selected_atom_id": str(selected_atom.get("local_id")) if selected_atom else "",
                "created_atom_id": str(created_atom.get("local_id")) if created_atom else "",
                "micro_rule_count": len(rules),
                "best_matches": [
                    {
                        "local_id": item["atom"].get("local_id"),
                        "semantic_family": item["atom"].get("semantic_family"),
                        "semantic_role": item["atom"].get("semantic_role"),
                        "score": item["score"],
                    }
                    for item in resolution.get("best", [])
                ],
            }
        )

    genome = normalize_genome(genome, manifest)
    return {
        "manifest": manifest,
        "patched_genome": genome,
        "applications": applications,
        "unresolved_patches": unresolved,
        "summary": {
            "patch_count": len(raw_patches),
            "accepted_count": sum(1 for item in applications if item.get("accepted")),
            "created_atom_count": sum(1 for item in applications if item.get("created_atom_id")),
            "unresolved_count": len(unresolved),
            "silent_fallback_count": 0,
        },
    }
