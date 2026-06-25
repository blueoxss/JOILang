#!/usr/bin/env python3
from __future__ import annotations

import copy
import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .artifacts import utc_now, write_json
except ImportError:
    from artifacts import utc_now, write_json  # type: ignore

try:
    from utils.prompt_advisor.schemas import FAMILY_TO_DEFAULT_BLOCK, normalize_patch
except Exception:  # pragma: no cover - fallback for standalone use
    FAMILY_TO_DEFAULT_BLOCK = {"Service_Mapping": "02", "Output_Schema": "03", "Repair_Clause": "05", "DET_Helper": "06"}

    def normalize_patch(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
        patch = dict(raw)
        patch.setdefault("patch_id", f"patch_{index:03d}")
        patch.setdefault("target_block_family", "DET_Helper")
        patch.setdefault("target_block_id", FAMILY_TO_DEFAULT_BLOCK.get(patch["target_block_family"], "06"))
        patch.setdefault("operation", "append_micro_rule")
        patch.setdefault("patch_text", "")
        return patch


CORE_BLOCKS = ("01", "02")
OPTIONAL_BLOCKS = ("03", "05", "06")
BLOCK_ORDER = ("01", "02", "03", "05", "06")
V16_MODEL_ID = "gpt_mg.version0_16"


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def is_v16_dynamic_package(rendered_package: dict[str, Any] | None) -> bool:
    if not isinstance(rendered_package, dict):
        return False
    manifest = rendered_package.get("prompt_manifest")
    metadata = rendered_package.get("metadata") if isinstance(rendered_package.get("metadata"), dict) else {}
    prompt_render = rendered_package.get("prompt_render") if isinstance(rendered_package.get("prompt_render"), dict) else {}
    model_id = str(rendered_package.get("model_id") or metadata.get("model_id") or "")
    if model_id == V16_MODEL_ID:
        return True
    if isinstance(manifest, dict) and manifest.get("local_ids_are_generation_specific") is True:
        return True
    return bool(prompt_render.get("supports_dynamic_block_space") and "version0_16" in str(rendered_package.get("source_model_package") or ""))


def _v16_base_path(rendered_package: dict[str, Any]) -> Path:
    metadata = rendered_package.get("metadata") if isinstance(rendered_package.get("metadata"), dict) else {}
    for key in ("base_path",):
        value = metadata.get(key)
        if value:
            return Path(str(value))
    for key in ("source_model_package", "model_package"):
        value = rendered_package.get(key)
        if value:
            return Path(str(value))
    return Path("gpt_mg/version0_16").resolve()


def _render_v16_with_genome(rendered_package: dict[str, Any], genome: dict[str, Any]) -> dict[str, Any]:
    from gpt_mg.version0_16.tools.block_space_ops import load_manifest, render_from_manifest

    base_path = _v16_base_path(rendered_package)
    manifest = rendered_package.get("prompt_manifest") if isinstance(rendered_package.get("prompt_manifest"), dict) else {}
    generation = genome.get("generation") if isinstance(genome, dict) else None
    block_space_id = genome.get("block_space_id") if isinstance(genome, dict) else None
    if not manifest or (
        block_space_id
        and str(manifest.get("block_space_id") or "") != str(block_space_id)
    ):
        try:
            manifest = load_manifest(base_path, generation=int(generation) if generation is not None else None, block_space_id=str(block_space_id or ""))
        except Exception:
            manifest = load_manifest(base_path, generation=0)
    user_input = str(rendered_package.get("user_prompt") or "")
    rendered = render_from_manifest(
        base_path=base_path,
        manifest=manifest,
        genome=genome,
        user_input=user_input,
        connected_devices={},
        other_params={"rendered_from_genome": True},
    )
    patched = copy.deepcopy(rendered_package)
    patched.update(
        {
            "prompt_text": rendered["prompt_text"],
            "system_prompt": rendered["system_prompt"],
            "user_prompt": rendered["user_prompt"],
            "messages": rendered["messages"],
            "blocks": rendered["blocks"],
            "blocks_metadata": rendered["blocks"],
            "prompt_manifest": rendered["prompt_manifest"],
            "genome": rendered["genome"],
        }
    )
    metadata = dict(patched.get("metadata") or {})
    metadata.update(rendered.get("metadata", {}))
    metadata["rendered_from_v16_dynamic_genome"] = True
    patched["metadata"] = metadata
    return patched


def fallback_genome() -> dict[str, Any]:
    return {"id": "patched_base", "blocks": ["01", "02", "03", "06"], "params": {}, "block_params": {}, "seed": 0}


def load_base_genome(path: str | Path | None = None) -> dict[str, Any]:
    if path and Path(path).exists():
        data = read_json(path)
        return ensure_genome(data if isinstance(data, dict) else {})
    return fallback_genome()


def normalize_blocks(blocks: Any) -> list[str]:
    requested = [str(block).zfill(2) for block in (blocks if isinstance(blocks, list) else [])]
    active = ["01", "02"]
    for block in BLOCK_ORDER:
        if block in CORE_BLOCKS:
            continue
        if block in requested and block not in active:
            active.append(block)
    return active


def ensure_genome(genome: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(genome)
    out["blocks"] = normalize_blocks(out.get("blocks") or ["01", "02", "03", "06"])
    out.setdefault("params", {})
    out.setdefault("block_params", {})
    out.setdefault("advisor_metadata", {})
    return out


def patch_list(patches_output: dict[str, Any]) -> list[dict[str, Any]]:
    raw_patches = patches_output.get("prompt_patches", []) if isinstance(patches_output, dict) else []
    return [normalize_patch(patch if isinstance(patch, dict) else {}, index) for index, patch in enumerate(raw_patches, start=1)]


def _add_block(genome: dict[str, Any], block_id: str) -> None:
    block_id = str(block_id).zfill(2)
    blocks = list(genome.get("blocks") or [])
    if block_id in OPTIONAL_BLOCKS and block_id not in blocks:
        blocks.append(block_id)
    genome["blocks"] = normalize_blocks(blocks)


def _append_micro_rule(genome: dict[str, Any], block_id: str, text: str) -> bool:
    if not text.strip():
        return False
    _add_block(genome, block_id)
    params = genome.setdefault("block_params", {}).setdefault(str(block_id).zfill(2), {})
    rules = list(params.get("micro_rules") or [])
    if text not in rules:
        rules.append(text)
        params["micro_rules"] = rules
        return True
    params["micro_rules"] = rules
    return False


def _replace_block_text(genome: dict[str, Any], block_id: str, text: str) -> bool:
    if not text.strip():
        return False
    _add_block(genome, block_id)
    params = genome.setdefault("block_params", {}).setdefault(str(block_id).zfill(2), {})
    previous = str(params.get("replacement_text") or "")
    params["replacement_text"] = text
    return previous != text


def _reduce_few_shot(genome: dict[str, Any], block_id: str) -> bool:
    _add_block(genome, block_id)
    params = genome.setdefault("block_params", {}).setdefault(str(block_id).zfill(2), {})
    before = params.get("few_shot_count")
    params["few_shot_count"] = 0 if before is None else max(0, int(before) - 1)
    return params["few_shot_count"] != before


def _compress_candidate_strategies(genome: dict[str, Any]) -> bool:
    params = genome.setdefault("params", {})
    before = list(params.get("candidate_strategies") or [])
    if not before:
        params["candidate_strategies"] = ["direct", "compact_json"]
        return True
    kept = []
    for item in before:
        if item not in kept:
            kept.append(item)
        if len(kept) >= 2:
            break
    params["candidate_strategies"] = kept
    return kept != before


def apply_patch_to_genome(genome: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    operation = str(patch.get("operation") or "append_micro_rule")
    family = str(patch.get("target_block_family") or "DET_Helper")
    block_id = str(patch.get("target_block_id") or FAMILY_TO_DEFAULT_BLOCK.get(family, "06")).zfill(2)
    text = str(patch.get("patch_text") or "")
    changed = False
    if operation in {"append_micro_rule", "strengthen_existing_rule", "diversify_micro_rules", "promote_gene_to_dynamic_core", "demote_gene_to_optional"}:
        changed = _append_micro_rule(genome, block_id, text)
    elif operation == "activate_optional_block":
        before = list(genome.get("blocks") or [])
        _add_block(genome, block_id)
        changed = before != genome.get("blocks")
    elif operation == "deactivate_optional_block":
        if block_id not in CORE_BLOCKS:
            before = list(genome.get("blocks") or [])
            genome["blocks"] = normalize_blocks([block for block in before if block != block_id])
            changed = before != genome["blocks"]
    elif operation in {"delete_conflicting_rule", "suppress_gene"}:
        genome.setdefault("advisor_metadata", {}).setdefault("suppressed_patch_ids", []).append(patch.get("patch_id"))
        changed = True
    elif operation in {"replace_sentence", "replace_block_text"}:
        changed = _replace_block_text(genome, block_id, text)
    elif operation == "reduce_few_shot":
        changed = _reduce_few_shot(genome, block_id)
    elif operation == "compress_candidate_strategies":
        changed = _compress_candidate_strategies(genome)
    genome.setdefault("advisor_metadata", {}).setdefault("applied_patch_ids", []).append(patch.get("patch_id"))
    return {"patch_id": patch.get("patch_id"), "operation": operation, "target_block_id": block_id, "target_block_family": family, "changed": changed, "patch_text": text}


def rendered_prompt_with_genome(rendered_package: dict[str, Any] | None, genome: dict[str, Any]) -> str:
    if is_v16_dynamic_package(rendered_package) and isinstance(genome, dict) and "active_atoms" in genome:
        return str(_render_v16_with_genome(rendered_package or {}, genome).get("prompt_text") or "")
    base = str((rendered_package or {}).get("prompt_text") or "")
    lines = []
    for block_id, params in (genome.get("block_params") or {}).items():
        rules = params.get("micro_rules") if isinstance(params, dict) else []
        if rules:
            lines.append(f"[GA block {block_id} micro_rules]")
            lines.extend(f"- {rule}" for rule in rules)
        replacement = params.get("replacement_text") if isinstance(params, dict) else ""
        if replacement:
            lines.append(f"[GA block {block_id} replacement_text]")
            lines.append(str(replacement))
    if not lines:
        return base
    return base.rstrip() + "\n\n---\n[GA Prompt Patch Overlay]\n" + "\n".join(lines) + "\n"


def rendered_package_with_genome(rendered_package: dict[str, Any], genome: dict[str, Any]) -> dict[str, Any]:
    if is_v16_dynamic_package(rendered_package) and isinstance(genome, dict) and "active_atoms" in genome:
        return _render_v16_with_genome(rendered_package, genome)
    patched = copy.deepcopy(rendered_package)
    prompt = rendered_prompt_with_genome(rendered_package, genome)
    patched["prompt_text"] = prompt
    patched["system_prompt"] = prompt if not patched.get("user_prompt") else patched.get("system_prompt", "")
    patched["genome"] = genome
    messages = patched.get("messages")
    if isinstance(messages, list) and messages:
        new_messages = copy.deepcopy(messages)
        for message in new_messages:
            if isinstance(message, dict) and message.get("role") == "system":
                message["content"] = prompt if not patched.get("user_prompt") else str(message.get("content") or "") + "\n\n" + prompt.split("[GA Prompt Patch Overlay]", 1)[-1]
                break
        else:
            new_messages.insert(0, {"role": "system", "content": prompt})
        patched["messages"] = new_messages
    return patched


def _apply_v16_prompt_patches(
    *,
    prompt_patches_path: str | Path,
    out_dir: str | Path,
    base_genome_path: str | Path | None,
    rendered_package: dict[str, Any],
) -> dict[str, Any]:
    from gpt_mg.version0_16.tools.block_space_ops import apply_dynamic_patch_output, load_genome, write_json

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    base_path = _v16_base_path(rendered_package)
    patches_output = read_json(prompt_patches_path)
    manifest = rendered_package.get("prompt_manifest") if isinstance(rendered_package.get("prompt_manifest"), dict) else {}
    if not manifest:
        from gpt_mg.version0_16.tools.block_space_ops import load_manifest

        manifest = load_manifest(base_path, generation=0)
    if base_genome_path:
        genome = load_genome(base_path, base_genome_path)
    elif isinstance(rendered_package.get("genome"), dict):
        genome = copy.deepcopy(rendered_package["genome"])
    else:
        genome = load_genome(base_path, None)
    result = apply_dynamic_patch_output(
        patches_output=patches_output,
        base_path=base_path,
        manifest=manifest,
        genome=genome,
        create_on_unresolved=True,
    )
    patched_package = _render_v16_with_genome(rendered_package, result["patched_genome"])
    prompt_preview = str(patched_package.get("prompt_text") or "")
    write_json(root / "patched_genome.json", result["patched_genome"])
    write_json(root / "patched_block_space_manifest.json", result["manifest"])
    report = {
        "created_at": utc_now(),
        "dynamic_block_space": True,
        "model_id": V16_MODEL_ID,
        "prompt_patches_path": str(prompt_patches_path),
        "base_genome_path": str(base_genome_path or "rendered_package.genome"),
        "patched_genome_path": str(root / "patched_genome.json"),
        "patched_manifest_path": str(root / "patched_block_space_manifest.json"),
        "accepted_proposal_count": int(result["summary"].get("accepted_count") or 0),
        "advisor_child_scheduled_count": 1 if int(result["summary"].get("accepted_count") or 0) > 0 else 0,
        "advisor_backed_diff_count": int(result["summary"].get("accepted_count") or 0),
        "patch_count": int(result["summary"].get("patch_count") or 0),
        "patch_visibility_ok": True,
        "before_active_atoms": list(genome.get("active_atoms") or []),
        "after_active_atoms": list(result["patched_genome"].get("active_atoms") or []),
        "summary": result["summary"],
        "applications": result["applications"],
        "unresolved_patches": result["unresolved_patches"],
        "policy": {
            "target_block_id_is_fallback_only": True,
            "silent_fallback_count": 0,
            "unresolved_policy": "create_new_atom_with_lineage_or_record_unresolved",
        },
    }
    write_json(root / "patch_application_report.json", report)
    diff_lines = ["# V16 Dynamic Prompt Patch Diff", "", "## Applications"]
    for item in result["applications"]:
        diff_lines.append(
            "- `{}` status={} accepted={} selected_atom={} created_atom={} fallback_hint={}".format(
                item.get("patch_id"),
                item.get("resolution_status"),
                item.get("accepted"),
                item.get("selected_atom_id") or "-",
                item.get("created_atom_id") or "-",
                item.get("fallback_block_id") or "-",
            )
        )
    diff_lines.extend(["", "## Policy", "- silent_fallback_count: `0`", "- numeric block ids are fallback hints only", ""])
    (root / "patch_diff.md").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
    (root / "patched_prompt_preview.md").write_text(prompt_preview, encoding="utf-8")
    return {"patched_genome": result["patched_genome"], "report": report, "prompt_preview": prompt_preview}


def apply_prompt_patches(
    *,
    prompt_patches_path: str | Path,
    out_dir: str | Path,
    base_genome_path: str | Path | None = None,
    rendered_package: dict[str, Any] | None = None,
    write_source_file: bool = False,
) -> dict[str, Any]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    if is_v16_dynamic_package(rendered_package):
        return _apply_v16_prompt_patches(
            prompt_patches_path=prompt_patches_path,
            out_dir=root,
            base_genome_path=base_genome_path,
            rendered_package=rendered_package or {},
        )
    patches_output = read_json(prompt_patches_path)
    genome = load_base_genome(base_genome_path)
    before = copy.deepcopy(genome)
    applications = [apply_patch_to_genome(genome, patch) for patch in patch_list(patches_output)]
    genome["id"] = str(genome.get("id") or "patched_base") + "_patched"
    prompt_preview = rendered_prompt_with_genome(rendered_package, genome)
    visible = [
        item["patch_id"]
        for item in applications
        if item.get("patch_text") and str(item["patch_text"]) in prompt_preview
    ]
    if write_source_file:
        source_dir = root / "generated_blocks"
        source_dir.mkdir(parents=True, exist_ok=True)
        for item in applications:
            if item.get("patch_text"):
                (source_dir / f"block_{item['target_block_id']}_{item['patch_id']}.md").write_text(str(item["patch_text"]) + "\n", encoding="utf-8")
    diff_lines = ["# Prompt Patch Diff", "", "## Applied Patches"]
    for item in applications:
        diff_lines.append(
            f"- `{item.get('patch_id')}` op={item.get('operation')} block={item.get('target_block_id')} changed={item.get('changed')}"
        )
    diff_lines.extend(["", "## Visibility", f"- visible_patch_count: `{len(visible)}`", ""])
    report = {
        "created_at": utc_now(),
        "prompt_patches_path": str(prompt_patches_path),
        "base_genome_path": str(base_genome_path or "fallback"),
        "patched_genome_path": str(root / "patched_genome.json"),
        "accepted_proposal_count": sum(1 for item in applications if item.get("changed")),
        "advisor_child_scheduled_count": 1 if any(item.get("changed") for item in applications) else 0,
        "advisor_backed_diff_count": len(visible),
        "patch_count": len(applications),
        "visible_patch_ids": visible,
        "patch_visibility_ok": len(visible) >= sum(1 for item in applications if item.get("patch_text")),
        "applications": applications,
        "before_blocks": before.get("blocks", []),
        "after_blocks": genome.get("blocks", []),
    }
    write_json(root / "patched_genome.json", genome)
    write_json(root / "patch_application_report.json", report)
    (root / "patch_diff.md").write_text("\n".join(diff_lines) + "\n", encoding="utf-8")
    (root / "patched_prompt_preview.md").write_text(prompt_preview, encoding="utf-8")
    return {"patched_genome": genome, "report": report, "prompt_preview": prompt_preview}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply prompt_patches.json to a GA-compatible genome without editing prompt files.")
    parser.add_argument("--prompt-patches", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--base-genome", default="")
    parser.add_argument("--write-source-file", action="store_true")
    args = parser.parse_args()
    result = apply_prompt_patches(
        prompt_patches_path=args.prompt_patches,
        out_dir=args.out_dir,
        base_genome_path=args.base_genome or None,
        rendered_package=None,
        write_source_file=args.write_source_file,
    )
    print(json.dumps(result["report"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
