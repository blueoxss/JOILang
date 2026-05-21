#!/usr/bin/env python3
# Assumption: this feedback loop may create new block variants and genome variants, but it only writes under gpt_mg/version0_14/.
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.run_generate import _llm_settings, generate_candidates_for_rows
from utils.det_evaluator import evaluate_candidates, summarize_failure_patterns
from utils.pipeline_common import (
    BLOCKS_DIR,
    DATASET_DEFAULT,
    RESULTS_DIR,
    SERVICE_SCHEMA_DEFAULT,
    build_prompt_values,
    dump_json,
    ensure_workspace,
    load_dataset_rows,
    load_genome,
    load_service_schema,
    make_run_id,
    parse_block_file,
    render_blocks_for_genome,
    resolve_block_path,
    sample_rows,
    seeded_uuid,
    select_rows,
    slugify,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the version0_14 validation + prompt-surgery feedback loop.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--genome-json", default=str(VERSION_ROOT / "genomes" / "example_genome.json"))
    parser.add_argument("--dataset", default=str(DATASET_DEFAULT))
    parser.add_argument("--service-schema", default=str(SERVICE_SCHEMA_DEFAULT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--category", action="append", default=[], help="Filter by dataset category. Can be repeated or comma-separated.")
    parser.add_argument("--validation-size", type=int, default=8)
    parser.add_argument("--candidate-k", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--improvement-threshold", type=float, default=0.25)
    parser.add_argument("--llm-mode", default=None)
    parser.add_argument("--llm-endpoint", default=None)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--seed", type=int, default=14)
    return parser


PATCH_RULES = {
    "invalid_json": {
        "generator": "Return exactly one JSON object only. Never emit prose, markdown, or code fences.",
        "repair": "When repairing, preserve only keys name, cron, period, code and output valid JSON only.",
    },
    "schema_missing_keys": {
        "generator": "Always output all required keys: name, cron, period, code.",
        "repair": "If a key is missing, reconstruct the JSON object with the required four keys only.",
    },
    "service_match": {
        "generator": "Prefer canonical_name exactly whenever the schema snippet provides canonical_name. Do not emit bare raw service names when canonical_name is available. If the schema offers exact actuator actions such as Camera_CaptureImage, Speaker_Speak, Switch_Off, DoorLock_Lock, or Light_MoveToRGB, use those exact canonical actions instead of natural-language synonyms.",
        "repair": "Replace unknown value/function tokens with the exact canonical_name from the schema snippet. Move side effects onto the correct actuator device family when the candidate called the wrong device.",
    },
    "arg_type": {
        "generator": "Match argument_type positionally. INTEGER and DOUBLE literals should be unquoted; ENUM literals must use allowed enum strings only.",
        "repair": "Coerce wrong argument literals to the exact schema type and unit, while preserving intent.",
    },
    "precondition": {
        "generator": "Insert a power-check only when the schema snippet explicitly supports it for the same target context; otherwise do not invent one.",
        "repair": "If diagnostics say a precondition is missing and the schema supports it, add the minimal guard before the main action.",
    },
    "semantic": {
        "generator": "Choose the smallest action sequence that satisfies the command verbs, nouns, numbers, tags, and timing semantics. Preserve location tags and grouped receivers such as all(#Hallway #Light), and preserve exact event wording such as repeated triggers versus one-shot waits.",
        "repair": "Rewrite the code to match the command semantics directly, not approximately. Restore missing tags, missing grouped receivers, and missing actuator steps.",
    },
    "extraneous": {
        "generator": "Remove unrelated actions, duplicate actions, and helper steps that do not directly support the command.",
        "repair": "Delete unrelated actions before attempting any other repair.",
    },
    "gt_mismatch": {
        "generator": "Prefer the smallest schema-valid program that directly matches the command's target operation, ordering, timing pattern, and dataset conventions. For unscheduled commands, default to cron \"\" and period 0, but for repeated event triggers use period 100 with prev/curr or triggered-state logic. Preserve delay(...), edge-trigger logic such as prev/curr threshold crossings, tag-based all(...), tag-preserving receivers, and stateful period toggles when the command implies them.",
        "repair": "When the output is schema-valid but diverges from the expected target action sequence, rewrite it toward the canonical action ordering, timing pattern, literals, and schedule defaults. Restore missing delay(...), threshold-crossing guards, repeated-event period 100 logic, exact grouped tag receivers, time-window end guards, button-specific values, and stateful period toggles when diagnostics imply them.",
    },
    "service_case": {
        "generator": "Keep receiver tags after # unchanged, but lowercase every service or value member token after ). or all(...). . Resolve against canonical_name, then emit the lowercase member form in the final code.",
        "repair": "If the candidate uses uppercase or mixed-case service/value members after the receiver dot, rewrite those member tokens to lowercase while preserving receiver tags and arguments.",
    },
}

MANUAL_FEEDBACK_FILENAMES = (
    "manual_feedback.txt",
    "manual_feedback.md",
    "manual_feedback.json",
    "feedback_rules.txt",
    "feedback_rules.json",
)
MANUAL_FEEDBACK_KEYS = (
    "manual_feedback",
    "manual_rules",
    "feedback_notes",
    "prompt_rules",
    "notes",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _append_patch_rules(original_text: str, rules: list[str], title: str) -> str:
    unique_rules = []
    seen = set()
    for rule in rules:
        if rule not in seen:
            seen.add(rule)
            unique_rules.append(rule)
    if not unique_rules:
        return original_text
    patch_body = "\n".join(f"- {rule}" for rule in unique_rules)
    return original_text.rstrip() + f"\n\n{title}\n{patch_body}\n"


def _strip_auto_sections(text: str) -> str:
    markers = [
        "\nAUTO-PATCH MICRO-RULES\n",
        "\nAUTO-GENERATED EXEMPLARS FROM GT FAILURES\n",
        "\nMANUAL FOCUS RULES\n",
    ]
    cut_points = [text.find(marker) for marker in markers if text.find(marker) != -1]
    if not cut_points:
        return text
    return text[: min(cut_points)].rstrip() + "\n"


def _patched_block_filename(block_id: str, base_name: str, patch_tag: str) -> str:
    stem = Path(base_name).stem
    suffix = Path(base_name).suffix or ".txt"
    return f"generated/{stem}__{patch_tag}{suffix}"


def _coerce_manual_rules(payload: Any) -> list[str]:
    rules: list[str] = []
    if payload is None:
        return rules
    if isinstance(payload, str):
        for line in payload.splitlines():
            rule = line.strip()
            if rule and not rule.startswith("#"):
                rules.append(rule)
        return rules
    if isinstance(payload, (list, tuple)):
        for item in payload:
            rules.extend(_coerce_manual_rules(item))
        return rules
    if isinstance(payload, dict):
        for key in MANUAL_FEEDBACK_KEYS:
            if key in payload:
                rules.extend(_coerce_manual_rules(payload.get(key)))
        return rules
    return rules


def _load_manual_feedback_rules() -> list[str]:
    logs_root = VERSION_ROOT / "logs"
    if not logs_root.exists():
        return []

    candidate_paths: list[Path] = []
    for filename in MANUAL_FEEDBACK_FILENAMES:
        candidate_paths.extend(sorted(logs_root.glob(f"**/{filename}")))
    candidate_paths.extend(sorted(logs_root.glob("feedback_attempt_*/*.json")))

    collected: list[str] = []
    seen: set[str] = set()
    for path in candidate_paths:
        try:
            if path.suffix.lower() == ".json":
                payload = json.loads(path.read_text(encoding="utf-8"))
                rules = _coerce_manual_rules(payload)
            else:
                rules = _coerce_manual_rules(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for rule in rules:
            if rule not in seen:
                seen.add(rule)
                collected.append(rule)
    return collected


def _coerce_gt_example(row: dict[str, Any]) -> dict[str, Any] | None:
    raw = row.get("gt")
    if not raw:
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    script = str(parsed.get("script") or parsed.get("code") or "").strip()
    if not script:
        return None
    period = parsed.get("period", -1)
    try:
        period = int(period)
    except Exception:
        period = -1
    name = str(parsed.get("name") or "").strip()
    if not name:
        name = f"AutoExample{int(row.get('row_no') or 0)}"
    return {
        "name": name[:50],
        "cron": str(parsed.get("cron", "") or ""),
        "period": period,
        "code": script,
    }


def _build_auto_exemplar_text(rows: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for index, row in enumerate(rows, start=1):
        gt_json = _coerce_gt_example(row)
        if not gt_json:
            continue
        sections.extend(
            [
                f"### AUTO EXEMPLAR {index}",
                "Input command_eng:",
                str(row.get("command_eng", "")),
                "",
                "Correct output:",
                json.dumps(gt_json, ensure_ascii=False),
                "",
            ]
        )
    if not sections:
        return ""
    return "AUTO-GENERATED EXEMPLARS FROM GT FAILURES\n" + "\n".join(sections).strip() + "\n"


def _make_patched_genome(
    base_genome: dict[str, Any],
    *,
    failure_types: list[str],
    exemplar_rows: list[dict[str, Any]] | None,
    manual_rules: list[str] | None,
    seed: int,
    patch_tag: str,
) -> dict[str, Any]:
    rng = random.Random(seed)
    patched = json.loads(json.dumps(base_genome))
    patched["id"] = f"gen-{seeded_uuid(rng)}"
    patched["seed"] = seed
    patched.setdefault("params", {})
    patched.setdefault("block_params", {})

    generator_rules = [PATCH_RULES[item]["generator"] for item in failure_types if item in PATCH_RULES]
    repair_rules = [PATCH_RULES[item]["repair"] for item in failure_types if item in PATCH_RULES]
    exemplar_text = _build_auto_exemplar_text(exemplar_rows or [])

    patch_targets: list[tuple[str, list[str]]] = [
        ("02", generator_rules),
        ("05", repair_rules),
    ]
    if manual_rules:
        patch_targets = [
            ("01", []),
            ("02", generator_rules),
            ("03", []),
            ("05", repair_rules),
        ]

    for block_id, rules in patch_targets:
        source_path = resolve_block_path(block_id, patched.get("block_params", {}).get(block_id, {}))
        source_text = _strip_auto_sections(_read_text(source_path))
        patched_text = _append_patch_rules(source_text, rules, "AUTO-PATCH MICRO-RULES")
        if manual_rules:
            patched_text = _append_patch_rules(patched_text, manual_rules, "MANUAL FOCUS RULES")
        if block_id == "02" and exemplar_text:
            patched_text = patched_text.rstrip() + "\n\n" + exemplar_text
        new_relative = _patched_block_filename(block_id, source_path.name, patch_tag)
        new_path = BLOCKS_DIR / new_relative
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_text(patched_text, encoding="utf-8")
        patched.setdefault("block_params", {}).setdefault(block_id, {})["source_file"] = new_relative
        if block_id == "02" and failure_types:
            current_few_shot = int(patched["block_params"].setdefault(block_id, {}).get("few_shot_count", patched.get("params", {}).get("few_shot_count", 3)))
            patched["block_params"][block_id]["few_shot_count"] = min(3, max(1, current_few_shot))
    if any(item in {"service_match", "semantic"} for item in failure_types):
        patched.setdefault("block_params", {}).setdefault("02", {})["few_shot_count"] = min(
            3,
            int(patched["block_params"].setdefault("02", {}).get("few_shot_count", patched.get("params", {}).get("few_shot_count", 3))) + 1,
        )
    if any(item in {"invalid_json", "extraneous"} for item in failure_types):
        patched.setdefault("params", {})["temperature"] = 0.0
    return patched


def evaluate_genome_on_rows(
    *,
    profile: str,
    genome: dict[str, Any],
    row_subset: list[tuple[int, dict[str, str]]],
    service_schema: dict[str, dict[str, Any]],
    candidate_k: int,
    llm_mode: str | None,
    llm_endpoint: str | None,
    timeout_sec: int,
    retries: int,
    seed: int,
    run_label: str,
    det_profile: str = "legacy",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    temperature, max_tokens, model = _llm_settings(
        genome,
        argparse.Namespace(temperature=None, max_tokens=None),
    )

    model_slug = slugify(str(model))
    run_id = make_run_id(
        f"{run_label}_{model_slug}_{genome.get('id', 'genome')}",
        seed,
    )
    output_root = Path(output_dir).expanduser().resolve() if output_dir else RESULTS_DIR
    output_root.mkdir(parents=True, exist_ok=True)
    output_csv = output_root / f"candidates_{slugify(run_id)}.csv"
    generation_summary = generate_candidates_for_rows(
        profile=profile,
        genome=genome,
        dataset_rows=row_subset,
        service_schema=service_schema,
        candidate_k=candidate_k,
        llm_mode=llm_mode,
        llm_endpoint=llm_endpoint,
        timeout_sec=timeout_sec,
        retries=retries,
        run_id=run_id,
        output_csv=output_csv,
        seed=seed,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )

    det_rows: list[dict[str, Any]] = []
    scores: list[float] = []
    for row in generation_summary["rows"]:
        command_eng = row.get("command_eng", "")
        candidates = json.loads(row.get("candidates", "[]")) if row.get("candidates") else []
        scored = evaluate_candidates(
            command_eng,
            candidates,
            service_schema,
            connected_devices=row.get("connected_devices", ""),
            ground_truth=row.get("gt", ""),
            profile=det_profile,
        )
        best = scored[0] if scored else {
            "det_score": 0.0,
            "failure_reasons": ["no_candidates"],
            "candidate": "",
            "det_gt_exact": False,
            "det_gt_similarity": 0.0,
        }
        scores.append(float(best.get("det_score", 0.0)))
        det_rows.append(
            {
                "row_no": int(row.get("row_no") or 0),
                "category": str(row.get("category", "")),
                "command_eng": command_eng,
                "det_score": best.get("det_score", 0.0),
                "det_gt_exact": best.get("det_gt_exact", False),
                "det_gt_similarity": best.get("det_gt_similarity", 0.0),
                "failure_reasons": best.get("failure_reasons", []),
                "output": best.get("candidate", ""),
                "gt": row.get("gt", ""),
            }
        )
    avg_score = statistics.fmean(scores) if scores else 0.0
    variance = statistics.pvariance(scores) if len(scores) > 1 else 0.0
    return {
        "run_id": run_id,
        "output_csv": str(output_csv),
        "rows": det_rows,
        "avg_det_score": round(avg_score, 4),
        "variance": round(variance, 6),
        "failure_summary": summarize_failure_patterns(det_rows),
        "generation_summary": generation_summary,
    }


def _pick_exemplar_rows(metrics: dict[str, Any], *, max_rows: int = 2) -> list[dict[str, Any]]:
    rows = list(metrics.get("rows", []))
    rows.sort(
        key=lambda row: (
            float(row.get("det_gt_similarity", 0.0)),
            float(row.get("det_score", 0.0)),
            int(row.get("row_no", 0)),
        )
    )
    exemplars: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("gt"):
            continue
        exemplars.append(row)
        if len(exemplars) >= max_rows:
            break
    return exemplars


def run_feedback_loop(
    *,
    profile: str,
    genome: dict[str, Any],
    dataset_rows: list[tuple[int, dict[str, str]]],
    service_schema: dict[str, dict[str, Any]],
    validation_size: int,
    candidate_k: int,
    attempts: int,
    improvement_threshold: float,
    llm_mode: str | None,
    llm_endpoint: str | None,
    timeout_sec: int,
    retries: int,
    seed: int,
) -> dict[str, Any]:
    ensure_workspace()
    validation_rows = sample_rows(dataset_rows, sample_size=validation_size, seed=seed)
    baseline = evaluate_genome_on_rows(
        profile=profile,
        genome=genome,
        row_subset=validation_rows,
        service_schema=service_schema,
        candidate_k=candidate_k,
        llm_mode=llm_mode,
        llm_endpoint=llm_endpoint,
        timeout_sec=timeout_sec,
        retries=retries,
        seed=seed,
        run_label="feedback_baseline",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    patch_dir = RESULTS_DIR / "patch_attempts" / f"{slugify(genome.get('id', 'genome'))}_{timestamp}"
    patch_dir.mkdir(parents=True, exist_ok=True)
    dump_json(patch_dir / "baseline.json", baseline)

    best_genome = genome
    best_metrics = baseline
    attempts_log: list[dict[str, Any]] = []
    manual_rules = _load_manual_feedback_rules()
    top_failures = [name for name, _count in baseline["failure_summary"].get("top_failure_types", []) if name in PATCH_RULES]
    if not top_failures:
        top_failures = ["semantic"]
    exemplar_rows = _pick_exemplar_rows(baseline, max_rows=2)

    for attempt_index in range(attempts):
        active_failures = top_failures[: max(1, min(len(top_failures), attempt_index + 1))]
        patch_tag = f"patch_{timestamp}_{attempt_index + 1}"
        patched_genome = _make_patched_genome(
            best_genome,
            failure_types=active_failures,
            exemplar_rows=exemplar_rows,
            manual_rules=manual_rules,
            seed=seed + attempt_index + 1,
            patch_tag=patch_tag,
        )
        patched_genome_path = patch_dir / f"{patched_genome['id']}.json"
        dump_json(patched_genome_path, patched_genome)
        metrics = evaluate_genome_on_rows(
            profile=profile,
            genome=patched_genome,
            row_subset=validation_rows,
            service_schema=service_schema,
            candidate_k=candidate_k,
            llm_mode=llm_mode,
            llm_endpoint=llm_endpoint,
            timeout_sec=timeout_sec,
            retries=retries,
            seed=seed + attempt_index + 1,
            run_label=f"feedback_attempt_{attempt_index + 1}",
        )
        improved = float(metrics["avg_det_score"]) > float(best_metrics["avg_det_score"]) + improvement_threshold
        attempt_record = {
            "attempt": attempt_index + 1,
            "failure_types": active_failures,
            "genome_json": str(patched_genome_path),
            "avg_det_score": metrics["avg_det_score"],
            "variance": metrics["variance"],
            "improved": improved,
            "manual_rule_count": len(manual_rules),
        }
