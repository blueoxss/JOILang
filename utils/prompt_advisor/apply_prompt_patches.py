#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from .schemas import (
        FAMILY_TO_DEFAULT_BLOCK,
        RISK_ORDER,
        TOKEN_COST_ORDER,
        deep_copy_jsonable,
        normalize_patches_output,
        slugify,
        utc_now,
    )
except ImportError:
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from schemas import (
        FAMILY_TO_DEFAULT_BLOCK,
        RISK_ORDER,
        TOKEN_COST_ORDER,
        deep_copy_jsonable,
        normalize_patches_output,
        slugify,
        utc_now,
    )


CORE_BLOCKS = ("01", "02")
OPTIONAL_BLOCKS = ("03", "05", "06")
BLOCK_ORDER = ("01", "02", "03", "05", "06")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply prompt patches into a diverse candidate genome population.")
    parser.add_argument("--prompt-patches", required=True)
    parser.add_argument("--base-genome", default="")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--population-size", type=int, default=12)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def fallback_base_genome() -> dict[str, Any]:
    return {
        "blocks": ["01", "02", "03", "06"],
        "params": {},
        "block_params": {},
        "seed": 0,
    }


def load_base_genome(path_text: str) -> tuple[dict[str, Any], str]:
    if path_text:
        path = Path(path_text)
        if path.exists():
            genome = read_json(path)
            return ensure_genome_shape(genome), str(path)
    return fallback_base_genome(), "fallback"


def normalize_active_blocks(blocks: list[str] | tuple[str, ...] | None) -> list[str]:
    requested = [str(block).zfill(2) for block in (blocks or [])]
    active = list(CORE_BLOCKS)
    for block_id in BLOCK_ORDER:
        if block_id in CORE_BLOCKS:
            continue
        if block_id in requested and block_id not in active:
            active.append(block_id)
    return active


def ensure_genome_shape(genome: dict[str, Any]) -> dict[str, Any]:
    normalized = deep_copy_jsonable(genome if isinstance(genome, dict) else {})
    normalized["blocks"] = normalize_active_blocks(normalized.get("blocks") or ["01", "02", "03", "06"])
    normalized.setdefault("params", {})
    normalized.setdefault("block_params", {})
    normalized.setdefault("seed", 0)
    return normalized


def patch_sort_key(patch: dict[str, Any]) -> tuple[int, int, int]:
    return (
        -int(patch.get("priority") or 0),
        RISK_ORDER.get(str(patch.get("regression_risk") or "medium"), 1),
        TOKEN_COST_ORDER.get(str(patch.get("token_cost") or "medium"), 1),
    )


def add_block(blocks: list[str], block_id: str) -> list[str]:
    block_id = str(block_id).zfill(2)
    if block_id in OPTIONAL_BLOCKS and block_id not in blocks:
        blocks.append(block_id)
    return normalize_active_blocks(blocks)


def remove_optional_block(blocks: list[str], block_id: str) -> list[str]:
    block_id = str(block_id).zfill(2)
    if block_id in CORE_BLOCKS:
        return normalize_active_blocks(blocks)
    return normalize_active_blocks([block for block in blocks if block != block_id])


def append_micro_rule(genome: dict[str, Any], block_id: str, rule: str) -> None:
    block_id = str(block_id).zfill(2)
    genome["blocks"] = add_block(list(genome.get("blocks") or []), block_id)
    params = genome.setdefault("block_params", {}).setdefault(block_id, {})
    rules = list(params.get("micro_rules") or [])
    if rule and rule not in rules:
        rules.append(rule)
    params["micro_rules"] = rules


def apply_patch_to_genome(genome: dict[str, Any], patch: dict[str, Any], *, allow_repair_block: bool) -> bool:
    operation = str(patch.get("operation") or "append_micro_rule")
    block_id = str(patch.get("target_block_id") or FAMILY_TO_DEFAULT_BLOCK.get(patch.get("target_block_family"), "06")).zfill(2)
    if block_id == "05" and not allow_repair_block:
        return False
    if operation == "activate_optional_block":
        genome["blocks"] = add_block(list(genome.get("blocks") or []), block_id)
        return True
    if operation == "deactivate_optional_block":
        genome["blocks"] = remove_optional_block(list(genome.get("blocks") or []), block_id)
        return True
    if operation in {"suppress_gene", "delete_conflicting_rule"}:
        genome.setdefault("advisor_metadata", {}).setdefault("suppressed_patch_ids", []).append(patch.get("patch_id"))
        return True
    if operation in {"promote_gene_to_dynamic_core", "demote_gene_to_optional"}:
        genome["blocks"] = add_block(list(genome.get("blocks") or []), block_id)
    append_micro_rule(genome, block_id, str(patch.get("patch_text") or ""))
    return True


def aggregate_level(patches: list[dict[str, Any]], field: str) -> str:
    order = RISK_ORDER if field in {"risk", "regression_risk"} else TOKEN_COST_ORDER
    reverse = {v: k for k, v in order.items()}
    max_value = max((order.get(str(patch.get(field) or "medium"), 1) for patch in patches), default=1)
    return reverse.get(max_value, "medium")


def summarize_expected_effect(patches: list[dict[str, Any]]) -> str:
    effects = [str(patch.get("expected_effect") or "").strip() for patch in patches if str(patch.get("expected_effect") or "").strip()]
    return " | ".join(effects[:3]) if effects else "Evaluate prompt micro-rule mutation impact."


def recommended_scope(patches: list[dict[str, Any]]) -> str:
    scopes = [str(patch.get("validation_scope") or "").strip() for patch in patches if str(patch.get("validation_scope") or "").strip()]
    return scopes[0] if scopes else "Rerun strict DET on evidence rows, then full benchmark if improved."


def make_candidate(
    *,
    index: int,
    base_genome: dict[str, Any],
    patches: list[dict[str, Any]],
    mutation_intent: str,
    diversity_family: str,
    allow_repair_block: bool = False,
    low_confidence: bool = False,
) -> dict[str, Any] | None:
    if not patches:
        return None
    genome = ensure_genome_shape(copy.deepcopy(base_genome))
    applied: list[dict[str, Any]] = []
    for patch in patches:
        if apply_patch_to_genome(genome, patch, allow_repair_block=allow_repair_block):
            applied.append(patch)
    if not applied:
        return None
    patch_ids = [str(patch.get("patch_id")) for patch in applied]
    families = sorted({str(patch.get("target_block_family")) for patch in applied})
    dynamic_core_families = sorted({str(patch.get("target_block_family")) for patch in applied if patch.get("dynamic_core")})
    optional_families = sorted({str(patch.get("target_block_family")) for patch in applied if patch.get("optional")})
    suppressed_families = sorted({str(patch.get("target_block_family")) for patch in applied if patch.get("suppress_or_do_not_change")})
    candidate_id = f"cand_{index:03d}_{slugify(diversity_family or mutation_intent)}"
    micro_rule_count = sum(len((params or {}).get("micro_rules") or []) for params in (genome.get("block_params") or {}).values())
    metadata = {
        "candidate_id": candidate_id,
        "mutation_intent": mutation_intent,
        "source_patch_ids": patch_ids,
        "active_blocks": normalize_active_blocks(genome.get("blocks") or []),
        "dynamic_core_families": dynamic_core_families,
        "optional_families": optional_families,
        "suppressed_families": suppressed_families,
        "target_block_families": families,
        "micro_rule_count": micro_rule_count,
        "estimated_token_cost": aggregate_level(applied, "token_cost"),
        "expected_effect": summarize_expected_effect(applied),
        "regression_risk": aggregate_level(applied, "regression_risk"),
        "recommended_rerun_scope": recommended_scope(applied),
        "low_confidence": low_confidence,
    }
    genome["id"] = candidate_id
    genome["blocks"] = metadata["active_blocks"]
    genome.setdefault("advisor_metadata", {}).update(metadata)
    return {
        "candidate_id": candidate_id,
        "source_patch_ids": patch_ids,
        "mutation_intent": mutation_intent,
        "diversity_family": diversity_family,
        "genome": genome,
        "expected_effect": metadata["expected_effect"],
        "risk": aggregate_level(applied, "risk"),
        "token_cost": metadata["estimated_token_cost"],
        "validation_scope": metadata["recommended_rerun_scope"],
        "metadata": metadata,
    }


def group_by_family(patches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for patch in patches:
        grouped[str(patch.get("target_block_family") or "DET_Helper")].append(patch)
    for family in list(grouped):
        grouped[family] = sorted(grouped[family], key=patch_sort_key)
    return grouped


def intent_for_family(family: str) -> str:
    if family in {"Service_Mapping", "Canonical_Service_Name", "Enum_Grounding"}:
        return "service_repair"
    if family in {"Temporal_Rule", "Cron_Period_Planning"}:
        return "temporal_repair"
    if family in {"Receiver_Tag_Preservation", "Owner_Device_Rule"}:
        return "receiver_repair"
    if family in {"Skeleton", "DET_Helper", "Event_Trigger_Skeleton"}:
        return "skeleton_repair"
    if family == "Dataflow":
        return "dataflow_repair"
    if family in {"Minimality", "Output_Schema"}:
        return "minimality_repair"
    if family == "Repair_Clause":
        return "repair_candidate"
    return "diversity"


def unique_patch_signature(patches: list[dict[str, Any]]) -> tuple[str, ...]:
    return tuple(sorted(str(patch.get("patch_id")) for patch in patches))


def add_candidate(
    records: list[dict[str, Any]],
    seen: set[tuple[str, ...]],
    *,
    base_genome: dict[str, Any],
    patches: list[dict[str, Any]],
    mutation_intent: str,
    diversity_family: str,
    allow_repair_block: bool = False,
    low_confidence: bool = False,
    population_size: int,
) -> None:
    if len(records) >= population_size:
        return
    signature = unique_patch_signature(patches)
    if not signature or signature in seen:
        return
    candidate = make_candidate(
        index=len(records),
        base_genome=base_genome,
        patches=patches,
        mutation_intent=mutation_intent,
        diversity_family=diversity_family,
        allow_repair_block=allow_repair_block,
        low_confidence=low_confidence,
    )
    if candidate:
        records.append(candidate)
        seen.add(signature)


def build_population(base_genome: dict[str, Any], patches: list[dict[str, Any]], population_size: int) -> list[dict[str, Any]]:
    population_size = max(1, population_size)
    valid = [patch for patch in patches if not patch.get("suppress_or_do_not_change")]
    valid = sorted(valid, key=patch_sort_key)
    high_priority = [patch for patch in valid if int(patch.get("priority") or 0) >= 70]
    low_risk = [
        patch
        for patch in valid
        if patch.get("token_cost") == "low" and patch.get("regression_risk") == "low"
    ]
    high_risk = [patch for patch in valid if patch.get("regression_risk") == "high"]
    grouped = group_by_family(valid)
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()

    for patch in high_priority or valid:
        add_candidate(
            records,
            seen,
            base_genome=base_genome,
            patches=[patch],
            mutation_intent=intent_for_family(str(patch.get("target_block_family"))),
            diversity_family=str(patch.get("target_block_family")),
            allow_repair_block=patch.get("target_block_id") == "05",
            low_confidence=len(patch.get("evidence_rows") or []) <= 1,
            population_size=population_size,
        )

    for family, family_patches in grouped.items():
        add_candidate(
            records,
            seen,
            base_genome=base_genome,
            patches=family_patches[:3],
            mutation_intent=intent_for_family(family),
            diversity_family=f"{family}_cluster",
            allow_repair_block=family == "Repair_Clause",
            low_confidence=all(len(patch.get("evidence_rows") or []) <= 1 for patch in family_patches[:3]),
            population_size=population_size,
        )

    conservative = low_risk[:3] or [patch for patch in valid if patch.get("regression_risk") != "high" and patch.get("token_cost") != "high"][:3]
    add_candidate(
        records,
        seen,
        base_genome=base_genome,
        patches=conservative,
        mutation_intent="conservative",
        diversity_family="low_cost_low_risk",
        population_size=population_size,
    )

    aggressive = high_priority[:6] or valid[:6]
    add_candidate(
        records,
        seen,
        base_genome=base_genome,
        patches=aggressive,
        mutation_intent="aggressive",
        diversity_family="high_priority_bundle",
        allow_repair_block=True,
        population_size=population_size,
    )

    families = list(grouped.keys())
    balanced: list[dict[str, Any]] = []
    for family in families:
        if grouped[family]:
            candidate_patch = grouped[family][0]
            if candidate_patch.get("regression_risk") != "high" and candidate_patch.get("token_cost") != "high":
                balanced.append(candidate_patch)
        if len(balanced) >= 4:
            break
    add_candidate(
        records,
        seen,
        base_genome=base_genome,
        patches=balanced,
        mutation_intent="balanced",
        diversity_family="cross_cluster_balanced",
        population_size=population_size,
    )

    for offset in range(max(0, population_size - len(records))):
        combo = valid[offset::2][:4] if offset % 2 else valid[offset::3][:4]
        if not combo and valid:
            combo = [valid[offset % len(valid)]]
        add_candidate(
            records,
            seen,
            base_genome=base_genome,
            patches=combo,
            mutation_intent="diversity",
            diversity_family=f"staggered_{offset}",
            allow_repair_block=True,
            low_confidence=any(len(patch.get("evidence_rows") or []) <= 1 for patch in combo),
            population_size=population_size,
        )

    if high_risk and len(records) < population_size:
        add_candidate(
            records,
            seen,
            base_genome=base_genome,
            patches=high_risk[:2],
            mutation_intent="aggressive",
            diversity_family="high_risk_isolated",
            allow_repair_block=True,
            population_size=population_size,
        )

    return records[:population_size]


def population_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    intent_groups = sorted({record["mutation_intent"] for record in records})
    family_combos = sorted({"+".join(record["metadata"].get("target_block_families") or []) for record in records})
    all_patch_sets = {tuple(record["source_patch_ids"]) for record in records}
    return {
        "candidate_count": len(records),
        "mutation_intent_groups": intent_groups,
        "target_block_family_combinations": family_combos,
        "has_conservative": any(record["mutation_intent"] == "conservative" for record in records),
        "has_aggressive": any(record["mutation_intent"] == "aggressive" for record in records),
        "all_candidates_same_patch_set": len(all_patch_sets) <= 1 if records else False,
    }


def write_population_md(path: Path, manifest: dict[str, Any]) -> None:
    lines = ["# Prompt Advisor Mutation Population", ""]
    summary = manifest.get("summary", {})
    lines.append("## Summary")
    lines.append(f"- candidate genomes: {summary.get('candidate_count')}")
    lines.append(f"- mutation intent groups: {', '.join(summary.get('mutation_intent_groups') or [])}")
    lines.append(f"- conservative candidate: {summary.get('has_conservative')}")
    lines.append(f"- aggressive candidate: {summary.get('has_aggressive')}")
    lines.append("")
    lines.append("## Candidates")
    for record in manifest.get("candidates", []):
        meta = record.get("metadata", {})
        lines.append(f"### {record.get('candidate_id')}")
        lines.append(f"- intent: {record.get('mutation_intent')}")
        lines.append(f"- source patches: {', '.join(record.get('source_patch_ids') or [])}")
        lines.append(f"- active blocks: {', '.join(meta.get('active_blocks') or [])}")
        lines.append(f"- families: {', '.join(meta.get('target_block_families') or [])}")
        lines.append(f"- token cost: {record.get('token_cost')}")
        lines.append(f"- regression risk: {meta.get('regression_risk')}")
        lines.append(f"- validation: {record.get('validation_scope')}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    patches_path = Path(args.prompt_patches)
    out_dir = Path(args.out_dir)
    patches_output = normalize_patches_output(read_json(patches_path), source="apply_prompt_patches")
    base_genome, base_source = load_base_genome(args.base_genome)
    population = build_population(base_genome, patches_output.get("prompt_patches", []), args.population_size)

    out_dir.mkdir(parents=True, exist_ok=True)
    genomes_dir = out_dir / "genomes"
    genomes_dir.mkdir(parents=True, exist_ok=True)
    for record in population:
        genome_path = genomes_dir / f"{record['candidate_id']}.json"
        write_json(genome_path, record["genome"])
        record["genome_path"] = str(genome_path)

    manifest = {
        "metadata": {
            "created_at": utc_now(),
            "prompt_patches": str(patches_path),
            "base_genome": base_source,
            "population_size_requested": args.population_size,
        },
        "summary": population_summary(population),
        "prompt_patches_meta": patches_output.get("advisor_meta", {}),
        "candidates": population,
    }
    write_json(out_dir / "prompt_patches.normalized.json", patches_output)
    write_json(out_dir / "mutation_population.json", manifest)
    write_csv(
        out_dir / "mutation_population.csv",
        [
            {
                "candidate_id": record["candidate_id"],
                "mutation_intent": record["mutation_intent"],
                "diversity_family": record["diversity_family"],
                "source_patch_ids": record["source_patch_ids"],
                "active_blocks": record["metadata"].get("active_blocks"),
                "target_block_families": record["metadata"].get("target_block_families"),
                "micro_rule_count": record["metadata"].get("micro_rule_count"),
                "estimated_token_cost": record["metadata"].get("estimated_token_cost"),
                "regression_risk": record["metadata"].get("regression_risk"),
                "genome_path": record.get("genome_path"),
            }
            for record in population
        ],
        [
            "candidate_id",
            "mutation_intent",
            "diversity_family",
            "source_patch_ids",
            "active_blocks",
            "target_block_families",
            "micro_rule_count",
            "estimated_token_cost",
            "regression_risk",
            "genome_path",
        ],
    )
    write_population_md(out_dir / "mutation_population.md", manifest)
    print(f"Wrote population to {out_dir}")
    print(
        "Population summary: "
        f"candidates={manifest['summary']['candidate_count']}, "
        f"intents={len(manifest['summary']['mutation_intent_groups'])}, "
        f"family_combos={len(manifest['summary']['target_block_family_combinations'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

