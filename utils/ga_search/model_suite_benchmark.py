#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from statistics import fmean
from typing import Any

try:
    from .candidate_generation import generate_candidates_for_rows, write_candidate_csv
    from .dataset_runner import command_text, load_dataset_rows, select_dataset_rows
    from .evaluation import evaluate_candidate_records, write_evaluation_outputs
    from .local_model_registry import (
        MODEL_SPECS,
        build_worker_extra_payload,
        canonical_model_id,
        default_local_model_base_dir,
        resolve_local_model_name,
    )
    from .model_resolver import resolve_model_package
    from .render_adapter import render_model_spec
except ImportError:
    from candidate_generation import generate_candidates_for_rows, write_candidate_csv  # type: ignore
    from dataset_runner import command_text, load_dataset_rows, select_dataset_rows  # type: ignore
    from evaluation import evaluate_candidate_records, write_evaluation_outputs  # type: ignore
    from local_model_registry import (  # type: ignore
        MODEL_SPECS,
        build_worker_extra_payload,
        canonical_model_id,
        default_local_model_base_dir,
        resolve_local_model_name,
    )
    from model_resolver import resolve_model_package  # type: ignore
    from render_adapter import render_model_spec  # type: ignore


def _bool_text(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_json_arg(value: str | None) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    path = Path(text).expanduser()
    if path.exists():
        text = path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise SystemExit("--llm-extra-json must be a JSON object or a path to a JSON object.")
    return parsed


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _mean(values: list[float]) -> float:
    return round(fmean(values), 4) if values else 0.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonical JOILang local model suite benchmark under utils/ga_search."
    )
    parser.add_argument("--model", default="gpt_mg.version0_13")
    parser.add_argument("--model-package", default="")
    parser.add_argument("--model-key", action="append", default=[], help="Example: --model-key qwen25_coder_14b")
    parser.add_argument("--dataset", default="datasets/JOICommands-280.csv")
    parser.add_argument("--service-schema", default="datasets/service_list_ver2.0.1.json")
    parser.add_argument("--service-context-mode", default="schema_fallback")
    parser.add_argument("--row-no", action="append", type=int, default=[])
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--limit-per-category", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--candidate-k", type=int, default=1)
    parser.add_argument("--llm-mode", default="worker", choices=["worker", "local", "openai", "mock"])
    parser.add_argument("--llm-endpoint", default="")
    parser.add_argument("--llm-extra-json", default="", help="Inline JSON or JSON file path.")
    parser.add_argument("--local-model-base-dir", default=str(default_local_model_base_dir()))
    parser.add_argument("--worker-python", default="")
    parser.add_argument("--local-device", default="cuda:0")
    parser.add_argument("--local-dtype", default="bf16")
    parser.add_argument("--local-files-only", default="true")
    parser.add_argument("--local-trust-remote-code", default="true")
    parser.add_argument("--local-load-in-4bit", default="false")
    parser.add_argument("--local-max-new-tokens", type=int, default=512)
    parser.add_argument("--det-threshold", type=float, default=70.0)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--preflight-only", action="store_true")
    return parser


def _selected_model_keys(args: argparse.Namespace) -> list[str]:
    keys = [str(k).strip() for k in args.model_key if str(k).strip()]
    return list(dict.fromkeys(keys)) if keys else list(MODEL_SPECS)


def _select_rows(args: argparse.Namespace) -> list[tuple[int, dict[str, Any]]]:
    rows = load_dataset_rows(args.dataset)

    if args.row_no:
        selected: dict[int, dict[str, Any]] = {}
        for row_no in args.row_no:
            chunk = select_dataset_rows(
                rows,
                row_no=row_no,
                start_row=args.start_row,
                end_row=args.end_row,
                categories=args.category,
                limit_per_category=args.limit_per_category,
                sample_size=None,
                seed=args.seed,
            )
            for rn, row in chunk:
                selected[int(rn)] = row
        return sorted(selected.items(), key=lambda item: item[0])

    return select_dataset_rows(
        rows,
        row_no=None,
        start_row=args.start_row,
        end_row=args.end_row,
        categories=args.category,
        limit_per_category=args.limit_per_category,
        sample_size=args.sample_size,
        seed=args.seed,
    )


def _preflight(args: argparse.Namespace, model_keys: list[str]) -> list[dict[str, Any]]:
    base = Path(args.local_model_base_dir).expanduser()
    rows = []
    for key in model_keys:
        model_id = canonical_model_id(key)
        local_model = resolve_local_model_name(model_id, base_dir=base)
        rows.append(
            {
                "model_key": key,
                "model_id": model_id,
                "local_model_base_dir": str(base),
                "local_model_name": local_model,
                "local_model_exists": Path(local_model).exists(),
            }
        )
    return rows


def _render_prompt(args: argparse.Namespace, rows: list[tuple[int, dict[str, Any]]]) -> dict[str, Any]:
    spec = resolve_model_package(
        model=args.model or None,
        model_package=args.model_package or None,
    )
    user_input = command_text(rows[0][1]) if rows else "Turn on the light."
    other_params: dict[str, Any] = {}
    if args.service_schema:
        other_params["service_schema"] = args.service_schema
    return render_model_spec(
        spec,
        user_input or "Turn on the light.",
        connected_devices={},
        other_params=other_params,
    )


def run_one_model(
    args: argparse.Namespace,
    *,
    model_key: str,
    rows: list[tuple[int, dict[str, Any]]],
    output_root: Path,
) -> dict[str, Any]:
    model_id = canonical_model_id(model_key)
    rendered = _render_prompt(args, rows)

    extra = _read_json_arg(args.llm_extra_json)
    extra = build_worker_extra_payload(
        model_id,
        base_dir=args.local_model_base_dir,
        worker_python=args.worker_python,
        local_device=args.local_device,
        local_dtype=args.local_dtype,
        local_files_only=_bool_text(args.local_files_only),
        local_trust_remote_code=_bool_text(args.local_trust_remote_code),
        local_load_in_4bit=_bool_text(args.local_load_in_4bit),
        local_max_new_tokens=args.local_max_new_tokens,
        extra=extra,
    )

    model_dir = output_root / model_key
    records = generate_candidates_for_rows(
        rows=rows,
        rendered_package=rendered,
        out_dir=model_dir,
        llm_mode=args.llm_mode,
        model_key=model_id,
        candidate_k=args.candidate_k,
        generation=0,
        genome_id="suite_base",
        candidate_strategy="mock_gt_copy" if args.llm_mode == "mock" else f"{args.llm_mode}_direct",
        service_schema=args.service_schema,
        service_context_mode=args.service_context_mode,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
        llm_endpoint=args.llm_endpoint,
        llm_extra=extra,
        repair_attempts=0,
    )
    write_candidate_csv(model_dir / "candidates" / "generation_000.csv", records)

    eval_rows = evaluate_candidate_records(records, det_threshold=args.det_threshold)
    summary = write_evaluation_outputs(model_dir, eval_rows)

    det_scores = [float(row.get("det_score") or 0.0) for row in eval_rows]
    prompt_tokens = [float(row.get("generation_prompt_tokens_total") or 0.0) for row in eval_rows]
    completion_tokens = [float(row.get("generation_completion_tokens_total") or 0.0) for row in eval_rows]
    latency = [float(row.get("latency_sec") or 0.0) for row in eval_rows]
    error_types = [str(row.get("generation_error_type") or "") for row in eval_rows if str(row.get("generation_error_type") or "")]

    model_summary = {
        "model_key": model_key,
        "model_id": model_id,
        "out_dir": str(model_dir),
        "rows": len(eval_rows),
        "det_pass_rate": summary.get("det_pass_rate", 0.0),
        "avg_det_score": _mean(det_scores),
        "generation_error_rate": summary.get("generation_error_rate", 0.0),
        "avg_prompt_tokens": _mean(prompt_tokens),
        "avg_completion_tokens": _mean(completion_tokens),
        "avg_latency_sec": _mean(latency),
        "local_model_name": str(extra.get("local_model_name", "")),
        "local_model_exists": Path(str(extra.get("local_model_name", ""))).exists(),
        "worker_python": str(extra.get("worker_python", "")),
        "local_worker": str(extra.get("local_worker", "")),
        "top_generation_error_type": error_types[0] if error_types else "",
    }
    (model_dir / "model_summary.json").write_text(
        json.dumps(model_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return model_summary


def main() -> int:
    args = build_parser().parse_args()
    output_root = Path(
        args.output_dir
        or f"artifacts/model_suite_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    model_keys = _selected_model_keys(args)
    preflight_rows = _preflight(args, model_keys)
    _write_csv(output_root / "preflight.csv", preflight_rows)

    print(json.dumps({"output_root": str(output_root), "preflight": preflight_rows}, ensure_ascii=False, indent=2))

    if args.preflight_only:
        return 0

    rows = _select_rows(args)
    if not rows:
        raise SystemExit("no dataset rows selected")

    summaries = [
        run_one_model(args, model_key=model_key, rows=rows, output_root=output_root)
        for model_key in model_keys
    ]

    _write_csv(output_root / "suite_summary.csv", summaries)
    (output_root / "suite_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"output_root": str(output_root), "models": summaries}, ensure_ascii=False, indent=2))

    return 2 if any(float(item.get("generation_error_rate") or 0.0) >= 1.0 for item in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
