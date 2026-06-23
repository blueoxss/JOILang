#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from utils.det_evaluator import strict_det_evaluate_row
except ImportError:
    from det_evaluator import strict_det_evaluate_row  # type: ignore


def evaluate_candidate_records(
    records: list[dict[str, Any]],
    *,
    det_threshold: float = 70.0,
) -> list[dict[str, Any]]:
    results = []
    for record in records:
        row = {
            "category": record.get("category", ""),
            "command_eng": record.get("command_eng", ""),
            "command_kor": record.get("command_kor", ""),
            "gt": record.get("gt", ""),
        }
        candidate = record.get("generated_json") or record.get("candidates") or "{}"
        if isinstance(candidate, str):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    candidate = parsed[0] if parsed else {}
                else:
                    candidate = parsed
            except Exception:
                pass
        result = strict_det_evaluate_row(
            row=row,
            candidate=candidate,
            row_no=record.get("row_no", ""),
            genome_id=str(record.get("genome_id") or "base"),
            candidate_index=int(record.get("candidate_index") or 0),
            det_threshold=det_threshold,
        )
        result.update(
            {
                "generation": record.get("generation", 0),
                "candidate_strategy": record.get("candidate_strategy", ""),
                "generation_error_type": record.get("generation_error_type", ""),
                "latency_sec": record.get("latency_sec", ""),
            }
        )
        results.append(result)
    return results


def _csv_cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key, "")) for key in columns})


def write_evaluation_outputs(out_dir: str | Path, eval_rows: list[dict[str, Any]]) -> dict[str, Any]:
    root = Path(out_dir)
    eval_dir = root / "eval"
    write_csv(eval_dir / "row_evaluation.csv", eval_rows)

    reason_counter = Counter(reason for row in eval_rows for reason in row.get("failure_reasons", []))
    reason_rows = [{"failure_reason": reason, "count": count} for reason, count in reason_counter.most_common()]
    write_csv(eval_dir / "failure_reason_summary.csv", reason_rows)

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eval_rows:
        by_category[str(row.get("category", ""))].append(row)
    category_rows = []
    for category, rows in sorted(by_category.items()):
        category_rows.append(
            {
                "category": category,
                "rows": len(rows),
                "det_pass_rate": sum(1 for row in rows if row.get("det_pass")) / len(rows) if rows else 0.0,
                "avg_det_score": sum(float(row.get("det_score") or 0) for row in rows) / len(rows) if rows else 0.0,
            }
        )
    write_csv(eval_dir / "category_summary.csv", category_rows)
    summary = {
        "rows": len(eval_rows),
        "det_pass_rate": sum(1 for row in eval_rows if row.get("det_pass")) / len(eval_rows) if eval_rows else 0.0,
        "avg_det_score": sum(float(row.get("det_score") or 0) for row in eval_rows) / len(eval_rows) if eval_rows else 0.0,
        "official_metric": "strict_det",
        "ground_truth_column": "gt",
        "cloud_is_auxiliary": True,
    }
    (eval_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
