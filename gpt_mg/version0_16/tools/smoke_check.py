#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .block_space_ops import (
        apply_dynamic_patch_output,
        load_genome,
        load_manifest,
        package_root,
        render_from_manifest,
        resolve_selector_to_atom,
        validate_manifest,
    )
except ImportError:
    from block_space_ops import (  # type: ignore
        apply_dynamic_patch_output,
        load_genome,
        load_manifest,
        package_root,
        render_from_manifest,
        resolve_selector_to_atom,
        validate_manifest,
    )


FAILURE_SELECTORS = {
    "unknown_service": {
        "semantic_family": "Service_Grounding",
        "semantic_role": "canonical_service_name",
        "behavior_tags": ["schema_authority", "canonical_service_name", "no_invented_service"],
        "failure_reason": "unknown_service",
        "fallback_block_id": "06",
    },
    "cron_mismatch": {
        "semantic_family": "Temporal",
        "semantic_role": "cron_schedule",
        "behavior_tags": ["cron", "schedule"],
        "failure_reason": "cron_mismatch",
        "fallback_block_id": "06",
    },
    "numeric_grounding": {
        "semantic_family": "Argument_Grounding",
        "semantic_role": "numeric_unit_conversion",
        "behavior_tags": ["numeric_value", "unit_conversion", "bounds"],
        "failure_reason": "numeric_grounding",
        "fallback_block_id": "06",
    },
    "invalid_json": {
        "semantic_family": "Output_Schema",
        "semantic_role": "json_output_contract",
        "behavior_tags": ["json_only", "required_keys", "valid_json"],
        "failure_reason": "invalid_json",
        "fallback_block_id": "06",
    },
}


def _patches_for_failures() -> dict[str, Any]:
    patches = []
    for index, reason in enumerate(FAILURE_SELECTORS, start=1):
        patches.append(
            {
                "patch_id": f"synthetic_{reason}_{index:02d}",
                "target_block_id": "06",
                "failure_reasons": [reason],
                "operation": "append_micro_rule",
                "patch_text": f"Semantic test rule for {reason}; do not rely on fixed block 06.",
            }
        )
    return {"prompt_patches": patches}


def run() -> dict[str, Any]:
    root = package_root()
    results: dict[str, Any] = {"package_root": str(root), "generations": []}
    for generation in (0, 1):
        manifest = load_manifest(root, generation=generation)
        validate_manifest(manifest)
        genome = load_genome(root, root / "genomes" / f"base_genome_g{generation:03d}.json")
        rendered = render_from_manifest(
            base_path=root,
            manifest=manifest,
            genome=genome,
            user_input="Turn on the light.",
            connected_devices={},
            other_params={"smoke_check": True},
        )
        assert rendered["prompt_text"].strip()
        assert rendered["metadata"]["block_space_id"] == manifest["block_space_id"]
        assert len(manifest["atoms"]) != 0
        resolutions = {}
        for reason, selector in FAILURE_SELECTORS.items():
            resolution = resolve_selector_to_atom(selector, manifest)
            assert resolution["status"] == "resolved", (generation, reason, resolution)
            atom = resolution["selected_atom"]
            assert atom
            assert reason in atom.get("failure_targets", []) or set(selector["behavior_tags"]) & set(atom.get("behavior_tags", []))
            resolutions[reason] = {
                "status": resolution["status"],
                "selected_atom_id": atom["local_id"],
                "semantic_family": atom["semantic_family"],
                "semantic_role": atom["semantic_role"],
                "score": resolution["best"][0]["score"],
            }
        patch_result = apply_dynamic_patch_output(
            patches_output=_patches_for_failures(),
            base_path=root,
            manifest=manifest,
            genome=genome,
            create_on_unresolved=False,
        )
        assert patch_result["summary"]["silent_fallback_count"] == 0
        assert patch_result["summary"]["unresolved_count"] == 0, patch_result["unresolved_patches"]
        assert patch_result["summary"]["accepted_count"] == len(FAILURE_SELECTORS)
        results["generations"].append(
            {
                "generation": generation,
                "block_space_id": manifest["block_space_id"],
                "atom_count": len(manifest["atoms"]),
                "rendered_prompt_chars": len(rendered["prompt_text"]),
                "failure_resolutions": resolutions,
                "patch_summary": patch_result["summary"],
            }
        )
    assert results["generations"][0]["atom_count"] != results["generations"][1]["atom_count"]
    return results


def main() -> int:
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
