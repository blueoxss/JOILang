#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .advisor_integration import run_advisor_for_ga_search
    from .advisor_modes import validate_advisor_mode
    from .artifacts import default_run_dir, save_search_artifacts, write_candidate_artifacts
    from .block_search import build_blocks_search_input
    from .monolith_search import build_monolith_search_input
    from .render_adapter import render_model_package
except ImportError:
    from advisor_integration import run_advisor_for_ga_search  # type: ignore
    from advisor_modes import validate_advisor_mode  # type: ignore
    from artifacts import default_run_dir, save_search_artifacts, write_candidate_artifacts  # type: ignore
    from block_search import build_blocks_search_input  # type: ignore
    from monolith_search import build_monolith_search_input  # type: ignore
    from render_adapter import render_model_package  # type: ignore


def parse_json_arg(value: str | None, *, default: Any) -> Any:
    if value is None or str(value).strip() == "":
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON argument: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare repository-wide GA search artifacts from a JOILang model package."
    )
    parser.add_argument("--model-package", required=True)
    parser.add_argument("--search-mode", required=True, choices=["monolith", "blocks"])
    parser.add_argument("--advisor-mode", default="none", choices=["none", "local", "cloud", "hybrid"])
    parser.add_argument("--strict-results-dir", default="")
    parser.add_argument("--local-det-report", default="")
    parser.add_argument("--cloud-judge-csv", default="")
    parser.add_argument("--advisor-rich-feedback", default="")
    parser.add_argument("--prompt-patches", default="")
    parser.add_argument("--advisor-top-k", type=int, default=20)
    parser.add_argument("--population-size", type=int, default=12)
    parser.add_argument("--dry-run-advisor", action="store_true")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--out-root", default="artifacts/ga_search")
    parser.add_argument("--timestamp", default="")
    parser.add_argument("--user-input", default="Turn on the light.")
    parser.add_argument("--connected-devices-json", default="")
    parser.add_argument("--other-params-json", default="")
    parser.add_argument("--model-key", default="")
    parser.add_argument("--print-summary", action="store_true")
    return parser


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


def main() -> int:
    args = build_parser().parse_args()
    advisor_mode = validate_advisor_mode(args.advisor_mode)
    connected_devices = parse_json_arg(args.connected_devices_json, default={})
    other_params = parse_json_arg(args.other_params_json, default={})
    rendered_package = render_model_package(
        args.model_package,
        args.user_input,
        connected_devices=connected_devices,
        other_params=other_params,
    )

    if args.search_mode == "monolith":
        search_input = build_monolith_search_input(rendered_package)
        decomposed_blocks = None
    else:
        search_input = build_blocks_search_input(rendered_package)
        decomposed_blocks = search_input.get("blocks", [])

    run_dir = Path(args.out_dir) if args.out_dir else default_run_dir(
        args.out_root,
        rendered_package.get("model_package_id") or Path(args.model_package).name,
        timestamp=args.timestamp or None,
    )
    advisor_result = None
    candidate_records = None
    if advisor_mode != "none" or args.prompt_patches:
        advisor_result = run_advisor_for_ga_search(
            advisor_mode=advisor_mode,
            advisor_dir=run_dir / "advisor",
            search_mode=args.search_mode,
            strict_results_dir=args.strict_results_dir or None,
            local_det_report=args.local_det_report or None,
            cloud_judge_csv=args.cloud_judge_csv or None,
            advisor_rich_feedback=args.advisor_rich_feedback or None,
            prompt_patches=args.prompt_patches or None,
            top_k=args.advisor_top_k,
            dry_run=args.dry_run_advisor,
            population_size=args.population_size,
        )
        candidate_records = advisor_result.get("candidate_records", [])

    candidate_manifest = write_candidate_artifacts(
        run_dir,
        search_mode=args.search_mode,
        advisor_mode=advisor_mode,
        candidates=candidate_records,
    )
    manifest = save_search_artifacts(
        run_dir,
        rendered_package=rendered_package,
        search_input=search_input,
        search_mode=args.search_mode,
        advisor_mode=advisor_mode,
        decomposed_blocks=decomposed_blocks,
        advisor_summary=advisor_result,
        candidate_manifest=candidate_manifest,
    )
    if args.model_key:
        manifest["model_key"] = args.model_key
        (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.print_summary:
        print_summary(manifest, search_input, advisor_result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
