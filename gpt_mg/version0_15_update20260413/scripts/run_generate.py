#!/usr/bin/env python3
# Assumption: execute from anywhere; this script adds gpt_mg/version0_14 to sys.path and reads repo datasets without modifying them.
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from utils.local_llm_client import (
    LocalLLMError,
    call as llm_call,
    classify_error_text,
    is_oom_error_type,
)
from utils.pipeline_common import (
    DATASET_DEFAULT,
    DEFAULT_CANDIDATE_STRATEGIES,
    LOGS_DIR,
    RESULTS_DIR,
    SERVICE_SCHEMA_DEFAULT,
    append_jsonl,
    atomic_write_csv,
    build_prompt_values,
    dump_json,
    ensure_workspace,
    load_dataset_rows,
    load_genome,
    load_service_schema,
    make_run_id,
    normalize_candidate_json_text,
    parse_connected_devices,
    render_prompt_bundle,
    select_rows,
    slugify,
    unique_fieldnames,
)


GENERATION_EXTRA_FIELDS = [
    "row_no",
    "profile",
    "genome_id",
    "genome_seed",
    "run_id",
    "candidate_count",
    "candidates",
    "candidate_metadata",
    "prompt_log_paths",
    "generation_status",
    "generation_call_count",
    "generation_error_count",
    "generation_error_type",
    "generation_error_types",
    "generation_oom_flag",
    "generation_prompt_chars_total",
    "generation_prompt_tokens_total",
    "generation_completion_tokens_total",
    "generation_total_tokens_total",
    "generation_llm_latency_sec",
    "generation_peak_vram_gb",
    "generation_total_pipeline_sec",
    "llm_mode",
    "llm_model",
    "service_list_snippet_source",
    "service_list_device_count",
    "service_list_retrieval_status",
    "service_list_retrieval_mode",
    "service_list_retrieval_topk",
    "service_list_retrieval_device",
    "service_list_retrieval_categories",
    "service_list_retrieval_scores",
    "service_list_retrieval_fallback_reason",
    "prompt_render_mode",
    "prompt_assets_dir",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate JOI candidates for selected JOICommands-280 rows using a version0_14 genome.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--genome-json", default=str(VERSION_ROOT / "genomes" / "example_genome.json"))
    parser.add_argument("--dataset", default=str(DATASET_DEFAULT))
    parser.add_argument("--service-schema", default=str(SERVICE_SCHEMA_DEFAULT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--category", action="append", default=[], help="Filter by dataset category. Can be repeated or comma-separated.")
    parser.add_argument("--candidate-k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-csv", default=None)
    parser.add_argument("--llm-mode", default=None)
    parser.add_argument("--llm-endpoint", default=None)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--model", default=None, help="Override the model id while keeping the same prompt/genome.")
    parser.add_argument("--service-context-mode", default=None, choices=["auto", "retrieval_fallback", "schema_fallback"])
    parser.add_argument("--enable-retrieval-premapping", action="store_true", help="Shortcut for --service-context-mode retrieval_fallback.")
    parser.add_argument("--disable-retrieval-premapping", action="store_true", help="Shortcut for --service-context-mode schema_fallback.")
    parser.add_argument("--retrieval-topk", type=int, default=None)
    parser.add_argument("--retrieval-mode", default=None, choices=["hybrid", "dense", "bm25"])
    parser.add_argument("--retrieval-json", default=None)
    parser.add_argument("--retrieval-bundle-dir", default=None)
    parser.add_argument("--retrieval-model-dir", default=None)
    parser.add_argument("--retrieval-device", default=None)
    parser.add_argument("--prompt-render-mode", default=None, choices=["blocks", "legacy_v13_monolith"])
    parser.add_argument("--prompt-assets-dir", default=None, help="Optional directory for legacy monolithic prompt assets.")
    return parser


def _service_context_mode(args: argparse.Namespace) -> str | None:
    if args.enable_retrieval_premapping:
        return "retrieval_fallback"
    if args.disable_retrieval_premapping:
        return "schema_fallback"
    return args.service_context_mode


def _candidate_strategies(genome: dict[str, Any], candidate_k: int) -> list[str]:
    strategies = list(genome.get("params", {}).get("candidate_strategies") or DEFAULT_CANDIDATE_STRATEGIES)
    if not strategies:
        strategies = list(DEFAULT_CANDIDATE_STRATEGIES)
    return [strategies[idx % len(strategies)] for idx in range(candidate_k)]


def _llm_settings(
    genome: dict[str, Any],
    cli_args: argparse.Namespace,
    *,
    model_override: str | None = None,
) -> tuple[float, int, str]:
    params = genome.get("params", {})
    block_02 = genome.get("block_params", {}).get("02", {})
    temperature = cli_args.temperature
    if temperature is None:
        temperature = block_02.get("temperature", params.get("temperature", 0.0))
    max_tokens = cli_args.max_tokens
    if max_tokens is None:
        max_tokens = block_02.get("max_tokens", params.get("max_tokens", 1024))
    model = str(model_override or params.get("model", "Qwen/Qwen2.5-Coder-7B-Instruct"))
    return float(temperature), int(max_tokens), str(model)


def _system_prompt() -> str:
    return (
        "You are a deterministic JOILang generation engine. "
        "The natural-language command may be written in English or Korean. "
        "If it is Korean, translate it internally to the closest intent-preserving English meaning before reasoning. "
        "Follow the user instructions exactly and return only the requested JSON object."
    )


def _error_type_from_exception(exc: Exception) -> str:
    if isinstance(exc, LocalLLMError):
        return str(exc.error_type or classify_error_text(str(exc)))
    return classify_error_text(str(exc))


def _summarize_candidate_meta(candidate_meta: list[dict[str, Any]]) -> dict[str, Any]:
    error_types: list[str] = []
    prompt_chars = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0
    llm_latency_sec = 0.0
    peak_vram_gb = 0.0
    for meta in candidate_meta:
        prompt_chars += int(meta.get("prompt_chars") or 0)
        prompt_tokens += int(meta.get("prompt_tokens") or 0)
        completion_tokens += int(meta.get("completion_tokens") or 0)
        total_tokens += int(meta.get("total_tokens") or 0)
        llm_latency_sec += float(meta.get("latency_sec") or 0.0)
        peak_vram_gb = max(peak_vram_gb, float(meta.get("peak_vram_gb") or 0.0))
        error_type = str(meta.get("error_type", "") or "").strip()
        if error_type:
            error_types.append(error_type)
    primary_error = error_types[0] if error_types else ""
    return {
        "generation_call_count": len(candidate_meta),
        "generation_error_count": len(error_types),
        "generation_error_type": primary_error,
        "generation_error_types": json.dumps(error_types, ensure_ascii=False),
        "generation_oom_flag": any(is_oom_error_type(item) for item in error_types),
        "generation_prompt_chars_total": prompt_chars,
        "generation_prompt_tokens_total": prompt_tokens,
        "generation_completion_tokens_total": completion_tokens,
        "generation_total_tokens_total": total_tokens,
        "generation_llm_latency_sec": round(llm_latency_sec, 4),
        "generation_peak_vram_gb": round(peak_vram_gb, 4),
    }


def generate_candidates_for_rows(
    *,
    profile: str,
    genome: dict[str, Any],
    dataset_rows: list[tuple[int, dict[str, str]]],
    service_schema: dict[str, dict[str, Any]],
    candidate_k: int,
    llm_mode: str | None,
    llm_endpoint: str | None,
    timeout_sec: int,
    retries: int,
    run_id: str,
    output_csv: str | Path,
    seed: int,
    temperature: float,
    max_tokens: int,
    model: str,
    llm_extra_payload: dict[str, Any] | None = None,
    service_context_kwargs: dict[str, Any] | None = None,
    prompt_render_mode: str | None = None,
    prompt_assets_dir: str | None = None,
) -> dict[str, Any]:
    ensure_workspace()
    output_csv = Path(output_csv)
    logs_dir = LOGS_DIR / run_id
    logs_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = RESULTS_DIR / f"candidates_{slugify(run_id)}.jsonl"

    output_rows: list[dict[str, Any]] = []
    fieldnames: list[str] | None = None
    strategies = _candidate_strategies(genome, candidate_k)
    for row_no, row in dataset_rows:
        row_started = time.perf_counter()
        candidates: list[str] = []
        candidate_meta: list[dict[str, Any]] = []
        prompt_log_paths: list[str] = []
        generation_status = "ok"
        for candidate_index in range(candidate_k):
            strategy = strategies[candidate_index]
            values = build_prompt_values(
                row_no,
                row,
                service_schema,
                candidate_strategy=strategy,
                **(service_context_kwargs or {}),
            )
            system_prompt, user_prompt, manifest = render_prompt_bundle(
                genome,
                values=values,
                command_text=str(values.get("command_text") or values.get("command_eng") or values.get("command_kor") or ""),
                prompt_render_mode=prompt_render_mode,
                prompt_assets_dir=prompt_assets_dir,
                phase="generate",
                default_system_prompt=_system_prompt(),
            )
            prompt_chars = len(system_prompt) + len(user_prompt)
            log_path = logs_dir / f"row_{row_no:03d}_cand_{candidate_index + 1}.json"
            prompt_log_paths.append(str(log_path))
            try:
                response = llm_call(
                    system_prompt,
                    user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    mode=llm_mode,
                    model=model,
                    endpoint=llm_endpoint,
                    timeout_sec=timeout_sec,
                    retries=retries,
                    seed=seed + row_no + candidate_index,
                    log_path=log_path,
                    extra_payload=llm_extra_payload,
                )
                candidate_text = normalize_candidate_json_text(
                    str(response.get("content", "")).strip(),
                    default_cron=str(values.get("optional_cron", "") or ""),
                    default_period=int(str(values.get("optional_period", "0") or "0")),
                    service_schema=service_schema,
                    command_text=str(values.get("command_eng") or values.get("command_kor") or ""),
                    connected_devices=parse_connected_devices(row.get("connected_devices", "")),
                )
                candidates.append(candidate_text)
                candidate_meta.append(
                    {
                        "candidate_index": candidate_index,
                        "strategy": strategy,
                        "prompt_chars": prompt_chars,
                        "prompt_tokens": response.get("prompt_tokens", 0),
                        "completion_tokens": response.get("completion_tokens", 0),
                        "total_tokens": response.get("total_tokens", 0),
                        "latency_sec": response.get("latency_sec", 0.0),
                        "peak_vram_gb": response.get("peak_vram_gb", 0.0),
                        "load_sec": response.get("load_sec", 0.0),
                        "generate_sec": response.get("generate_sec", 0.0),
                        "prompt_prep_sec": response.get("prompt_prep_sec", 0.0),
                        "decode_sec": response.get("decode_sec", 0.0),
                        "worker_pid": response.get("worker_pid", 0),
                        "error_type": "",
                        "oom_flag": False,
                        "block_manifest": manifest,
                    }
                )
            except Exception as exc:
                generation_status = "partial_error"
                error_type = _error_type_from_exception(exc)
                candidates.append("")
                candidate_meta.append(
                    {
                        "candidate_index": candidate_index,
                        "strategy": strategy,
                        "prompt_chars": prompt_chars,
                        "error": str(exc),
                        "error_type": error_type,
                        "oom_flag": is_oom_error_type(error_type),
                        "block_manifest": manifest,
                    }
                )
                dump_json(log_path, {"error": str(exc), "block_manifest": manifest, "prompt": user_prompt})

        row_metrics = _summarize_candidate_meta(candidate_meta)
        result_row = dict(row)
        result_row.update(
            {
                "row_no": row_no,
                "profile": profile,
                "genome_id": genome.get("id", "unknown"),
                "genome_seed": genome.get("seed", seed),
                "run_id": run_id,
                "candidate_count": len(candidates),
                "candidates": json.dumps(candidates, ensure_ascii=False),
                "candidate_metadata": json.dumps(candidate_meta, ensure_ascii=False),
                "prompt_log_paths": json.dumps(prompt_log_paths, ensure_ascii=False),
                "generation_status": generation_status,
                "generation_total_pipeline_sec": round(time.perf_counter() - row_started, 4),
                "llm_mode": llm_mode or "worker",
                "llm_model": model,
                "prompt_render_mode": str(prompt_render_mode or "blocks"),
                "prompt_assets_dir": str(prompt_assets_dir or ""),
            }
        )
        for key in (
            "service_list_snippet_source",
            "service_list_device_count",
            "service_list_retrieval_status",
            "service_list_retrieval_mode",
            "service_list_retrieval_topk",
            "service_list_retrieval_device",
            "service_list_retrieval_categories",
            "service_list_retrieval_scores",
            "service_list_retrieval_fallback_reason",
        ):
            result_row[key] = values.get(key, "")
        result_row.update(row_metrics)
        output_rows.append(result_row)
        fieldnames = unique_fieldnames(output_rows, GENERATION_EXTRA_FIELDS)
        atomic_write_csv(output_csv, fieldnames, output_rows)
        append_jsonl(
            jsonl_path,
            {
                "row_no": row_no,
                "profile": profile,
                "genome_id": genome.get("id", "unknown"),
                "candidates": candidates,
                "candidate_metadata": candidate_meta,
            },
        )

    return {
        "run_id": run_id,
        "output_csv": str(output_csv),
        "jsonl_path": str(jsonl_path),
        "row_count": len(output_rows),
        "rows": output_rows,
        "fieldnames": fieldnames or [],
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ensure_workspace()
    genome = load_genome(args.genome_json)
    service_schema = load_service_schema(args.service_schema)
    rows = load_dataset_rows(args.dataset)
    selected_rows = select_rows(
        rows,
        start_row=args.start_row,
        end_row=args.end_row,
        limit=args.limit,
        categories=args.category,
    )
    if not selected_rows:
        raise SystemExit("No rows selected. Check --start-row/--end-row/--limit/--category.")

    temperature, max_tokens, model = _llm_settings(genome, args, model_override=args.model)
    run_id = args.run_id or make_run_id(f"generate_{args.profile}_{genome.get('id', 'genome')}", args.seed)
    output_csv = args.output_csv or RESULTS_DIR / f"candidates_{slugify(genome.get('id', 'genome'))}.csv"

    summary = generate_candidates_for_rows(
        profile=args.profile,
        genome=genome,
        dataset_rows=selected_rows,
        service_schema=service_schema,
        candidate_k=args.candidate_k,
        llm_mode=args.llm_mode,
        llm_endpoint=args.llm_endpoint,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        run_id=run_id,
        output_csv=output_csv,
        seed=args.seed,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        service_context_kwargs={
            "service_context_mode": _service_context_mode(args),
            "retrieval_topk": args.retrieval_topk,
            "retrieval_mode": args.retrieval_mode,
            "retrieval_json_path": args.retrieval_json,
            "retrieval_bundle_dir": args.retrieval_bundle_dir,
            "retrieval_model_dir": args.retrieval_model_dir,
            "retrieval_device": args.retrieval_device,
        },
        prompt_render_mode=args.prompt_render_mode,
        prompt_assets_dir=args.prompt_assets_dir,
    )

    print("Generation completed")
    print(f"- run_id: {summary['run_id']}")
    print(f"- output_csv: {summary['output_csv']}")
    print(f"- jsonl_path: {summary['jsonl_path']}")
    print(f"- rows: {summary['row_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
