#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.prompt_profiler import profile_prompt_blocks_for_genome
from utils.pipeline_common import BLOCKS_DIR, RESULTS_DIR, dump_json, load_genome


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip().lower())


def _block_files(blocks_dir: Path) -> list[Path]:
    return sorted(path for path in blocks_dir.glob("**/*") if path.is_file() and path.suffix.lower() in {".txt", ".md"})


def _read_prompt_lines(blocks_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _block_files(blocks_dir):
        rel = str(path.relative_to(blocks_dir))
        for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped:
                rows.append({"path": rel, "line": idx, "text": stripped, "norm": _normalize_line(stripped)})
    return rows


def _duplicate_rules(rows: list[dict[str, Any]], markers: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        norm = str(row["norm"])
        if any(marker in norm for marker in markers):
            grouped[norm].append(row)
    return [
        {"text": text, "count": len(items), "locations": [{"path": item["path"], "line": item["line"]} for item in items]}
        for text, items in sorted(grouped.items())
        if len(items) > 1
    ]


def _verbose_blocks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        words = re.findall(r"\w+", str(row["text"]))
        if len(words) >= 35 and any(token in str(row["norm"]) for token in ("explain", "description", "because", "therefore", "must")):
            findings.append({"path": row["path"], "line": row["line"], "word_count": len(words), "text": row["text"][:240]})
    return findings


def _negative_validator_rules(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validator_markers = (
        "invalid json",
        "schema",
        "unknown service",
        "argument_type",
        "enum",
        "lowercase receiver",
        "while",
        "sleep",
    )
    findings: list[dict[str, Any]] = []
    for row in rows:
        norm = str(row["norm"])
        if ("do not" in norm or "never" in norm or "forbid" in norm) and any(marker in norm for marker in validator_markers):
            findings.append({"path": row["path"], "line": row["line"], "text": row["text"]})
    return findings


def _unselected_examples(genome: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for block in profile_prompt_blocks_for_genome(genome):
        few_shot_count = int(block.get("few_shot_count") or 0)
        removable = int(block.get("removable_examples") or 0)
        if removable > few_shot_count:
            findings.append(
                {
                    "block_id": block.get("block_id"),
                    "block_family": block.get("block_family"),
                    "few_shot_count": few_shot_count,
                    "removable_examples": removable,
                }
            )
    return findings


def build_report(*, blocks_dir: Path, genome: dict[str, Any]) -> dict[str, Any]:
    rows = _read_prompt_lines(blocks_dir)
    duplicate_output_contracts = _duplicate_rules(rows, ("return exactly", "return a single", "json object only"))
    duplicate_json_rules = _duplicate_rules(rows, ("json", "required keys", "code must"))
    repeated_service_descriptions = _duplicate_rules(rows, ("service_list_snippet", "canonical_name", "receiver", "function"))
    line_counts = Counter(row["path"] for row in rows)
    no_op_compressions: list[dict[str, Any]] = []
    strategies = list((genome.get("params") or {}).get("candidate_strategies") or [])
    if strategies == ["minimal"]:
        no_op_compressions.append(
            {
                "operator": "compress_candidate_strategies_to_minimal",
                "reason": "candidate_strategies already equals ['minimal']",
            }
        )
    return {
        "blocks_dir": str(blocks_dir),
        "line_counts": dict(line_counts),
        "duplicated_output_contracts": duplicate_output_contracts,
        "duplicated_json_only_rules": duplicate_json_rules,
        "repeated_device_function_descriptions": repeated_service_descriptions[:50],
        "verbose_explanation_blocks": _verbose_blocks(rows)[:100],
        "examples_that_may_never_be_selected": _unselected_examples(genome),
        "negative_rules_likely_covered_by_validators": _negative_validator_rules(rows)[:100],
        "no_op_compression_operators": no_op_compressions,
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    lines = ["# Prompt Redundancy Report", ""]
    lines.append(f"- Blocks dir: `{report.get('blocks_dir', '')}`")
    lines.append(f"- Duplicated output contracts: {len(report.get('duplicated_output_contracts') or [])}")
    lines.append(f"- Duplicated JSON-only rules: {len(report.get('duplicated_json_only_rules') or [])}")
    lines.append(f"- Repeated service/function descriptions: {len(report.get('repeated_device_function_descriptions') or [])}")
    lines.append(f"- Verbose explanation lines: {len(report.get('verbose_explanation_blocks') or [])}")
    lines.append(f"- Validator-covered negative rules: {len(report.get('negative_rules_likely_covered_by_validators') or [])}")
    lines.append("")
    for key, title in (
        ("duplicated_output_contracts", "Duplicated Output Contracts"),
        ("duplicated_json_only_rules", "Duplicated JSON Rules"),
        ("no_op_compression_operators", "No-op Compression Operators"),
    ):
        lines.append(f"## {title}")
        items = report.get(key) or []
        if not items:
            lines.append("- None detected.")
            lines.append("")
            continue
        for item in items[:20]:
            text = item.get("text") or item.get("operator") or ""
            reason = item.get("reason", "")
            lines.append(f"- `{text}` {reason}".rstrip())
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan JOILang prompt blocks for redundant prompt text.")
    parser.add_argument("--blocks-dir", default=str(BLOCKS_DIR))
    parser.add_argument("--genome-json", default=str(VERSION_ROOT / "genomes" / "example_genome.json"))
    parser.add_argument("--output-dir", default=str(RESULTS_DIR))
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    genome = load_genome(args.genome_json)
    report = build_report(blocks_dir=Path(args.blocks_dir).expanduser().resolve(), genome=genome)
    dump_json(output_dir / "prompt_redundancy_report.json", report)
    (output_dir / "prompt_redundancy_report.md").write_text(report_to_markdown(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
