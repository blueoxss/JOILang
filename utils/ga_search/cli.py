#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .advisor_integration import run_advisor_for_ga_search
    from .advisor_modes import validate_advisor_mode
    from .artifacts import default_run_dir, save_search_artifacts, write_candidate_artifacts
    from .block_search import build_blocks_search_input
    from .candidate_generation import generate_candidates_for_rows, write_candidate_csv
    from .checks import run_check
    from .dataset_runner import command_text, load_dataset_rows, select_dataset_rows
    from .evaluation import evaluate_candidate_records, write_evaluation_outputs
    from .ga_engine import run_mock_search
    from .model_resolver import ModelPackageSpec, resolve_model_package
    from .monolith_search import build_monolith_search_input
    from .render_adapter import render_model_spec
except ImportError:
    from advisor_integration import run_advisor_for_ga_search  # type: ignore
    from advisor_modes import validate_advisor_mode  # type: ignore
    from artifacts import default_run_dir, save_search_artifacts, write_candidate_artifacts  # type: ignore
    from block_search import build_blocks_search_input  # type: ignore
    from candidate_generation import generate_candidates_for_rows, write_candidate_csv  # type: ignore
    from checks import run_check  # type: ignore
    from dataset_runner import command_text, load_dataset_rows, select_dataset_rows  # type: ignore
    from evaluation import evaluate_candidate_records, write_evaluation_outputs  # type: ignore
    from ga_engine import run_mock_search  # type: ignore
    from model_resolver import ModelPackageSpec, resolve_model_package  # type: ignore
    from monolith_search import build_monolith_search_input  # type: ignore
    from render_adapter import render_model_spec  # type: ignore


COMMANDS = {"render", "eval", "search", "advisor", "check"}


def parse_json_arg(value: str | None, *, default: Any) -> Any:
    if value is None or str(value).strip() == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON argument: {exc}") from exc


def add_common_model_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", default="")
    parser.add_argument("--model-package", default="")
    parser.add_argument("--user-input", default="Turn on the light.")
    parser.add_argument("--connected-devices-json", default="")
    parser.add_argument("--other-params-json", default="")
    parser.add_argument("--search-mode", default="auto", choices=["monolith", "blocks", "auto"])
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--out-root", default="artifacts/ga_search")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--print-summary", action="store_true")
    parser.add_argument("--dry-run", action="store_true")


def add_dataset_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", default="datasets/JOICommands-280.csv")
    parser.add_argument("--service-schema", default="")
    parser.add_argument("--row-no", type=int, default=None)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--limit-per-category", type=int, default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    parser.add_argument("--validation-size", type=int, default=None)
    parser.add_argument("--cheap-eval-limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=0)


def add_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--llm-mode", default="mock", choices=["worker", "local", "openai", "mock"])
    parser.add_argument("--model-key", default="")
    parser.add_argument("--candidate-k", type=int, default=1)
    parser.add_argument("--repair-attempts", type=int, default=0)
    parser.add_argument("--det-profile", default="strict")
    parser.add_argument("--det-threshold", type=float, default=70.0)
    parser.add_argument("--print-mode", default="summary", choices=["summary", "compare", "none", "paths"])


def add_search_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--population", type=int, default=2)
    parser.add_argument("--gens", type=int, default=1)
    parser.add_argument("--min-generations", type=int, default=None)
    parser.add_argument("--max-generations", type=int, default=None)
    parser.add_argument("--selection-mode", default="det_score")
    parser.add_argument("--fitness-mode", default="strict_det")
    parser.add_argument("--mutation-mode", default="mock")
    parser.add_argument("--feedback-guided-mutation", action="store_true")
    parser.add_argument("--enable-compression-mutation", action="store_true")
    parser.add_argument("--enable-prompt-decompiler", action="store_true")
    parser.add_argument("--enable-rendered-prompt-dedupe", action="store_true")
    parser.add_argument("--enable-pareto-archive", action="store_true")
    parser.add_argument("--enable-group-specialist-archives", action="store_true")
    parser.add_argument("--write-model-package-artifacts", action="store_true")


def add_advisor_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--advisor-mode", default="none", choices=["none", "local", "cloud", "hybrid"])
    parser.add_argument("--advisor-llm-mode", default="mock", choices=["mock", "openai"])
    parser.add_argument("--advisor-model-key", default="")
    parser.add_argument("--advisor-trigger-mode", default="auto")
    parser.add_argument("--advisor-temperature", type=float, default=0.0)
    parser.add_argument("--strict-results-dir", default="")
    parser.add_argument("--local-det-report", default="")
    parser.add_argument("--cloud-judge-csv", default="")
    parser.add_argument("--advisor-rich-feedback", default="")
    parser.add_argument("--prompt-patches", default="")
    parser.add_argument("--advisor-top-k", type=int, default=20)
    parser.add_argument("--population-size", type=int, default=12)
    parser.add_argument("--dry-run-advisor", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Canonical JOILang GA search, render, and strict DET evaluation CLI.")
    sub = parser.add_subparsers(dest="command")

    render = sub.add_parser("render", help="Render a model package prompt.")
    add_common_model_args(render)

    ev = sub.add_parser("eval", help="Generate candidates and run strict DET evaluation.")
    add_common_model_args(ev)
    add_dataset_args(ev)
    add_generation_args(ev)

    search = sub.add_parser("search", help="Run a lightweight GA search/evaluation loop.")
    add_common_model_args(search)
    add_dataset_args(search)
    add_generation_args(search)
    add_search_args(search)
    add_advisor_args(search)

    advisor = sub.add_parser("advisor", help="Build advisor evidence and mutation population artifacts.")
    add_common_model_args(advisor)
    add_advisor_args(advisor)

    check = sub.add_parser("check", help="Run lightweight ga_search checks.")
    add_common_model_args(check)
    check.add_argument("--check", default="smoke")

    return parser


def build_flat_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backward-compatible GA search artifact preparation.")
    add_common_model_args(parser)
    add_advisor_args(parser)
    parser.set_defaults(command="prepare")
    return parser


def resolve_spec(args: argparse.Namespace) -> ModelPackageSpec:
    return resolve_model_package(model=args.model or None, model_package=args.model_package or None)


def render_for_args(args: argparse.Namespace, user_input: str | None = None) -> dict[str, Any]:
    spec = resolve_spec(args)
    connected_devices = parse_json_arg(getattr(args, "connected_devices_json", ""), default={})
    other_params = parse_json_arg(getattr(args, "other_params_json", ""), default={})
    if getattr(args, "service_schema", ""):
        other_params.setdefault("service_schema", args.service_schema)
    return render_model_spec(
        spec,
        user_input or getattr(args, "user_input", "Turn on the light."),
        connected_devices=connected_devices,
        other_params=other_params,
    )


def effective_search_mode(args: argparse.Namespace, rendered: dict[str, Any]) -> str:
    mode = getattr(args, "search_mode", "auto") or "auto"
    if mode == "auto":
        return "blocks" if rendered.get("blocks_metadata") else "monolith"
    return mode


def build_search_input(rendered: dict[str, Any], search_mode: str) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    if search_mode == "blocks":
        search_input = build_blocks_search_input(rendered)
        return search_input, search_input.get("blocks", [])
    search_input = build_monolith_search_input(rendered)
    return search_input, None


def run_prepare_like(args: argparse.Namespace) -> int:
    rendered = render_for_args(args)
    search_mode = effective_search_mode(args, rendered)
    search_input, decomposed_blocks = build_search_input(rendered, search_mode)
    advisor_mode = validate_advisor_mode(getattr(args, "advisor_mode", "none"))
    run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
        args.out_root,
        rendered.get("model_package_id") or rendered.get("model_id") or "model",
        timestamp=args.timestamp or None,
    )
    advisor_result = None
    candidate_records = None
    if advisor_mode != "none" or getattr(args, "prompt_patches", ""):
        advisor_result = run_advisor_for_ga_search(
            advisor_mode=advisor_mode,
            advisor_dir=run_dir / "advisor",
            search_mode=search_mode,
            strict_results_dir=getattr(args, "strict_results_dir", "") or None,
            local_det_report=getattr(args, "local_det_report", "") or None,
            cloud_judge_csv=getattr(args, "cloud_judge_csv", "") or None,
            advisor_rich_feedback=getattr(args, "advisor_rich_feedback", "") or None,
            prompt_patches=getattr(args, "prompt_patches", "") or None,
            top_k=int(getattr(args, "advisor_top_k", 20) or 20),
            dry_run=bool(getattr(args, "dry_run_advisor", False)),
            population_size=int(getattr(args, "population_size", 12) or 12),
        )
        candidate_records = advisor_result.get("candidate_records", [])
    candidate_manifest = write_candidate_artifacts(run_dir, search_mode=search_mode, advisor_mode=advisor_mode, candidates=candidate_records)
    manifest = save_search_artifacts(
        run_dir,
        rendered_package=rendered,
        search_input=search_input,
        search_mode=search_mode,
        advisor_mode=advisor_mode,
        decomposed_blocks=decomposed_blocks,
        advisor_summary=advisor_result,
        candidate_manifest=candidate_manifest,
    )
    if getattr(args, "print_summary", False):
        print_summary(manifest, search_input, advisor_result)
    return 0


def run_render(args: argparse.Namespace) -> int:
    rendered = render_for_args(args)
    search_mode = effective_search_mode(args, rendered)
    search_input, decomposed_blocks = build_search_input(rendered, search_mode)
    if not args.dry_run:
        run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
            args.out_root,
            rendered.get("model_package_id") or rendered.get("model_id") or "model",
            timestamp=args.timestamp or None,
        )
        candidate_manifest = write_candidate_artifacts(run_dir, search_mode=search_mode, advisor_mode="none")
        save_search_artifacts(
            run_dir,
            rendered_package=rendered,
            search_input=search_input,
            search_mode=search_mode,
            advisor_mode="none",
            decomposed_blocks=decomposed_blocks,
            candidate_manifest=candidate_manifest,
        )
    print(
        json.dumps(
            {
                "model_id": rendered.get("model_id"),
                "model_package": rendered.get("source_model_package"),
                "render_mode": rendered.get("render_mode"),
                "search_mode": search_mode,
                "prompt_chars": len(str(rendered.get("prompt_text") or "")),
                "messages": len(rendered.get("messages") or []),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def selected_rows_for_args(args: argparse.Namespace) -> list[tuple[int, dict[str, Any]]]:
    rows = load_dataset_rows(args.dataset)
    sample_size = args.sample_size
    if sample_size is None:
        sample_size = args.cheap_eval_limit or args.validation_size
    return select_dataset_rows(
        rows,
        row_no=args.row_no,
        start_row=args.start_row,
        end_row=args.end_row,
        categories=args.category,
        limit_per_category=args.limit_per_category,
        sample_size=sample_size,
        seed=args.seed,
    )


def run_eval(args: argparse.Namespace) -> int:
    rows = selected_rows_for_args(args)
    if not rows:
        raise SystemExit("no dataset rows selected")
    rendered = render_for_args(args, user_input=command_text(rows[0][1]) or args.user_input)
    search_mode = effective_search_mode(args, rendered)
    run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
        args.out_root,
        rendered.get("model_package_id") or rendered.get("model_id") or "model",
        timestamp=args.timestamp or None,
    )
    candidate_records = generate_candidates_for_rows(
        rows=rows,
        rendered_package=rendered,
        out_dir=run_dir,
        llm_mode=args.llm_mode,
        candidate_k=args.candidate_k,
        generation=0,
        genome_id="eval_base",
        candidate_strategy="mock_gt_copy" if args.llm_mode == "mock" else "unsupported",
    )
    write_candidate_csv(run_dir / "candidates" / "generation_000.csv", candidate_records)
    eval_rows = evaluate_candidate_records(candidate_records, det_threshold=args.det_threshold)
    summary = write_evaluation_outputs(run_dir, eval_rows)
    search_mode = effective_search_mode(args, rendered)
    search_input, decomposed_blocks = build_search_input(rendered, search_mode)
    candidate_manifest = write_candidate_artifacts(run_dir, search_mode=search_mode, advisor_mode="none")
    save_search_artifacts(
        run_dir,
        rendered_package=rendered,
        search_input=search_input,
        search_mode=search_mode,
        advisor_mode="none",
        decomposed_blocks=decomposed_blocks,
        candidate_manifest=candidate_manifest,
    )
    if args.print_mode != "none":
        print(json.dumps({"out_dir": str(run_dir), **summary}, ensure_ascii=False, indent=2))
    return 0


def run_search(args: argparse.Namespace) -> int:
    rows = selected_rows_for_args(args)
    if not rows:
        raise SystemExit("no dataset rows selected")
    rendered = render_for_args(args, user_input=command_text(rows[0][1]) or args.user_input)
    search_mode = effective_search_mode(args, rendered)
    run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
        args.out_root,
        rendered.get("model_package_id") or rendered.get("model_id") or "model",
        timestamp=args.timestamp or None,
    )
    summary = run_mock_search(
        rows=rows,
        rendered_package=rendered,
        out_dir=run_dir,
        population=args.population,
        gens=args.gens,
        candidate_k=args.candidate_k,
        llm_mode=args.llm_mode,
        det_threshold=args.det_threshold,
        search_mode=search_mode,
    )
    search_input, decomposed_blocks = build_search_input(rendered, search_mode)
    advisor_result = None
    if args.advisor_mode != "none" or args.prompt_patches:
        advisor_result = run_advisor_for_ga_search(
            advisor_mode=args.advisor_mode,
            advisor_dir=run_dir / "advisor",
            search_mode=search_mode,
            strict_results_dir=args.strict_results_dir or None,
            local_det_report=args.local_det_report or None,
            cloud_judge_csv=args.cloud_judge_csv or None,
            advisor_rich_feedback=args.advisor_rich_feedback or None,
            prompt_patches=args.prompt_patches or None,
            top_k=args.advisor_top_k,
            dry_run=args.dry_run_advisor or args.advisor_llm_mode == "mock",
            population_size=args.population_size,
        )
    candidate_manifest = write_candidate_artifacts(
        run_dir,
        search_mode=search_mode,
        advisor_mode=args.advisor_mode,
        candidates=advisor_result.get("candidate_records", []) if advisor_result else None,
    )
    manifest = save_search_artifacts(
        run_dir,
        rendered_package=rendered,
        search_input=search_input,
        search_mode=search_mode,
        advisor_mode=args.advisor_mode,
        decomposed_blocks=decomposed_blocks,
        advisor_summary=advisor_result,
        candidate_manifest=candidate_manifest,
    )
    manifest["ga_summary"] = summary
    (run_dir / "ga_run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.print_mode != "none" or args.print_summary:
        print(json.dumps({"out_dir": str(run_dir), **summary}, ensure_ascii=False, indent=2))
    return 0


def run_check_cmd(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else None
    result = run_check(args.check, out_dir=out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"PASS", "WARN"} else 1


def run_advisor_cmd(args: argparse.Namespace) -> int:
    rendered = render_for_args(args)
    run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
        args.out_root,
        rendered.get("model_package_id") or rendered.get("model_id") or "model",
        timestamp=args.timestamp or None,
    )
    result = run_advisor_for_ga_search(
        advisor_mode=args.advisor_mode,
        advisor_dir=run_dir / "advisor",
        search_mode=effective_search_mode(args, rendered),
        strict_results_dir=args.strict_results_dir or None,
        local_det_report=args.local_det_report or None,
        cloud_judge_csv=args.cloud_judge_csv or None,
        advisor_rich_feedback=args.advisor_rich_feedback or None,
        prompt_patches=args.prompt_patches or None,
        top_k=args.advisor_top_k,
        dry_run=args.dry_run_advisor or args.advisor_llm_mode == "mock",
        population_size=args.population_size,
    )
    print(json.dumps({"advisor_dir": result["advisor_dir"], **result["summary"]}, ensure_ascii=False, indent=2))
    return 0


def print_summary(manifest: dict[str, Any], search_input: dict[str, Any], advisor_summary: dict[str, Any] | None) -> None:
    print("GA search artifact summary")
    print(f"- run_dir: {manifest.get('run_dir')}")
    print(f"- search_mode: {manifest.get('search_mode')}")
    print(f"- model_render_mode: {manifest.get('model_render_mode')}")
    if search_input.get("search_mode") == "blocks":
        print(f"- block_count: {search_input.get('block_count')}")
        print(f"- block_source: {search_input.get('source')}")
        print(f"- prompt_text_preserved: {search_input.get('prompt_text_preserved')}")
    else:
        print(f"- prompt_length_chars: {search_input.get('prompt_length_chars')}")
    if advisor_summary:
        print(f"- advisor_mode: {advisor_summary.get('advisor_mode')}")
        print(f"- advisor_primary_signal: {advisor_summary.get('summary', {}).get('primary_signal')}")
        print(f"- prompt_patches: {advisor_summary.get('summary', {}).get('prompt_patches')}")
        print(f"- population_candidates: {advisor_summary.get('summary', {}).get('population_candidates')}")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] not in COMMANDS:
        args = build_flat_parser().parse_args(argv)
        if not args.model and not args.model_package:
            raise SystemExit("flat mode requires --model-package or --model")
        if args.search_mode == "auto":
            args.search_mode = "monolith"
        return run_prepare_like(args)

    args = build_parser().parse_args(argv)
    if args.command == "render":
        return run_render(args)
    if args.command == "eval":
        return run_eval(args)
    if args.command == "search":
        return run_search(args)
    if args.command == "advisor":
        return run_advisor_cmd(args)
    if args.command == "check":
        return run_check_cmd(args)
    raise SystemExit(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
