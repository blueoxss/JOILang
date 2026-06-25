#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .block_space_ops import sha256_text, write_json
except ImportError:
    from block_space_ops import sha256_text, write_json  # type: ignore


SEED_ATOMS: list[dict[str, Any]] = [
    {
        "local_id": "00",
        "name": "system_contract",
        "semantic_family": "Contract",
        "semantic_role": "system_contract",
        "behavior_tags": ["role", "task_scope", "json_only"],
        "span": (1, 16),
        "required": True,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": False,
        "order_group": "contract",
        "failure_targets": ["missing_generated_code", "invalid_json"],
    },
    {
        "local_id": "01",
        "name": "json_output_schema",
        "semantic_family": "Output_Schema",
        "semantic_role": "json_output_contract",
        "behavior_tags": ["json_only", "required_keys", "valid_json"],
        "span": (37, 40),
        "required": True,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": False,
        "order_group": "contract",
        "failure_targets": ["invalid_json", "missing_required_key", "missing_generated_code"],
    },
    {
        "local_id": "02",
        "name": "joi_grammar_core",
        "semantic_family": "Grammar",
        "semantic_role": "joi_core_syntax",
        "behavior_tags": ["joi_syntax", "allowed_constructs", "no_while"],
        "span": (85, 92),
        "required": True,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": False,
        "order_group": "grammar",
        "failure_targets": ["invalid_json", "missing_generated_code", "gt_mismatch"],
    },
    {
        "local_id": "03",
        "name": "receiver_tag_preservation",
        "semantic_family": "Receiver_Grounding",
        "semantic_role": "receiver_tag_preservation",
        "behavior_tags": ["receiver_tag", "selector_tag", "uppercase_tag"],
        "span": (45, 49),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "receiver",
        "failure_targets": ["gt_receiver_coverage", "receiver"],
    },
    {
        "local_id": "04",
        "name": "connected_device_scope",
        "semantic_family": "Receiver_Grounding",
        "semantic_role": "connected_device_scope",
        "behavior_tags": ["connected_devices", "selector_tags", "schema_fallback"],
        "span": (17, 36),
        "required": True,
        "mutation_allowed": ["strengthen", "compress", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "receiver",
        "failure_targets": ["gt_receiver_coverage", "unknown_service"],
    },
    {
        "local_id": "05",
        "name": "service_schema_authority",
        "semantic_family": "Service_Grounding",
        "semantic_role": "service_schema_authority",
        "behavior_tags": ["schema_authority", "service_schema", "canonical_name"],
        "span": (93, 3887),
        "required": True,
        "mutation_allowed": ["compress", "split", "merge"],
        "crossover_enabled": False,
        "order_group": "service",
        "failure_targets": ["unknown_service", "gt_service_coverage", "service_match"],
    },
    {
        "local_id": "06",
        "name": "canonical_service_name",
        "semantic_family": "Service_Grounding",
        "semantic_role": "canonical_service_name",
        "behavior_tags": ["canonical_service_name", "no_invented_service", "member_lowercase"],
        "span": (33, 36),
        "required": True,
        "mutation_allowed": ["strengthen", "compress", "merge"],
        "crossover_enabled": True,
        "order_group": "service",
        "failure_targets": ["unknown_service", "service_match"],
    },
    {
        "local_id": "07",
        "name": "value_vs_function",
        "semantic_family": "Service_Grounding",
        "semantic_role": "value_vs_function",
        "behavior_tags": ["function_service", "value_service", "sensor_action"],
        "span": (41, 44),
        "required": False,
        "mutation_allowed": ["strengthen", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "service",
        "failure_targets": ["gt_service_coverage", "unknown_service"],
    },
    {
        "local_id": "08",
        "name": "argument_type_and_order",
        "semantic_family": "Argument_Grounding",
        "semantic_role": "argument_type_and_order",
        "behavior_tags": ["argument_type", "argument_order", "bounds"],
        "span": (3912, 3928),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "argument",
        "failure_targets": ["arg_type", "numeric_grounding", "enum_grounding"],
    },
    {
        "local_id": "09",
        "name": "enum_grounding",
        "semantic_family": "Argument_Grounding",
        "semantic_role": "enum_grounding",
        "behavior_tags": ["enum_value", "allowed_values"],
        "span": (75, 82),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "argument",
        "failure_targets": ["enum_grounding", "unknown_service"],
    },
    {
        "local_id": "10",
        "name": "numeric_unit_conversion",
        "semantic_family": "Argument_Grounding",
        "semantic_role": "numeric_unit_conversion",
        "behavior_tags": ["numeric_value", "unit_conversion", "bounds"],
        "span": (50, 50),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "argument",
        "failure_targets": ["numeric_grounding"],
    },
    {
        "local_id": "11",
        "name": "cron_schedule",
        "semantic_family": "Temporal",
        "semantic_role": "cron_schedule",
        "behavior_tags": ["cron", "schedule", "wall_clock"],
        "span": (63, 65),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "temporal",
        "failure_targets": ["cron_mismatch", "numeric_grounding"],
    },
    {
        "local_id": "12",
        "name": "period_policy",
        "semantic_family": "Temporal",
        "semantic_role": "period_policy",
        "behavior_tags": ["period", "monitoring", "polling"],
        "span": (66, 68),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "merge"],
        "crossover_enabled": True,
        "order_group": "temporal",
        "failure_targets": ["period_mismatch", "loop_policy_error"],
    },
    {
        "local_id": "13",
        "name": "delay_and_wait",
        "semantic_family": "Temporal",
        "semantic_role": "delay_and_wait",
        "behavior_tags": ["delay", "wait_until", "one_shot_trigger"],
        "span": (3934, 3936),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "temporal",
        "failure_targets": ["cron_mismatch", "period_mismatch", "gt_mismatch"],
    },
    {
        "local_id": "14",
        "name": "loop_and_break_constraints",
        "semantic_family": "Loop",
        "semantic_role": "loop_constraints",
        "behavior_tags": ["loop_constraints", "break_policy", "no_unsupported_while"],
        "span": (3937, 3940),
        "required": False,
        "mutation_allowed": ["strengthen", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "temporal",
        "failure_targets": ["loop_policy_error", "period_mismatch"],
    },
    {
        "local_id": "15",
        "name": "event_trigger_skeleton",
        "semantic_family": "Control_Flow",
        "semantic_role": "event_trigger_skeleton",
        "behavior_tags": ["edge_trigger", "prev_curr", "triggered_state"],
        "span": (66, 67),
        "required": False,
        "mutation_allowed": ["strengthen", "split", "merge"],
        "crossover_enabled": True,
        "order_group": "control_flow",
        "failure_targets": ["gt_mismatch", "period_mismatch"],
    },
    {
        "local_id": "16",
        "name": "snapshot_recheck_pattern",
        "semantic_family": "Control_Flow",
        "semantic_role": "snapshot_recheck_pattern",
        "behavior_tags": ["snapshot", "recheck", "delay"],
        "span": (68, 68),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "control_flow",
        "failure_targets": ["gt_mismatch", "dataflow"],
    },
    {
        "local_id": "17",
        "name": "dataflow_read_bind_use",
        "semantic_family": "Dataflow",
        "semantic_role": "read_bind_use",
        "behavior_tags": ["read_bind_use", "variable_scope", "sensor_action"],
        "span": (3941, 3941),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "dataflow",
        "failure_targets": ["dataflow", "gt_service_coverage"],
    },
    {
        "local_id": "18",
        "name": "any_all_group_receiver",
        "semantic_family": "Receiver_Grounding",
        "semantic_role": "any_all_group_receiver",
        "behavior_tags": ["any_all", "group_receiver", "all_receiver"],
        "span": (69, 72),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "receiver",
        "failure_targets": ["gt_receiver_coverage"],
    },
    {
        "local_id": "19",
        "name": "owner_location_selector",
        "semantic_family": "Receiver_Grounding",
        "semantic_role": "owner_location_selector",
        "behavior_tags": ["owner", "location", "selector_tag"],
        "span": (3917, 3921),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "merge"],
        "crossover_enabled": True,
        "order_group": "receiver",
        "failure_targets": ["gt_receiver_coverage"],
    },
    {
        "local_id": "20",
        "name": "sensor_action_separation",
        "semantic_family": "Dataflow",
        "semantic_role": "sensor_action_separation",
        "behavior_tags": ["sensor_action", "actuator_target", "read_vs_act"],
        "span": (59, 62),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "dataflow",
        "failure_targets": ["dataflow", "gt_service_coverage"],
    },
    {
        "local_id": "21",
        "name": "minimality_no_extraneous",
        "semantic_family": "Minimality",
        "semantic_role": "no_extraneous_actions",
        "behavior_tags": ["minimality", "no_extraneous", "smallest_program"],
        "span": (3929, 3933),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "minimality",
        "failure_targets": ["extraneous", "gt_mismatch"],
    },
    {
        "local_id": "22",
        "name": "repair_contract",
        "semantic_family": "Repair",
        "semantic_role": "safe_fallback_contract",
        "behavior_tags": ["repair_contract", "empty_code_if_unsafe", "retry"],
        "span": (4016, 4018),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "repair",
        "failure_targets": ["missing_generated_code", "invalid_json"],
    },
    {
        "local_id": "23",
        "name": "det_self_check",
        "semantic_family": "DET_Self_Check",
        "semantic_role": "strict_det_self_check",
        "behavior_tags": ["self_check", "schema_match", "semantic_diff"],
        "span": (3946, 3955),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "self_check",
        "failure_targets": ["gt_mismatch", "unknown_service", "numeric_grounding", "enum_grounding"],
    },
    {
        "local_id": "24",
        "name": "korean_literal_preservation",
        "semantic_family": "Language",
        "semantic_role": "korean_literal_preservation",
        "behavior_tags": ["korean", "literal_preservation", "speaker_text"],
        "span": (73, 74),
        "required": False,
        "mutation_allowed": ["strengthen", "compress"],
        "crossover_enabled": True,
        "order_group": "language",
        "failure_targets": ["gt_mismatch", "semantic"],
    },
    {
        "local_id": "25",
        "name": "domain_special_cases",
        "semantic_family": "Domain_Cases",
        "semantic_role": "domain_special_cases",
        "behavior_tags": ["domain_cases", "canonical_actions", "dataset_cases"],
        "span": (75, 82),
        "required": False,
        "mutation_allowed": ["strengthen", "compress", "split"],
        "crossover_enabled": True,
        "order_group": "domain",
        "failure_targets": ["unknown_service", "gt_service_coverage", "enum_grounding"],
    },
]


G001_GROUPS: list[dict[str, Any]] = [
    {"local_id": "00", "name": "contract_core", "parents": ["00", "01"], "semantic_family": "Contract", "semantic_role": "contract_core"},
    {"local_id": "01", "name": "schema_authority_and_service_names", "parents": ["05", "06"], "semantic_family": "Service_Grounding", "semantic_role": "schema_authority_and_service_names"},
    {"local_id": "02", "name": "receiver_and_connected_scope", "parents": ["03", "04", "18", "19"], "semantic_family": "Receiver_Grounding", "semantic_role": "receiver_and_connected_scope"},
    {"local_id": "03", "name": "joi_syntax_and_output", "parents": ["02", "22"], "semantic_family": "Grammar", "semantic_role": "joi_syntax_and_output"},
    {"local_id": "04", "name": "temporal_cron_period", "parents": ["11", "12"], "semantic_family": "Temporal", "semantic_role": "temporal_cron_period"},
    {"local_id": "05", "name": "delay_wait_break", "parents": ["13", "14"], "semantic_family": "Temporal", "semantic_role": "delay_wait_break"},
    {"local_id": "06", "name": "event_and_snapshot_skeletons", "parents": ["15", "16"], "semantic_family": "Control_Flow", "semantic_role": "event_and_snapshot_skeletons"},
    {"local_id": "07", "name": "value_function_dataflow", "parents": ["07", "17", "20"], "semantic_family": "Dataflow", "semantic_role": "value_function_dataflow"},
    {"local_id": "08", "name": "numeric_enum_arguments", "parents": ["08", "09", "10"], "semantic_family": "Argument_Grounding", "semantic_role": "numeric_enum_arguments"},
    {"local_id": "09", "name": "minimality", "parents": ["21"], "semantic_family": "Minimality", "semantic_role": "minimality"},
    {"local_id": "10", "name": "det_self_check", "parents": ["23"], "semantic_family": "DET_Self_Check", "semantic_role": "det_self_check"},
    {"local_id": "11", "name": "language_preservation", "parents": ["24"], "semantic_family": "Language", "semantic_role": "language_preservation"},
    {"local_id": "12", "name": "domain_cases", "parents": ["25"], "semantic_family": "Domain_Cases", "semantic_role": "domain_cases"},
    {"local_id": "13", "name": "runtime_binding_rules", "parents": ["04", "05"], "semantic_family": "Service_Grounding", "semantic_role": "runtime_binding_rules"},
    {"local_id": "14", "name": "examples_basic", "parents": ["23"], "semantic_family": "Examples", "semantic_role": "examples_basic"},
    {"local_id": "15", "name": "examples_temporal", "parents": ["11", "12", "13"], "semantic_family": "Examples", "semantic_role": "examples_temporal"},
]


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def source_path(root: Path) -> Path:
    return root / "prompts" / "source" / "merged_system_prompt_260413.md"


def _slice_lines(lines: list[str], start: int, end: int) -> str:
    start = max(1, int(start))
    end = min(len(lines), int(end))
    if end < start:
        return ""
    return "".join(lines[start - 1 : end]).rstrip() + "\n"


def _atom_filename(spec: dict[str, Any], generation: int) -> str:
    return f"blocks/generated/g{generation:03d}/{spec['local_id']}_{spec['name']}.md"


def build_g000(root: Path) -> dict[str, Any]:
    source = source_path(root)
    lines = source.read_text(encoding="utf-8").splitlines(keepends=True)
    source_text = "".join(lines)
    atoms = []
    for order, spec in enumerate(SEED_ATOMS):
        start, end = spec["span"]
        rel_path = _atom_filename(spec, 0)
        text = _slice_lines(lines, start, end)
        if not text.strip():
            text = f"[Seed atom placeholder for {spec['name']}]\n"
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        atoms.append(
            {
                "local_id": spec["local_id"],
                "name": spec["name"],
                "semantic_family": spec["semantic_family"],
                "semantic_role": spec["semantic_role"],
                "behavior_tags": spec["behavior_tags"],
                "source_span": {"start_line": start, "end_line": end},
                "content_hash": sha256_text(text),
                "path": rel_path,
                "required": bool(spec["required"]),
                "default_active": True,
                "mutation_allowed": spec["mutation_allowed"],
                "crossover_enabled": bool(spec["crossover_enabled"]),
                "order_group": spec["order_group"],
                "render_order": order,
                "lineage": {"op": "seed", "parents": [], "source": "merged_system_prompt_260413.md"},
                "failure_targets": spec["failure_targets"],
            }
        )
    manifest = {
        "generation": 0,
        "block_space_id": "seg_000",
        "source_prompt": "prompts/source/merged_system_prompt_260413.md",
        "segmentation_method": "manual_seed_from_monolith_line_spans",
        "created_from": {
            "source_file": "merged_system_prompt_260413.md",
            "source_hash": sha256_text(source_text),
        },
        "local_ids_are_generation_specific": True,
        "seed_segmentation_only": True,
        "atoms": atoms,
    }
    write_json(root / "registries" / "generation_block_space_g000.json", manifest)
    write_json(root / "registries" / "block_space_seed.json", manifest)
    return manifest


def build_g001(root: Path, g000: dict[str, Any]) -> dict[str, Any]:
    atoms_by_id = {str(atom["local_id"]): atom for atom in g000["atoms"]}
    atoms = []
    for order, group in enumerate(G001_GROUPS):
        parent_atoms = [atoms_by_id[parent] for parent in group["parents"] if parent in atoms_by_id]
        parent_text = []
        tags: list[str] = []
        failures: list[str] = []
        for atom in parent_atoms:
            tags.extend(atom.get("behavior_tags", []))
            failures.extend(atom.get("failure_targets", []))
            parent_path = root / str(atom["path"])
            parent_text.append(parent_path.read_text(encoding="utf-8") if parent_path.exists() else "")
        text = (
            f"[Derived generation g001 atom: {group['name']}]\n"
            f"Lineage parents: {', '.join(group['parents'])}\n\n"
            + "\n\n".join(part.strip() for part in parent_text if part.strip())
            + "\n"
        )
        rel_path = f"blocks/generated/g001/{group['local_id']}_{group['name']}.md"
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        source_start = min((int(atom["source_span"]["start_line"]) for atom in parent_atoms if atom.get("source_span")), default=None)
        source_end = max((int(atom["source_span"]["end_line"]) for atom in parent_atoms if atom.get("source_span")), default=None)
        atoms.append(
            {
                "local_id": group["local_id"],
                "name": group["name"],
                "semantic_family": group["semantic_family"],
                "semantic_role": group["semantic_role"],
                "behavior_tags": list(dict.fromkeys(tags)),
                "source_span": {"start_line": source_start, "end_line": source_end},
                "content_hash": sha256_text(text),
                "path": rel_path,
                "required": order in {0, 1, 2, 3},
                "default_active": True,
                "mutation_allowed": ["strengthen", "compress", "rewrite", "split", "merge", "retire"],
                "crossover_enabled": order not in {0},
                "order_group": group["semantic_family"].lower(),
                "render_order": order,
                "lineage": {
                    "op": "merge" if len(group["parents"]) > 1 else "rewrite",
                    "parents": [f"g000_{parent}" for parent in group["parents"]],
                    "reason": "fixture demonstrating generation-local atom IDs and non-seed atom count",
                },
                "failure_targets": list(dict.fromkeys(failures)),
            }
        )
    source = source_path(root)
    manifest = {
        "generation": 1,
        "block_space_id": "seg_001",
        "source_prompt": "prompts/source/merged_system_prompt_260413.md",
        "segmentation_method": "deterministic_fixture_merge_seed_atoms",
        "created_from": {
            "source_file": "merged_system_prompt_260413.md",
            "source_hash": sha256_text(source.read_text(encoding="utf-8")),
            "parent_block_space_id": "seg_000",
        },
        "local_ids_are_generation_specific": True,
        "seed_segmentation_only": False,
        "atoms": atoms,
        "block_operations": [
            {"op": "merge_atoms", "parents": group["parents"], "child": f"g001_{group['local_id']}", "reason": "g001 fixture"}
            for group in G001_GROUPS
            if len(group["parents"]) > 1
        ],
    }
    write_json(root / "registries" / "generation_block_space_g001.json", manifest)
    return manifest


def write_genome_schemas(root: Path, g000: dict[str, Any], g001: dict[str, Any]) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "JOILang v16 dynamic atom genome",
        "type": "object",
        "required": ["genome_id", "generation", "block_space_id", "active_atoms"],
        "properties": {
            "genome_id": {"type": "string"},
            "generation": {"type": "integer"},
            "block_space_id": {"type": "string"},
            "active_atoms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Generation-local atom IDs valid only with block_space_id.",
            },
            "atom_params": {"type": "object"},
            "block_variants": {"type": "object"},
            "block_operations": {"type": "array"},
            "metadata": {"type": "object"},
        },
    }
    write_json(root / "genomes" / "genome_schema.json", schema)
    for manifest in (g000, g001):
        generation = int(manifest["generation"])
        genome = {
            "genome_id": f"v16_g{generation:03d}_base",
            "generation": generation,
            "block_space_id": manifest["block_space_id"],
            "active_atoms": [
                atom["local_id"]
                for atom in sorted(manifest["atoms"], key=lambda item: int(item["render_order"]))
                if atom.get("required") or atom.get("default_active", True)
            ],
            "atom_params": {},
            "block_variants": {},
            "block_operations": [],
            "metadata": {
                "schema": "v16_dynamic_genome.v1",
                "local_ids_are_generation_specific": True,
                "note": "Do not compare local IDs across generations without block_space_id and lineage.",
            },
        }
        write_json(root / "genomes" / f"base_genome_g{generation:03d}.json", genome)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v16 dynamic prompt atom block-space fixtures.")
    parser.add_argument("--base-path", default=str(package_root()))
    args = parser.parse_args()
    root = Path(args.base_path)
    g000 = build_g000(root)
    g001 = build_g001(root, g000)
    write_genome_schemas(root, g000, g001)
    print(
        json.dumps(
            {
                "base_path": str(root),
                "g000_atoms": len(g000["atoms"]),
                "g001_atoms": len(g001["atoms"]),
                "source_prompt": str(source_path(root)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
