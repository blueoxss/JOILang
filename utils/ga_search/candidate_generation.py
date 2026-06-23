#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

try:
    from .dataset_runner import command_text
except ImportError:
    from dataset_runner import command_text  # type: ignore


GENERATION_ERROR_TYPES = {
    "invalid_json",
    "empty_output",
    "worker_crash",
    "model_load_error",
    "timeout",
    "openai_unauthorized",
    "openai_rate_limit",
    "cuda_oom",
    "unsupported_llm_mode",
    "unknown_error",
}


def parse_gt_for_mock(row: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(str(row.get("gt") or "{}"))
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        data = {}
    return {
        "name": str(data.get("name", "")),
        "cron": str(data.get("cron", "")),
        "period": data.get("period", 0),
        "code": str(data.get("code") or data.get("script") or ""),
    }


def _write_raw_response(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_candidates_for_rows(
    *,
    rows: list[tuple[int, dict[str, Any]]],
    rendered_package: dict[str, Any],
    out_dir: str | Path,
    llm_mode: str = "mock",
    candidate_k: int = 1,
    generation: int = 0,
    genome_id: str = "base",
    candidate_strategy: str = "mock_gt_copy",
) -> list[dict[str, Any]]:
    root = Path(out_dir)
    raw_dir = root / "raw_responses"
    prompt_dir = root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for row_no, row in rows:
        prompt_log_path = prompt_dir / f"row_{row_no}_gen_{generation:03d}.md"
        prompt_log_path.write_text(str(rendered_package.get("prompt_text") or ""), encoding="utf-8")
        for candidate_index in range(max(1, candidate_k)):
            started = time.perf_counter()
            generation_error_type = ""
            generation_error_count = 0
            if llm_mode == "mock":
                candidate = parse_gt_for_mock(row)
            else:
                candidate = {"name": "", "cron": "", "period": 0, "code": ""}
                generation_error_type = "unsupported_llm_mode"
                generation_error_count = 1
            latency = time.perf_counter() - started
            raw_response_path = raw_dir / f"row_{row_no}_cand_{candidate_index}_gen_{generation:03d}.json"
            _write_raw_response(raw_response_path, {"llm_mode": llm_mode, "candidate": candidate, "error": generation_error_type})
            records.append(
                {
                    "row_no": row_no,
                    "category": row.get("category", ""),
                    "command_eng": row.get("command_eng", ""),
                    "command_kor": row.get("command_kor", ""),
                    "gt": row.get("gt", ""),
                    "genome_id": genome_id,
                    "generation": generation,
                    "candidate_index": candidate_index,
                    "candidate_strategy": candidate_strategy,
                    "prompt_render_mode": rendered_package.get("render_mode") or rendered_package.get("model_render_mode", ""),
                    "prompt_assets_dir": rendered_package.get("source_model_package", ""),
                    "prompt_log_paths": json.dumps([str(prompt_log_path)], ensure_ascii=False),
                    "raw_response_path": str(raw_response_path),
                    "candidates": json.dumps([candidate], ensure_ascii=False),
                    "generated_code": candidate.get("code", ""),
                    "generated_json": json.dumps(candidate, ensure_ascii=False),
                    "generation_error_type": generation_error_type,
                    "generation_error_count": generation_error_count,
                    "generation_prompt_tokens_total": 0,
                    "generation_completion_tokens_total": 0,
                    "generation_total_tokens_total": 0,
                    "latency_sec": round(latency, 6),
                    "peak_vram_gb": "",
                    "service_context_source": "mock_gt" if llm_mode == "mock" else "unsupported",
                    "service_context_mode": "schema_fallback",
                    "service_list_retrieval_scores": json.dumps(
                        {"status": "retrieval_disabled", "reason": "mock_generation"},
                        ensure_ascii=False,
                    ),
                    "connected_devices_used": row.get("connected_devices", ""),
                    "service_schema_path": "",
                }
            )
    return records


def write_candidate_csv(path: str | Path, records: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        target.write_text("", encoding="utf-8")
        return
    columns = list(records[0].keys())
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            writer.writerow(record)
