#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

try:
    from .dataset_runner import command_text
    from .llm_backends import LLMBackendError, call_llm_backend, messages_from_rendered
    from .repair_loop import repair_candidate_json_text
except ImportError:
    from dataset_runner import command_text  # type: ignore
    from llm_backends import LLMBackendError, call_llm_backend, messages_from_rendered  # type: ignore
    from repair_loop import repair_candidate_json_text  # type: ignore


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


def _safe_token(value: Any, default: str = "item") -> str:
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("_")
    return token or default


def _write_prompt_logs(
    prompt_dir: Path,
    row_no: int,
    candidate_index: int,
    generation: int,
    genome_id: str,
    rendered_package: dict[str, Any],
) -> list[str]:
    prompt_dir.mkdir(parents=True, exist_ok=True)
    stem = f"row_{row_no}_{_safe_token(genome_id, 'genome')}_cand_{candidate_index}_gen_{generation:03d}"
    md_path = prompt_dir / f"{stem}.md"
    json_path = prompt_dir / f"{stem}.json"
    md_path.write_text(str(rendered_package.get("prompt_text") or ""), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "model_id": rendered_package.get("model_id"),
                "render_mode": rendered_package.get("render_mode"),
                "messages": messages_from_rendered(rendered_package),
                "prompt_text": rendered_package.get("prompt_text") or "",
                "model_spec": rendered_package.get("model_spec", {}),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return [str(md_path), str(json_path)]


def build_service_context(
    *,
    service_schema: str | Path | None = None,
    service_context_mode: str = "schema_fallback",
) -> dict[str, Any]:
    schema_path = str(service_schema or "").strip()
    exists = bool(schema_path and Path(schema_path).exists())
    mode = str(service_context_mode or "schema_fallback")
    if mode in {"disabled", "none", "off"}:
        retrieval = {"status": "retrieval_disabled", "reason": "service_context_mode disabled"}
    else:
        retrieval = {"status": "retrieval_disabled", "reason": "canonical ga_search has not enabled service retrieval yet"}
    return {
        "service_schema_path": schema_path,
        "service_context_mode": mode,
        "service_context_source": "provided_schema" if exists else ("missing_schema" if schema_path else "not_provided"),
        "service_list_retrieval_scores": retrieval,
    }


def _empty_candidate() -> dict[str, Any]:
    return {"name": "", "cron": "", "period": 0, "code": ""}


def _raw_usage(raw_response: dict[str, Any]) -> dict[str, int]:
    usage = raw_response.get("usage") if isinstance(raw_response.get("usage"), dict) else {}
    return {
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def generate_candidates_for_rows(
    *,
    rows: list[tuple[int, dict[str, Any]]],
    rendered_package: dict[str, Any],
    out_dir: str | Path,
    llm_mode: str = "mock",
    model_key: str = "",
    candidate_k: int = 1,
    generation: int = 0,
    genome_id: str = "base",
    candidate_strategy: str = "mock_gt_copy",
    service_schema: str | Path | None = None,
    service_context_mode: str = "schema_fallback",
    timeout_sec: int = 1800,
    retries: int = 0,
    llm_endpoint: str = "",
    llm_extra: dict[str, Any] | None = None,
    repair_attempts: int = 0,
) -> list[dict[str, Any]]:
    root = Path(out_dir)
    raw_dir = root / "raw_responses"
    prompt_dir = root / "prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    mode = str(llm_mode or "mock").strip().lower()
    service_context = build_service_context(service_schema=service_schema, service_context_mode=service_context_mode)
    extra_payload = llm_extra or {}
    for row_no, row in rows:
        for candidate_index in range(max(1, candidate_k)):
            prompt_log_paths = _write_prompt_logs(prompt_dir, row_no, candidate_index, generation, genome_id, rendered_package)
            started = time.perf_counter()
            generation_error_type = ""
            generation_error_count = 0
            backend_response: dict[str, Any] = {}
            repair_result: dict[str, Any] = {}
            if mode == "mock":
                candidate = parse_gt_for_mock(row)
                backend_response = {
                    "content": json.dumps(candidate, ensure_ascii=False),
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "latency_sec": 0.0,
                    "peak_vram_gb": "",
                    "raw": {"mock": True},
                    "backend": "mock",
                }
                repair_result = {
                    "ok": True,
                    "candidate": candidate,
                    "error_type": "",
                    "repair_applied": False,
                    "repair_actions": [],
                }
            else:
                candidate = _empty_candidate()
                generation_error_count = 1
                last_error: LLMBackendError | None = None
                for attempt in range(max(1, retries + 1)):
                    try:
                        backend_response = call_llm_backend(
                            llm_mode=mode,
                            rendered_package=rendered_package,
                            model_key=model_key,
                            endpoint=llm_endpoint,
                            timeout_sec=timeout_sec,
                            extra_payload={**extra_payload, "attempt": attempt + 1},
                        )
                        repair_result = repair_candidate_json_text(str(backend_response.get("content") or ""))
                        candidate = repair_result.get("candidate", candidate)
                        generation_error_type = str(repair_result.get("error_type") or "")
                        generation_error_count = 1 if generation_error_type else 0
                        break
                    except LLMBackendError as exc:
                        last_error = exc
                        backend_response = {
                            "content": "",
                            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                            "latency_sec": round(time.perf_counter() - started, 6),
                            "peak_vram_gb": "",
                            "raw": exc.raw or {},
                            "backend": mode,
                            "error": str(exc),
                            "error_type": exc.error_type,
                        }
                        generation_error_type = exc.error_type
                        generation_error_count = 1
                if last_error and not repair_result and not backend_response.get("content"):
                    repair_result = {
                        "ok": False,
                        "candidate": candidate,
                        "error_type": generation_error_type,
                        "repair_applied": False,
                        "repair_actions": [],
                        "error": str(last_error),
                    }
            latency = time.perf_counter() - started
            raw_response_path = raw_dir / f"row_{row_no}_{_safe_token(genome_id, 'genome')}_cand_{candidate_index}_gen_{generation:03d}.json"
            usage = _raw_usage(backend_response)
            _write_raw_response(
                raw_response_path,
                {
                    "llm_mode": mode,
                    "candidate": candidate,
                    "generation_error_type": generation_error_type,
                    "backend_response": backend_response,
                    "repair": repair_result,
                    "service_context": service_context,
                },
            )
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
                    "candidate_strategy": candidate_strategy or ("mock_gt_copy" if mode == "mock" else f"{mode}_direct"),
                    "prompt_render_mode": rendered_package.get("render_mode") or rendered_package.get("model_render_mode", ""),
                    "prompt_assets_dir": rendered_package.get("source_model_package", ""),
                    "prompt_log_paths": json.dumps(prompt_log_paths, ensure_ascii=False),
                    "raw_response_path": str(raw_response_path),
                    "candidates": json.dumps([candidate], ensure_ascii=False),
                    "generated_code": candidate.get("code", ""),
                    "generated_json": json.dumps(candidate, ensure_ascii=False),
                    "generation_error_type": generation_error_type,
                    "generation_error_count": generation_error_count,
                    "generation_prompt_tokens_total": usage["prompt_tokens"],
                    "generation_completion_tokens_total": usage["completion_tokens"],
                    "generation_total_tokens_total": usage["total_tokens"],
                    "latency_sec": round(float(backend_response.get("latency_sec") or latency), 6),
                    "peak_vram_gb": backend_response.get("peak_vram_gb", ""),
                    "service_context_source": service_context["service_context_source"],
                    "service_context_mode": service_context["service_context_mode"],
                    "service_list_retrieval_scores": json.dumps(service_context["service_list_retrieval_scores"], ensure_ascii=False),
                    "connected_devices_used": row.get("connected_devices", ""),
                    "service_schema_path": service_context["service_schema_path"],
                    "repair_applied": bool(repair_result.get("repair_applied")),
                    "repair_actions": json.dumps(repair_result.get("repair_actions", []), ensure_ascii=False),
                    "backend": backend_response.get("backend", mode),
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
