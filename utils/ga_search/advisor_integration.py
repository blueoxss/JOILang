#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .advisor_evidence import FAILURE_TO_FAMILY, FAMILY_TO_INTENT, build_evidence_packet, write_evidence_packet
    from .advisor_modes import describe_advisor_mode, validate_advisor_mode
    from .artifacts import utc_now, write_json
except ImportError:
    from advisor_evidence import FAILURE_TO_FAMILY, FAMILY_TO_INTENT, build_evidence_packet, write_evidence_packet  # type: ignore
    from advisor_modes import describe_advisor_mode, validate_advisor_mode  # type: ignore
    from artifacts import utc_now, write_json  # type: ignore


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

FAMILY_RULES = {
    "Service_Mapping": "Before emitting a service member, verify it exists in the injected service schema and keep the canonical device-prefixed service name.",
    "Temporal_Rule": "Derive cron, period, delay, and numeric units before final output; use period only for repeated monitoring loops and convert units exactly.",
    "Skeleton": "Choose the JOILang skeleton by classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.",
    "DET_Helper": "Before final JSON, compare receiver coverage, service coverage, temporal structure, dataflow, numeric grounding, and enum grounding against the command intent.",
    "Receiver_Tag_Preservation": "Preserve every command-implied owner, location, group, sector, and selector tag in receiver expressions unless the command explicitly broadens the target.",
    "Owner_Device_Rule": "Keep condition subjects and action receivers tied to the command's device ownership and location constraints.",
    "Dataflow": "When reading a value for reporting or control, bind it once and use that variable downstream instead of inventing a separate value path.",
    "Enum_Grounding": "For enum services, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals in schema-required order.",
    "Minimality": "Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, wrappers, and unnecessary state changes.",
    "Output_Schema": "Return exactly one JSON object with required keys only; do not emit markdown, prose, comments, or code fences.",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _ensure_repo_importable() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)] if str(value).strip() else []


def _patch_priority(cluster: dict[str, Any], evidence_rows: list[str]) -> int:
    row_count = int(cluster.get("row_count") or len(evidence_rows) or 1)
    if row_count >= 5:
        return 90
    if row_count >= 2:
        return 80
    return 62


def _cloud_basis_for_rows(evidence_packet: dict[str, Any], row_ids: set[str]) -> dict[str, Any]:
    rows = []
    for row in evidence_packet.get("high_priority_rows", []):
        if str(row.get("row_no")) in row_ids and (row.get("cloud_scores") or row.get("cloud_reasoning")):
            rows.append(
                {
                    "row_no": row.get("row_no"),
                    "cloud_scores": row.get("cloud_scores", {}),
                    "cloud_reasoning_excerpt": str(row.get("cloud_reasoning") or "")[:500],
                }
            )
    return {"rows": rows, "cloud_is_auxiliary": True}


def build_prompt_patches_from_evidence(evidence_packet: dict[str, Any], *, dry_run: bool = True) -> dict[str, Any]:
    patches: list[dict[str, Any]] = []
    clusters = evidence_packet.get("failure_clusters") or []
    if not clusters and evidence_packet.get("high_priority_rows"):
        clusters = [
            {
                "cluster_id": "det_helper::general",
                "failure_types": ["gt_mismatch"],
                "rows": [str(row.get("row_no")) for row in evidence_packet.get("high_priority_rows", [])],
                "recommended_block_family": "DET_Helper",
                "mutation_intent": "skeleton_repair",
                "row_count": len(evidence_packet.get("high_priority_rows", [])),
            }
        ]

    for index, cluster in enumerate(clusters[:12], start=1):
        failure_types = _str_list(cluster.get("failure_types")) or ["gt_mismatch"]
        family = str(cluster.get("recommended_block_family") or FAILURE_TO_FAMILY.get(failure_types[0], "DET_Helper"))
        block_id = FAMILY_TO_DEFAULT_BLOCK.get(family, "06")
        row_ids = _str_list(cluster.get("rows"))
        priority = _patch_priority(cluster, row_ids)
        decision = "dynamic_core" if priority >= 80 and evidence_packet.get("advisor_mode") != "cloud" else "optional"
        patch_text = FAMILY_RULES.get(family, FAMILY_RULES["DET_Helper"])
        patches.append(
            {
                "patch_id": f"ga_{evidence_packet.get('advisor_mode', 'advisor')}_{index:03d}_{family.lower()}",
                "target_block_family": family,
                "target_block_id": block_id,
                "target_gene_id": f"{block_id}:{family}:{','.join(failure_types[:2])}",
                "operation": "append_micro_rule",
                "priority": priority,
                "patch_text": patch_text,
                "evidence_rows": row_ids,
                "evidence_failure_reasons": failure_types,
                "strict_det_basis": {
                    "primary_signal": evidence_packet.get("primary_signal"),
                    "top_failure_reasons": evidence_packet.get("global_summary", {}).get("top_failure_reasons", []),
                    "cluster_id": cluster.get("cluster_id"),
                },
                "cloud_judge_basis": _cloud_basis_for_rows(evidence_packet, set(row_ids)),
                "expected_effect": f"Reduce {', '.join(failure_types)} failures by targeting {family} behavior.",
                "risk": "medium" if decision == "dynamic_core" else "low",
                "token_cost": "low",
                "regression_risk": "medium" if priority >= 85 else "low",
                "validation_scope": "Rerun strict DET on evidence rows first, then full strict DET if improved.",
                "success_criteria": [
                    "strict DET failure count for evidence rows decreases",
                    "no new invalid JSON or schema contract failures",
                    "cloud reasoning remains auxiliary and is not used as official score",
                ],
                "core_optional_decision": decision,
                "dynamic_core": decision == "dynamic_core",
                "optional": decision == "optional",
                "suppress_or_do_not_change": False,
                "dry_run": dry_run,
                "mutation_intent": cluster.get("mutation_intent") or FAMILY_TO_INTENT.get(family, "diversity"),
            }
        )

    try:
        _ensure_repo_importable()
        from utils.prompt_advisor.schemas import make_minimal_patches_output

        output = make_minimal_patches_output(
            patches,
            source=f"ga_search_{evidence_packet.get('advisor_mode', 'advisor')}_{'dry_run' if dry_run else 'advisor'}",
            summary=evidence_packet.get("global_summary", {}),
        )
    except Exception:
        output = {
            "advisor_meta": {
                "created_at": utc_now(),
                "source": f"ga_search_{evidence_packet.get('advisor_mode', 'advisor')}",
                "schema_version": "prompt_advisor.v1",
                "dry_run": dry_run,
            },
            "compressed_feedback_summary": evidence_packet.get("global_summary", {}),
            "dynamic_criteria": {
                "primary_signal": evidence_packet.get("primary_signal"),
                "cloud_is_auxiliary": True,
                "micro_rule_policy": "minimal targeted mutations only",
            },
            "core_optional_decision": {
                "hard_core": ["Core_System", "Service_Mapping", "Output_Schema"],
                "dynamic_core": sorted({p["target_block_family"] for p in patches if p.get("dynamic_core")}),
                "optional": sorted({p["target_block_family"] for p in patches if p.get("optional")}),
                "suppress_or_do_not_change": [],
            },
            "prompt_patches": patches,
            "do_not_change": ["Do not edit final generation prompt files directly."],
            "iteration_audit": [],
            "validation_plan": {"primary": "strict DET rerun"},
            "final_decision": {"dry_run": dry_run, "ready_for_population": bool(patches)},
        }
    output.setdefault("advisor_meta", {})["dry_run"] = dry_run
    output.setdefault("advisor_meta", {})["advisor_mode"] = evidence_packet.get("advisor_mode")
    return output


def build_advisor_prompt_payload(evidence_packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "system_prompt": (
            "You are a feedback advisor for JOILang prompt optimization. "
            "You propose prompt mutations only and never generate JOILang code."
        ),
        "user_prompt": (
            "Treat strict DET as the primary signal. Use cloud judge reasoning only as auxiliary explanation. "
            "Return prompt_patches.json-compatible JSON with minimal targeted micro-rules."
        ),
        "evidence_summary": evidence_packet.get("global_summary", {}),
        "failure_clusters": evidence_packet.get("failure_clusters", [])[:12],
        "metadata": {
            "created_at": utc_now(),
            "advisor_mode": evidence_packet.get("advisor_mode"),
            "primary_signal": evidence_packet.get("primary_signal"),
            "cloud_is_auxiliary": True,
        },
    }


def _write_population_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "candidate_id",
        "mutation_intent",
        "source_patch_ids",
        "active_blocks",
        "target_block_families",
        "regression_risk",
        "estimated_token_cost",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
            writer.writerow(
                {
                    "candidate_id": record.get("candidate_id", ""),
                    "mutation_intent": record.get("mutation_intent", ""),
                    "source_patch_ids": json.dumps(record.get("source_patch_ids", []), ensure_ascii=False),
                    "active_blocks": json.dumps(metadata.get("active_blocks", []), ensure_ascii=False),
                    "target_block_families": json.dumps(metadata.get("target_block_families", []), ensure_ascii=False),
                    "regression_risk": metadata.get("regression_risk", ""),
                    "estimated_token_cost": metadata.get("estimated_token_cost", ""),
                }
            )


def _write_population_md(path: Path, manifest: dict[str, Any]) -> None:
    lines = ["# GA Search Advisor Mutation Population", ""]
    summary = manifest.get("summary", {})
    lines.append(f"- candidate_count: `{summary.get('candidate_count', 0)}`")
    lines.append(f"- mutation_intent_groups: `{summary.get('mutation_intent_groups', {})}`")
    lines.append("")
    lines.append("| candidate_id | intent | patches | risk |")
    lines.append("|---|---|---|---|")
    for record in manifest.get("candidates", []):
        metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
        lines.append(
            f"| `{record.get('candidate_id', '')}` | {record.get('mutation_intent', '')} | "
            f"{', '.join(record.get('source_patch_ids', []))} | {metadata.get('regression_risk', '')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_population_from_patches(
    prompt_patches: dict[str, Any],
    *,
    out_dir: str | Path,
    population_size: int = 12,
) -> dict[str, Any]:
    advisor_dir = Path(out_dir)
    try:
        _ensure_repo_importable()
        from utils.prompt_advisor.apply_prompt_patches import (
            build_population,
            fallback_base_genome,
            population_summary,
        )
        from utils.prompt_advisor.schemas import normalize_patches_output

        normalized = normalize_patches_output(prompt_patches, source="ga_search")
        population = build_population(fallback_base_genome(), normalized.get("prompt_patches", []), population_size)
        summary = population_summary(population)
    except Exception:
        normalized = prompt_patches
        patches = prompt_patches.get("prompt_patches", []) if isinstance(prompt_patches, dict) else []
        population = []
        for index, patch in enumerate(patches[:population_size]):
            candidate_id = f"cand_{index:03d}_{str(patch.get('target_block_family', 'patch')).lower()}"
            population.append(
                {
                    "candidate_id": candidate_id,
                    "source_patch_ids": [str(patch.get("patch_id", ""))],
                    "mutation_intent": str(patch.get("mutation_intent") or "diversity"),
                    "diversity_family": str(patch.get("target_block_family") or "DET_Helper"),
                    "genome": {
                        "id": candidate_id,
                        "blocks": ["01", "02", "03", "06"],
                        "params": {},
                        "block_params": {
                            str(patch.get("target_block_id") or "06").zfill(2): {
                                "micro_rules": [str(patch.get("patch_text") or "")]
                            }
                        },
                        "seed": index,
                    },
                    "metadata": {
                        "mutation_intent": str(patch.get("mutation_intent") or "diversity"),
                        "active_blocks": ["01", "02", "03", "06"],
                        "target_block_families": [str(patch.get("target_block_family") or "DET_Helper")],
                    },
                }
            )
        summary = {
            "candidate_count": len(population),
            "mutation_intent_groups": sorted({record.get("mutation_intent", "") for record in population}),
        }

    genomes_dir = advisor_dir / "genomes"
    genomes_dir.mkdir(parents=True, exist_ok=True)
    for record in population:
        genome_path = genomes_dir / f"{record['candidate_id']}.json"
        write_json(genome_path, record.get("genome", {}))
        record["genome_path"] = str(genome_path)
    manifest = {
        "metadata": {
            "created_at": utc_now(),
            "source": "ga_search_advisor_integration",
            "population_size_requested": population_size,
        },
        "summary": summary,
        "prompt_patches_meta": normalized.get("advisor_meta", {}) if isinstance(normalized, dict) else {},
        "candidates": population,
    }
    write_json(advisor_dir / "prompt_patches.normalized.json", normalized)
    write_json(advisor_dir / "mutation_population.json", manifest)
    _write_population_csv(advisor_dir / "mutation_population.csv", population)
    _write_population_md(advisor_dir / "mutation_population.md", manifest)
    return manifest


def population_to_candidate_records(
    population_manifest: dict[str, Any],
    *,
    search_mode: str,
    advisor_mode: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    records = []
    source = "dry_run_advisor_patch" if dry_run else "advisor_patch"
    for index, record in enumerate(population_manifest.get("candidates", [])):
        metadata = record.get("metadata", {}) if isinstance(record.get("metadata"), dict) else {}
        records.append(
            {
                "candidate_id": record.get("candidate_id") or f"candidate_{index:03d}",
                "source": source,
                "search_mode": search_mode,
                "base_prompt_ref": "rendered_base_prompt.md",
                "patch_refs": record.get("source_patch_ids", []),
                "rendered_candidate_prompt_path": None,
                "blocks": metadata.get("active_blocks") or record.get("genome", {}).get("blocks"),
                "metadata": {
                    "advisor_mode": advisor_mode,
                    "mutation_intent": record.get("mutation_intent", ""),
                    "evidence_rows": [],
                    "genome_path": record.get("genome_path", ""),
                    "target_block_families": metadata.get("target_block_families", []),
                    "regression_risk": metadata.get("regression_risk", ""),
                    "estimated_token_cost": metadata.get("estimated_token_cost", ""),
                },
            }
        )
    return records


def run_advisor_for_ga_search(
    *,
    advisor_mode: str,
    advisor_dir: str | Path,
    search_mode: str,
    strict_results_dir: str | None = None,
    local_det_report: str | None = None,
    cloud_judge_csv: str | None = None,
    advisor_rich_feedback: str | None = None,
    prompt_patches: str | None = None,
    top_k: int = 20,
    dry_run: bool = False,
    population_size: int = 12,
) -> dict[str, Any]:
    mode = validate_advisor_mode(advisor_mode)
    root = Path(advisor_dir)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "advisor_mode.json", describe_advisor_mode(mode))

    evidence = build_evidence_packet(
        advisor_mode=mode,
        strict_results_dir=strict_results_dir,
        local_det_report=local_det_report,
        cloud_judge_csv=cloud_judge_csv,
        advisor_rich_feedback=advisor_rich_feedback,
        top_k=top_k,
    )
    write_evidence_packet(evidence, root / "advisor_evidence_packet.json")
    write_json(root / "advisor_prompt.json", build_advisor_prompt_payload(evidence))

    if prompt_patches:
        patch_path = Path(prompt_patches)
        if not patch_path.exists():
            raise FileNotFoundError(f"prompt patches file not found: {patch_path}")
        patches_output = json.loads(patch_path.read_text(encoding="utf-8"))
    else:
        patches_output = build_prompt_patches_from_evidence(evidence, dry_run=dry_run)
    write_json(root / "prompt_patches.json", patches_output)
    population_manifest = build_population_from_patches(
        patches_output,
        out_dir=root,
        population_size=population_size,
    )
    candidate_records = population_to_candidate_records(
        population_manifest,
        search_mode=search_mode,
        advisor_mode=mode,
        dry_run=dry_run,
    )
    return {
        "advisor_mode": mode,
        "advisor_dir": str(root),
        "dry_run": dry_run,
        "evidence_packet": evidence,
        "prompt_patches_path": str(root / "prompt_patches.json"),
        "mutation_population_path": str(root / "mutation_population.json"),
        "candidate_records": candidate_records,
        "summary": {
            "evidence_rows": len(evidence.get("high_priority_rows", [])),
            "failure_clusters": len(evidence.get("failure_clusters", [])),
            "prompt_patches": len(patches_output.get("prompt_patches", [])) if isinstance(patches_output, dict) else 0,
            "population_candidates": len(population_manifest.get("candidates", [])),
            "primary_signal": evidence.get("primary_signal"),
            "cloud_is_auxiliary": True,
        },
    }
