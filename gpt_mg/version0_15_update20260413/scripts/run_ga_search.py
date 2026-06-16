#!/usr/bin/env python3
# Assumption: this GA search mutates prompt-block artifacts only; retrieval context is fixed at runtime.
from __future__ import annotations

import argparse
from email import parser
import json
import math
import random
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.run_feedback_loop import evaluate_genome_on_rows, run_feedback_loop
from scripts.run_model_suite_benchmark import PAPER_LOCAL5_SUITE
from scripts.ga_metrics import (
    GenomeMetricBundle,
    assign_pareto,
    best_tie_key,
    metrics_from_evaluation,
    one_row_margin,
    pareto_rows as build_pareto_rows,
    pareto_summary as build_pareto_summary,
)
from scripts.ga_mutation import (
    COMPRESSION_MUTATION_TYPES,
    apply_mutation_proposal,
    mutation_family_for_phase,
    proposal_for_family,
)
from scripts.ga_selection import (
    ArchiveState,
    metric_of,
    quota_elites,
    regression_gate,
    update_archives,
)
from scripts.ga_stop_controller import decide_next_action
from scripts.advisor_feedback import (
    apply_advisor_proposal,
    build_advisor_feedback_batch,
    build_advisor_prompt_from_batch,
    validate_advisor_proposal,
)
from scripts.mutation_proposals import (
    PROPOSAL_STATE_ACCEPTED_APPLIED,
    PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED,
    PROPOSAL_STATE_FAILED_TO_APPLY,
    PROPOSAL_STATE_PROPOSED,
    PROPOSAL_STATE_REJECTED,
    MutationProposal,
    proposal_from_advisor,
)
from scripts.prompt_decompiler import compression_proposals_from_artifact, decompile_prompt
from utils.ga_block_model import (
    get_core_blocks,
    get_optional_blocks,
    active_block_summary,
    feedback_records_from_rows,
    normalize_active_blocks,
    suggest_mutation_from_feedback,
    summarize_deterministic_feedback,
    validate_genome_blocks,
)
from utils.local_llm_client import call as call_llm
from utils.pipeline_common import (
    BLOCKS_DIR,
    BLOCK_FILE_MAP,
    DATASET_DEFAULT,
    RESULTS_DIR,
    SERVICE_SCHEMA_DEFAULT,
    atomic_write_csv,
    dump_json,
    ensure_workspace,
    load_dataset_rows,
    load_genome,
    load_service_schema,
    sample_rows,
    seeded_uuid,
    select_rows,
)
from utils.prompt_surgery_rules import det_feedback_rules, prompt_surgery_registry


MUTATION_RULES = [
    "Prefer canonical_name exactly when available.",
    "Use value entries in conditions and function entries in actions.",
    "For INTEGER and DOUBLE arguments, avoid quoted numeric literals.",
    "Return exactly one JSON object only with keys name, cron, period, code.",
    "Keep the code minimal and remove unrelated actions.",
]

CANONICAL_OPTIONAL_BLOCKS = get_optional_blocks()
DET_PASS_THRESHOLD = 70.0
DEFAULT_STRATEGIES = ["direct", "minimal", "canonical_names_first", "explicit_preconditions", "compact_json"]
PROMOTION_COLUMNS = [
    "generation",
    "candidate_id",
    "model_key",
    "DETPass",
    "SDET",
    "avg_prompt_tokens",
    "replay_gate_pass",
    "regression_gate_pass",
    "promoted",
    "rejection_reason",
    "accepted_prompt_path",
    "previous_accepted_prompt",
]
TOKEN_FEEDBACK_COLUMNS = [
    "failure_type",
    "generation",
    "model_key",
    "genome_id",
    "source_prompt_tokens",
    "baseline_token_budget",
    "derived_target_budget",
    "compression_strength",
    "peak_vram_gb",
    "attempted_allocation_gb",
    "row_id",
    "tokenizer_status",
    "token_count_status",
    "source_prompt_chars",
    "timestamp",
]
TOKEN_MUTATION_COLUMNS = [
    "generation",
    "model_key",
    "genome_id",
    "parent_id",
    "mutation_type",
    "compression_strategy",
    "compression_strength",
    "source_failure_type",
    "source_prompt_tokens",
    "baseline_token_budget",
    "derived_target_budget",
    "preserved_core_blocks",
    "removed_optional_blocks",
    "summarized_blocks",
    "few_shot_before",
    "few_shot_after",
    "estimated_prompt_tokens",
    "actual_prompt_tokens",
    "token_count_status",
    "compression_family",
    "compressed_child_of",
    "preserved_parent",
    "parent_preserved_in_generation",
    "skip_reason",
    "timestamp",
]
COMPRESSION_CHILD_COLUMNS = [
    "generation",
    "model_key",
    "child_genome_id",
    "parent_id",
    "compression_strategy",
    "compression_strength",
    "source_failure_type",
    "source_prompt_tokens",
    "baseline_token_budget",
    "derived_target_budget",
    "estimated_prompt_tokens",
    "actual_prompt_tokens",
    "preserved_core_blocks",
    "removed_optional_blocks",
    "summarized_blocks",
    "few_shot_before",
    "few_shot_after",
    "token_count_status",
    "compression_family",
    "compressed_child_of",
    "parent_preserved_in_generation",
    "timestamp",
]
PARETO_COLUMNS = [
    "generation",
    "genome_id",
    "model_key",
    "det",
    "det_pass_rate",
    "sdet",
    "avg_prompt_tokens",
    "warm_latency_p50",
    "peak_vram_gb",
    "oom_count",
    "failure_rate",
    "is_pareto_frontier",
    "newly_discovered_frontier",
    "dominated_by",
    "pareto_rank",
    "knee_candidate",
    "pareto_status",
]
PARETO_SUMMARY_COLUMNS = [
    "generation",
    "model_key",
    "new_frontier",
    "frontier_size",
    "best_det",
    "best_det_genome_id",
    "best_tokens",
    "best_tokens_genome_id",
    "knee_candidate",
    "pareto_status",
    "oom_resolved",
    "overbudget_children",
]
TOKEN_FAILURE_SEVERITY = {
    "cuda_oom": 100,
    "context_length_exceeded": 95,
    "max_context_exceeded": 95,
    "cold_load_oom": 90,
    "warm_generation_oom": 90,
    "prompt_token_over_budget": 80,
    "gpu_memory_over_budget": 70,
    "tokenizer_failure": 60,
}
COMPRESSION_STRATEGIES = [
    "drop_optional_blocks_for_budget",
    "summarize_optional_block",
    "reduce_few_shot_count",
    "compress_micro_rules",
    "simplify_candidate_strategies",
    "lower_max_tokens",
    "compress_block_family",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run genetic search over version0_15 prompt-block artifact genomes.")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--genome-json", default=str(VERSION_ROOT / "genomes" / "example_genome.json"))
    parser.add_argument("--dataset", default=str(DATASET_DEFAULT))
    parser.add_argument("--service-schema", default=str(SERVICE_SCHEMA_DEFAULT))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--start-row", type=int, default=1)
    parser.add_argument("--end-row", type=int, default=None)
    parser.add_argument("--category", action="append", default=[], help="Filter by dataset category. Can be repeated or comma-separated.")
    parser.add_argument("--limit-per-category", type=int, default=None)
    parser.add_argument("--population", type=int, default=20)
    parser.add_argument("--gens", type=int, default=30)
    parser.add_argument("--crossover-rate", type=float, default=0.6)
    parser.add_argument("--mutation-rate", type=float, default=0.2)
    parser.add_argument("--elites", type=int, default=2)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--cheap-eval-limit", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=2)
    parser.add_argument("--repair-attempts", type=int, default=0, help="Compatibility guard; GA core currently evaluates direct candidates only.")
    parser.add_argument("--validation-size", type=int, default=8)
    parser.add_argument("--alpha", type=float, default=0.5)
    parser.add_argument("--plateau-generations", type=int, default=3)
    parser.add_argument("--feedback-attempts", type=int, default=3)
    parser.add_argument("--feedback-threshold", type=float, default=0.25)
    parser.add_argument("--det-profile", choices=["legacy", "strict"], default="strict")
    parser.add_argument("--model-key", default="", help="Optional paper local model key, e.g. qwen25_coder_7b.")
    parser.add_argument("--output-root", default="", help="GA run output directory. Default: results/ga_search_<timestamp>.")
    parser.add_argument("--feedback-guided-mutation", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--progress", choices=["quiet", "minimal", "verbose"], default="minimal")
    parser.add_argument("--print-prompts", action="store_true", help="Reserved debugging flag. GA never prints prompts unless this is set.")
    parser.add_argument("--dry-run", action="store_true", help="Validate GA setup and write initial artifacts without LLM calls.")
    parser.add_argument("--smoke", action="store_true", help="Run the safe one-row GA smoke preset.")
    parser.add_argument("--small-category-smoke", action="store_true", help="Run categories 1 and 2 with at most two rows per category.")
    parser.add_argument("--small-ga-advisor-smoke", action="store_true", help="Run a tiny advisor-enabled smoke; uses mock advisor when no endpoint is configured.")
    parser.add_argument("--full-run", action="store_true", help="Allow long-running GA settings. Required for full-scale runs.")
    parser.add_argument("--resume", action="store_true", help="Resume into an existing output directory and keep stage status files.")
    parser.add_argument("--force", action="store_true", help="Allow writing into a non-empty output directory.")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--llm-mutation-advisor", action="store_true", help="Use an optional LLM advisor to propose prompt-block mutations.")
    parser.add_argument("--advisor-model-key", default="gpt41_mini")
    parser.add_argument("--advisor-llm-mode", choices=["openai", "mock", "worker"], default="openai", help="LLM backend for the mutation advisor. Keep separate from --llm-mode used by JOILang code generation.")
    parser.add_argument("--advisor-llm-endpoint",default="",help="Optional endpoint for advisor LLM calls. Empty means default OpenAI SDK/client path.")
    parser.add_argument("--advisor-top-k", type=int, default=3)
    parser.add_argument("--advisor-bottom-k", type=int, default=3)
    parser.add_argument("--advisor-max-examples", type=int, default=5)
    parser.add_argument("--advisor-temperature", type=float, default=0.0)
    parser.add_argument("--advisor-strict", action="store_true", help="Abort the GA run if the cloud advisor returns invalid JSON.")
    parser.add_argument("--advisor-max-representative-failures", type=int, default=10, help="Max representative failures per advisor batch packet.")
    parser.add_argument("--advisor-feedback-detail", choices=["compact", "normal", "verbose"], default="normal")
    parser.add_argument("--advisor-include-candidate-code", action=argparse.BooleanOptionalAction, default=True, help="Include candidate code in advisor representative failures.")
    parser.add_argument("--advisor-include-prompt-summary", action=argparse.BooleanOptionalAction, default=True, help="Include the current prompt/genome structure in the advisor batch.")
    parser.add_argument("--advisor-force-child-quota", action="store_true", help="Reserve an advisor child slot even when population < advisor-min-population-for-child.")
    parser.add_argument("--advisor-min-population-for-child", type=int, default=4, help="Minimum population required before advisor children are scheduled.")
    parser.add_argument("--advisor-compression-child-quota", type=int, default=1)
    parser.add_argument("--advisor-prefer-compression-after-detpass", type=float, default=90.0)
    parser.add_argument("--llm-mode", default=None)
    parser.add_argument("--llm-endpoint", default=None)
    parser.add_argument("--timeout-sec", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--seed", type=int, default=14)
    parser.add_argument("--token-budget", type=int, default=None, help="Global frozen prompt-token budget fallback for this GA run.")
    parser.add_argument("--model-token-budget-json", default="", help="Optional JSON mapping model_key to frozen prompt-token budget.")
    parser.add_argument("--auto-token-budget-from-oom", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--compression-strength", choices=["light", "medium", "aggressive"], default="medium")
    parser.add_argument("--compression-children-per-parent", type=int, default=3)
    parser.add_argument("--max-compression-children-per-gen", type=int, default=12)
    parser.add_argument("--max-compression-children-per-model", type=int, default=12)
    parser.add_argument("--preserve-topk-uncompressed", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--preserve-topk-count", type=int, default=3)
    parser.add_argument("--min-core-blocks", default="01,02")
    parser.add_argument("--pareto-selection", action="store_true", help="Reserved; default GA selection remains fitness-based.")
    parser.add_argument("--inject-mock-token-feedback", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--selection-mode", choices=["legacy", "redesign"], default="legacy")
    parser.add_argument("--fitness-mode", choices=["legacy", "detpass_token", "phase_aware"], default="legacy")
    parser.add_argument("--category-balance-mode", choices=["off", "guard", "fitness", "routing"], default="off")
    parser.add_argument("--token-penalty-mode", choices=["off", "budget", "accepted", "hybrid"], default="off")
    parser.add_argument("--target-detpass", type=float, default=95.0)
    parser.add_argument("--compression-detpass-threshold", type=float, default=90.0)
    parser.add_argument("--aggressive-compression-after-target", action="store_true")
    parser.add_argument("--compression-child-quota", type=int, default=1)
    parser.add_argument("--compression-child-ratio", type=float, default=0.2)
    parser.add_argument("--compression-token-reduction-target", type=float, default=0.15)
    parser.add_argument("--compression-token-plateau-delta", type=float, default=1.0)
    parser.add_argument("--allow-aggressive-compression", action="store_true")
    parser.add_argument("--micro-compression-child-quota", type=int, default=1)
    parser.add_argument("--micro-compression-child-ratio", type=float, default=0.05)
    parser.add_argument("--block-compression-child-quota", type=int, default=1)
    parser.add_argument("--block-compression-child-ratio", type=float, default=0.2)
    parser.add_argument("--multi-block-compression-child-quota", type=int, default=1)
    parser.add_argument("--multi-block-compression-child-ratio", type=float, default=0.2)
    parser.add_argument("--global-budget-compression-child-quota", type=int, default=0)
    parser.add_argument("--enable-block-token-breakdown", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-multi-block-compression", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-render-budget-compression", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--min-compression-token-delta", type=int, default=32)
    parser.add_argument("--detpass-row-margin", type=float, default=0.0)
    parser.add_argument("--fitness-token-weight-min", type=float, default=0.0)
    parser.add_argument("--fitness-token-weight-max", type=float, default=2.0)
    parser.add_argument("--fitness-regression-weight", type=float, default=2.0)
    parser.add_argument("--fitness-category-weight", type=float, default=0.05)
    parser.add_argument("--fitness-avgdet-weight", type=float, default=0.20)
    parser.add_argument("--fitness-variance-weight", type=float, default=0.05)
    parser.add_argument("--preserve-global-best", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--enable-pareto-archive", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-group-specialist-archives", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--mutation-mode", choices=["legacy", "family", "cloudless_decompiler", "hybrid"], default="legacy")
    parser.add_argument("--enable-compression-mutation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-prompt-decompiler", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--compression-min-token-reduction", type=float, default=0.05)
    parser.add_argument("--compression-detpass-margin-rows", type=int, default=1)
    parser.add_argument("--enable-rendered-prompt-dedupe", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--enable-operator-credit", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--reasoning-mutation-mode", choices=["off", "compact", "skeleton", "auto"], default="off")
    parser.add_argument("--intent-hint-mode", choices=["none", "keyword_list", "json_hint", "typed_slots", "auto"], default="none")
    parser.add_argument("--stop-controller-mode", choices=["legacy", "active"], default="legacy")
    parser.add_argument("--min-generations", type=int, default=3)
    parser.add_argument("--max-generations", type=int, default=None)
    parser.add_argument("--plateau-window", type=int, default=3)
    parser.add_argument("--disruptive-max-attempts", type=int, default=2)
    parser.add_argument("--advisor-trigger-mode", choices=["off", "on_plateau", "on_failure_plateau", "on_compression", "always"], default="off")
    parser.add_argument("--diversity-collapse-threshold", type=float, default=0.5)
    return parser


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_output_root(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return (RESULTS_DIR / f"ga_search_{_timestamp()}").resolve()


def _has_stage_flag(args: argparse.Namespace) -> bool:
    return bool(args.dry_run or args.smoke or args.small_category_smoke or args.small_ga_advisor_smoke)


def _normalize_stage_args(args: argparse.Namespace) -> argparse.Namespace:
    if not args.full_run and not _has_stage_flag(args):
        args.dry_run = True
        args.stage_name = "dry-run"
        args.stage_defaulted = True
    else:
        args.stage_defaulted = False

    if args.dry_run:
        args.stage_name = getattr(args, "stage_name", "dry-run")
    elif args.small_ga_advisor_smoke:
        args.stage_name = "ga-advisor-smoke"
        args.llm_mutation_advisor = True
        if not args.llm_mode and not args.llm_endpoint:
            args.llm_mode = "mock"
        args.model_key = args.model_key or "qwen25_coder_7b"
        args.limit = min(args.limit or 2, 2)
        args.population = min(args.population, 4)
        args.gens = min(args.gens, 2)
        args.sample_size = min(args.sample_size, 2)
        args.validation_size = min(args.validation_size, 2)
        args.cheap_eval_limit = min(args.cheap_eval_limit, 1)
        args.candidate_k = 1
        args.mutation_rate = 1.0
        args.repair_attempts = 0
    elif args.small_category_smoke:
        args.stage_name = "category-smoke"
        args.model_key = args.model_key or "qwen25_coder_7b"
        args.category = args.category or ["1", "2"]
        args.limit_per_category = min(args.limit_per_category or 2, 2)
        args.population = min(args.population, 4)
        args.gens = min(args.gens, 2)
        args.sample_size = min(args.sample_size, 4)
        args.validation_size = min(args.validation_size, 4)
        args.cheap_eval_limit = min(args.cheap_eval_limit, 2)
        args.candidate_k = 1
        args.mutation_rate = 1.0
        args.repair_attempts = 0
    elif args.smoke:
        args.stage_name = "one-row-smoke"
        args.model_key = args.model_key or "qwen25_coder_7b"
        args.limit = min(args.limit or 1, 1)
        args.population = min(args.population, 4)
        args.gens = min(args.gens, 2)
        args.sample_size = min(args.sample_size, 1)
        args.validation_size = min(args.validation_size, 1)
        args.cheap_eval_limit = min(args.cheap_eval_limit, 1)
        args.candidate_k = 1
        args.mutation_rate = 1.0
        args.repair_attempts = 0
    else:
        args.stage_name = "full-run" if args.full_run else "dry-run"

    if not args.full_run:
        args.population = min(args.population, 4)
        args.gens = min(args.gens, 2)
        args.candidate_k = min(args.candidate_k, 1)
        args.repair_attempts = 0
    return args


def _guard_output_root(output_root: Path, args: argparse.Namespace) -> None:
    if args.resume or args.force:
        return
    if output_root.exists() and any(output_root.iterdir()):
        raise SystemExit(
            f"Output directory already exists and is not empty: {output_root}. "
            "Use --resume or --force, or choose a new --output-root."
        )


def _write_stage_status(output_root: Path, stage: str, status: str, details: dict[str, Any] | None = None) -> None:
    payload = {
        "stage": stage,
        "status": status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **(details or {}),
    }
    dump_json(output_root / "stage_status" / f"{stage}.json", payload)


def _print_stage(args: argparse.Namespace, stage: str, status: str) -> None:
    if args.progress != "quiet":
        print(f"[STAGE] {stage} {status}", flush=True)


def _final_artifacts(summary: dict[str, Any]) -> list[tuple[str, str]]:
    output_root = Path(str(summary.get("output_root", "")))
    return [
        ("ga_generation_progress.csv", str(summary.get("generation_progress_csv") or output_root / "ga_generation_progress.csv")),
        ("ga_topk_genomes.csv", str(summary.get("topk_genomes_csv") or output_root / "ga_topk_genomes.csv")),
        ("ga_block_diffs.jsonl", str(summary.get("block_diffs_jsonl") or output_root / "ga_block_diffs.jsonl")),
        ("ga_population_diagnostics.csv", str(summary.get("population_diagnostics_csv") or output_root / "ga_population_diagnostics.csv")),
        ("structured_feedback.jsonl", str(summary.get("structured_feedback_jsonl") or output_root / "structured_feedback.jsonl")),
        ("advisor_feedback_batches.jsonl", str(summary.get("advisor_feedback_batches_jsonl") or output_root / "advisor_feedback_batches.jsonl")),
        ("mutation_proposals.jsonl", str(summary.get("mutation_proposals_jsonl") or output_root / "mutation_proposals.jsonl")),
        ("pareto_archive.csv", str(summary.get("pareto_archive_csv") or output_root / "pareto_archive.csv")),
        ("mutation_operator_credit.csv", str(summary.get("mutation_operator_credit_csv") or output_root / "mutation_operator_credit.csv")),
        ("advisor_mutation_proposals.jsonl", str(summary.get("advisor_mutation_proposals_jsonl") or output_root / "advisor_mutation_proposals.jsonl")),
        ("population_transitions.csv", str(summary.get("population_transitions_csv") or output_root / "population_transitions.csv")),
        ("promotion_decisions.csv", str(summary.get("promotion_decisions_csv") or output_root / "promotion_decisions.csv")),
        ("best_genome.json", str(output_root / "best_genome.json")),
        ("ga_summary.json", str(output_root / "ga_summary.json")),
    ]


def _model_name_for_key(model_key: str) -> str:
    if not model_key:
        return ""
    for entry in PAPER_LOCAL5_SUITE:
        if entry["key"] == model_key:
            return str(entry["model"])
    raise SystemExit(f"Unknown --model-key {model_key!r}. Available: {[entry['key'] for entry in PAPER_LOCAL5_SUITE]}")


def _model_label_for_key(model_key: str) -> str:
    for entry in PAPER_LOCAL5_SUITE:
        if entry["key"] == model_key:
            return str(entry.get("label") or entry["key"])
    if model_key == "gpt41_mini":
        return "GPT-4.1-mini"
    return model_key


def _advisor_model_name(model_key: str) -> str:
    if model_key == "gpt41_mini":
        return "gpt-4.1-mini"
    for entry in PAPER_LOCAL5_SUITE:
        if entry["key"] == model_key:
            return str(entry["model"])
    return model_key


def _copy_genome(genome: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(genome))


def _normalize_blocks(blocks: list[str]) -> list[str]:
    return normalize_active_blocks(blocks)


def _annotate_genome(
    genome: dict[str, Any],
    *,
    parent_ids: list[str] | None = None,
    mutation_types: list[str] | None = None,
    crossover_used: bool = False,
    feedback_types_used: list[str] | None = None,
    base_genome_id: str = "",
    advisor_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    genome.setdefault("_ga_metadata", {})
    metadata = {
        "parent_ids": parent_ids or [],
        "mutation_types": mutation_types or [],
        "crossover_used": crossover_used,
        "feedback_types_used": feedback_types_used or [],
        "base_genome_id": base_genome_id,
    }
    if advisor_metadata:
        metadata.update(advisor_metadata)
    genome["_ga_metadata"].update(metadata)
    return validate_genome_blocks(genome)


def _random_genome(base_genome: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    genome = _copy_genome(base_genome)
    genome["id"] = f"gen-{seeded_uuid(rng)}"
    genome["seed"] = rng.randint(1, 10**9)
    genome.setdefault("params", {})
    genome.setdefault("block_params", {})
    blocks = get_core_blocks()
    for block in CANONICAL_OPTIONAL_BLOCKS:
        if rng.random() < 0.75:
            blocks.append(block)
    genome["blocks"] = _normalize_blocks(blocks)
    genome["params"]["temperature"] = rng.choice([0.0, 0.0, 0.05, 0.1])
    genome["params"]["max_tokens"] = rng.choice([512, 768, 1024])
    genome["params"]["candidate_strategies"] = rng.sample(DEFAULT_STRATEGIES, k=rng.randint(2, 5))
    block02 = genome.setdefault("block_params", {}).setdefault("02", {})
    block02["few_shot_count"] = rng.choice([1, 2, 3])
    block02["micro_rules"] = rng.sample(MUTATION_RULES, k=rng.randint(0, min(3, len(MUTATION_RULES))))
    return _annotate_genome(genome, mutation_types=["initial_random"])


def _mutation_rule_from_feedback(feedback_hint: dict[str, str] | None) -> tuple[str, str, str]:
    if not feedback_hint:
        return "micro_rules", "", ""
    return (
        str(feedback_hint.get("suggested_mutation_type", "feedback_guided_rule")),
        str(feedback_hint.get("prompt_block_id", "02") or "02"),
        str(feedback_hint.get("rule", "") or ""),
    )


def _block_variant_sources(block_id: str) -> list[str]:
    default = BLOCK_FILE_MAP.get(block_id, "")
    sources = [default] if default else []
    prefixes = [f"{block_id}_"]
    if default:
        prefixes.append(Path(default).stem)
    generated_dir = BLOCKS_DIR / "generated"
    if generated_dir.exists():
        for path in sorted(generated_dir.glob("**/*")):
            if not path.is_file() or path.suffix.lower() not in {".txt", ".md"}:
                continue
            rel = str(path.relative_to(BLOCKS_DIR))
            name = path.name
            if any(name.startswith(prefix) for prefix in prefixes) and rel not in sources:
                sources.append(rel)
    return sources


def _mutate_genome(
    genome: dict[str, Any],
    rng: random.Random,
    *,
    feedback_hint: dict[str, str] | None = None,
    advisor_proposal: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    child = _copy_genome(genome)
    child["id"] = f"gen-{seeded_uuid(rng)}"
    child["seed"] = rng.randint(1, 10**9)
    child.setdefault("params", {})
    child.setdefault("block_params", {})
    diffs: list[dict[str, Any]] = []
    parent_id = str(genome.get("id", ""))
    old_child = _copy_genome(child)
    feedback_types_used: list[str] = []
    if feedback_hint:
        mutation_choice, target_block, feedback_rule = _mutation_rule_from_feedback(feedback_hint)
        feedback_types_used = [str(feedback_hint.get("failure_type", ""))]
    else:
        mutation_choice = rng.choice(
            [
                "block_activation",
                "block_deactivation",
                "block_replacement",
                "repair_block_insertion",
                "repair_block_removal",
                "few_shot",
                "max_tokens",
                "temperature",
                "micro_rules",
                "strategies",
            ]
        )
        target_block = rng.choice(CANONICAL_OPTIONAL_BLOCKS)
        feedback_rule = ""

    if mutation_choice in {"block_activation", "activate_or_strengthen_temporal_rule"}:
        blocks = list(child.get("blocks", []))
        if target_block not in blocks and target_block in CANONICAL_OPTIONAL_BLOCKS:
            blocks.append(target_block)
        child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice == "block_deactivation":
        target = rng.choice(list(CANONICAL_OPTIONAL_BLOCKS))
        blocks = list(child.get("blocks", ["01", "02", "03", "06"]))
        if target in blocks:
            blocks.remove(target)
        child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice == "block_replacement":
        active_optional = active_block_summary(child)["optional"]
        block_id = rng.choice(active_optional) if active_optional else rng.choice(CANONICAL_OPTIONAL_BLOCKS)
        variants = _block_variant_sources(block_id)
        current_source = str(child.get("block_params", {}).get(block_id, {}).get("source_file") or BLOCK_FILE_MAP.get(block_id, ""))
        alternatives = [source for source in variants if source != current_source]
        if alternatives:
            child["block_params"].setdefault(block_id, {})["source_file"] = rng.choice(alternatives)
            blocks = list(child.get("blocks", []))
            if block_id not in blocks:
                blocks.append(block_id)
            child["blocks"] = _normalize_blocks(blocks)
        else:
            blocks = list(child.get("blocks", []))
            if block_id in blocks:
                blocks.remove(block_id)
            else:
                blocks.append(block_id)
            child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice in {"repair_clause", "repair_block_insertion", "add_repair_block"}:
        blocks = list(child.get("blocks", []))
        if "05" not in blocks:
            blocks.append("05")
        child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice in {"repair_block_removal", "remove_repair_block"}:
        blocks = list(child.get("blocks", []))
        if "05" in blocks:
            blocks.remove("05")
        child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice in {
        "strengthen_json_only_rule",
        "add_schema_grounding_rule",
        "add_canonical_service_name_rule",
        "strengthen_enum_type_rule",
        "strengthen_temporal_rule",
        "strengthen_owner_device_rule",
        "add_sensor_to_action_flow_rule",
        "strengthen_skeleton_rule",
        "strengthen_minimality_rule",
        "strengthen_no_unrelated_action_rule",
        "add_micro_rule",
        "strengthen_rule",
        "add_targeted_repair_hint",
    }:
        block_id = target_block if target_block in {"02", "03", "06"} else "02"
        rules = list(child["block_params"].setdefault(block_id, {}).get("micro_rules") or [])
        if feedback_rule and feedback_rule not in rules:
            rules.append(feedback_rule)
        child["block_params"][block_id]["micro_rules"] = rules[-6:]
        if block_id in CANONICAL_OPTIONAL_BLOCKS:
            blocks = list(child.get("blocks", []))
            if block_id not in blocks:
                blocks.append(block_id)
            child["blocks"] = _normalize_blocks(blocks)
    elif mutation_choice == "few_shot":
        child["block_params"].setdefault("02", {})["few_shot_count"] = rng.choice([1, 2, 3])
    elif mutation_choice == "max_tokens":
        child["params"]["max_tokens"] = rng.choice([512, 768, 1024])
    elif mutation_choice == "temperature":
        child["params"]["temperature"] = rng.choice([0.0, 0.0, 0.05, 0.1])
    elif mutation_choice == "micro_rules":
        block_id = rng.choice(["02", "03", "06"])
        rules = list(child["block_params"].setdefault(block_id, {}).get("micro_rules") or [])
        rule = rng.choice(MUTATION_RULES)
        if rule not in rules:
            rules.append(rule)
        child["block_params"][block_id]["micro_rules"] = rules[-6:]
    elif mutation_choice == "strategies":
        child["params"]["candidate_strategies"] = rng.sample(DEFAULT_STRATEGIES, k=rng.randint(2, 5))
    advisor_metadata = None
    if advisor_proposal:
        advisor_metadata = {
            "advisor_used": True,
            "advisor_generation": advisor_proposal.get("advisor_generation", ""),
            "advisor_proposal_id": advisor_proposal.get("proposal_id", ""),
            "advisor_target_block": advisor_proposal.get("target_block_id", ""),
            "advisor_mutation_type": advisor_proposal.get("mutation_type", ""),
            "advisor_reason": advisor_proposal.get("reason", ""),
            "llm_advised": True,
        }
    child = _annotate_genome(
        child,
        parent_ids=[parent_id],
        mutation_types=[mutation_choice],
        crossover_used=bool((genome.get("_ga_metadata") or {}).get("crossover_used")),
        feedback_types_used=feedback_types_used,
        base_genome_id=parent_id,
        advisor_metadata=advisor_metadata,
    )
    diffs.extend(
        _diff_genomes(
            old_child,
            child,
            mutation_type=mutation_choice,
            feedback_hint=feedback_hint,
            advisor_proposal=advisor_proposal,
        )
    )
    child.setdefault("_ga_metadata", {})["diffs"] = diffs
    return child, diffs


def _crossover(parent_a: dict[str, Any], parent_b: dict[str, Any], rng: random.Random) -> tuple[dict[str, Any], dict[str, Any]]:
    child = _copy_genome(parent_a if rng.random() < 0.5 else parent_b)
    child["id"] = f"gen-{seeded_uuid(rng)}"
    child["seed"] = rng.randint(1, 10**9)
    child.setdefault("params", {})
    child.setdefault("block_params", {})

    blocks = get_core_blocks()
    optional_from_a: list[str] = []
    optional_from_b: list[str] = []
    for block_id in CANONICAL_OPTIONAL_BLOCKS:
        owner = parent_a if rng.random() < 0.5 else parent_b
        if block_id in owner.get("blocks", []):
            blocks.append(block_id)
            if owner is parent_a:
                optional_from_a.append(block_id)
            else:
                optional_from_b.append(block_id)
    child["blocks"] = _normalize_blocks(blocks)
    inherited_params: dict[str, str] = {}
    for key in {*(parent_a.get("params", {}).keys()), *(parent_b.get("params", {}).keys())}:
        owner = parent_a if rng.random() < 0.5 else parent_b
        if key in owner.get("params", {}):
            child["params"][key] = owner["params"][key]
            inherited_params[key] = str(owner.get("id", ""))

    # Mix candidate strategies instead of blindly taking one parent.
    strategies = []
    for parent in (parent_a, parent_b):
        for item in parent.get("params", {}).get("candidate_strategies", []) or []:
            if item not in strategies:
                strategies.append(item)
    if strategies:
        # Compression may reduce candidate_strategies to a single safe strategy.
        strategies = list(strategies or [])
        if len(strategies) == 0:
            child["params"]["candidate_strategies"] = ["minimal"]
        elif len(strategies) == 1:
            child["params"]["candidate_strategies"] = strategies
        else:
            upper = min(5, len(strategies))
            child["params"]["candidate_strategies"] = strategies[: rng.randint(2, upper)]

    for block_id in {*(parent_a.get("block_params", {}).keys()), *(parent_b.get("block_params", {}).keys())}:
        owner = parent_a if rng.random() < 0.5 else parent_b
        if block_id in owner.get("block_params", {}):
            child["block_params"][block_id] = _copy_genome(owner["block_params"][block_id])

    # Merge and deduplicate micro-rules for active blocks.
    for block_id in child.get("blocks", []):
        merged_rules: list[str] = []
        for parent in (parent_a, parent_b):
            for rule in parent.get("block_params", {}).get(block_id, {}).get("micro_rules", []) or []:
                if rule not in merged_rules:
                    merged_rules.append(rule)
        if merged_rules:
            child["block_params"].setdefault(block_id, {})["micro_rules"] = merged_rules[-6:]

    metadata = {
        "parent_a": parent_a.get("id", ""),
        "parent_b": parent_b.get("id", ""),
        "inherited_core_blocks": get_core_blocks(),
        "optional_from_a": optional_from_a,
        "optional_from_b": optional_from_b,
        "inherited_optional_blocks": active_block_summary(child)["optional"],
        "inherited_params": inherited_params,
        "crossover_type": "block_artifact_uniform",
    }
    child = _annotate_genome(
        child,
        parent_ids=[str(parent_a.get("id", "")), str(parent_b.get("id", ""))],
        mutation_types=[],
        crossover_used=True,
        base_genome_id=str(parent_a.get("id", "")),
    )
    child["_ga_metadata"]["crossover"] = metadata
    return child, metadata


def _tournament_select(population: list[dict[str, Any]], rng: random.Random, size: int = 3) -> dict[str, Any]:
    contenders = rng.sample(population, k=min(size, len(population)))
    contenders.sort(key=lambda item: (-float(item["fitness"]), float(item["variance"]), item["genome"]["id"]))
    return contenders[0]["genome"]


def _jsonish(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _diff_genomes(
    before: dict[str, Any],
    after: dict[str, Any],
    *,
    mutation_type: str,
    feedback_hint: dict[str, str] | None,
    advisor_proposal: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    feedback_driven = bool(feedback_hint)
    failure_source = str((feedback_hint or {}).get("failure_type", ""))
    llm_advised = bool(advisor_proposal)
    advisor_proposal_id = str((advisor_proposal or {}).get("proposal_id", ""))

    before_optional = active_block_summary(before)["optional"]
    after_optional = active_block_summary(after)["optional"]
    if before_optional != after_optional:
        rows.append(
            {
                "block_id": "optional",
                "field": "active_optional_blocks",
                "old_value": ",".join(before_optional),
                "new_value": ",".join(after_optional),
                "mutation_type": mutation_type,
                "feedback_driven": feedback_driven,
                "llm_advised": llm_advised,
                "advisor_proposal_id": advisor_proposal_id,
                "failure_type_source": failure_source,
            }
        )

    for key in sorted({*before.get("params", {}).keys(), *after.get("params", {}).keys()}):
        old_value = before.get("params", {}).get(key, "")
        new_value = after.get("params", {}).get(key, "")
        if old_value != new_value:
            rows.append(
                {
                    "block_id": "params",
                    "field": key,
                    "old_value": _jsonish(old_value),
                    "new_value": _jsonish(new_value),
                    "mutation_type": mutation_type,
                    "feedback_driven": feedback_driven,
                    "llm_advised": llm_advised,
                    "advisor_proposal_id": advisor_proposal_id,
                    "failure_type_source": failure_source,
                }
            )

    before_params = before.get("block_params", {}) or {}
    after_params = after.get("block_params", {}) or {}
    for block_id in sorted({*before_params.keys(), *after_params.keys()}):
        old_block = before_params.get(block_id, {}) or {}
        new_block = after_params.get(block_id, {}) or {}
        for field in sorted({*old_block.keys(), *new_block.keys()}):
            old_value = old_block.get(field, "")
            new_value = new_block.get(field, "")
            if old_value != new_value:
                rows.append(
                    {
                        "block_id": block_id,
                        "field": field,
                        "old_value": _jsonish(old_value),
                        "new_value": _jsonish(new_value),
                        "mutation_type": mutation_type,
                        "feedback_driven": feedback_driven,
                        "llm_advised": llm_advised,
                        "advisor_proposal_id": advisor_proposal_id,
                        "failure_type_source": failure_source,
                    }
                )
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")

def _write_cloud_advisor_prompt_artifacts(
    *,
    output_root: Path,
    generation: int,
    prompt_text: str,
    advisor_batch: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, str]:
    """Write the exact final cloud-advisor prompt and its source packet.

    This is analogous to config_loader.py's merged_system_prompt_*.md dump,
    but advisor prompts are generation-dependent because they include DET
    feedback, token breakdown, block breakdown, and staged compression state.
    """
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    gen = int(generation)

    prompt_path = output_root / f"cloud_advisor_prompt_generation_{gen:03d}.md"
    packet_path = output_root / f"cloud_advisor_feedback_packet_generation_{gen:03d}.json"
    meta_path = output_root / f"cloud_advisor_prompt_meta_generation_{gen:03d}.json"

    prompt_path.write_text(prompt_text, encoding="utf-8")

    dump_json(packet_path, advisor_batch)

    meta = {
        "generation": gen,
        "advisor_model_key": str(args.advisor_model_key),
        "advisor_model": _advisor_model_name(str(args.advisor_model_key)),
        "advisor_feedback_detail": str(args.advisor_feedback_detail),

        "generation_llm_mode": str(args.llm_mode or ""),
        "advisor_llm_mode": str(getattr(args, "advisor_llm_mode", "openai") or "openai"),
        "advisor_llm_endpoint": str(getattr(args, "advisor_llm_endpoint", "") or ""),

        "compression_ready": bool(getattr(args, "_compression_ready", False)),
        "compression_phase": str(getattr(args, "_compression_phase", "")),
        "generation_phase": str(getattr(args, "_generation_phase", "")),
        "prompt_path": str(prompt_path),
        "feedback_packet_path": str(packet_path),
        "prompt_chars": len(prompt_text),
        "prompt_est_tokens_char4": _estimate_prompt_tokens(prompt_text),
        "written_at": datetime.now().isoformat(timespec="seconds"),
    }

    dump_json(meta_path, meta)

    return {
        "cloud_advisor_prompt_path": str(prompt_path),
        "cloud_advisor_feedback_packet_path": str(packet_path),
        "cloud_advisor_prompt_meta_path": str(meta_path),
    }

def _safe_read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_csv_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import csv
        with path.open("r", encoding="utf-8", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    except Exception:
        return []


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    except Exception:
        pass
    return rows


def _json_to_tuple(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_json_to_tuple(item) for item in value)
    if isinstance(value, dict):
        return {key: _json_to_tuple(item) for key, item in value.items()}
    return value


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


BLOCK_FAMILY_LABELS = {
    "01": "Core_System",
    "02": "Service_Mapping",
    "03": "Output_Schema",
    "05": "Repair_Clause",
    "06": "DET_Helper",
}


def _proposal_operator(proposal: dict[str, Any] | MutationProposal) -> str:
    if isinstance(proposal, MutationProposal):
        return str(proposal.operator or "")
    return str(proposal.get("exact_mutation_operator") or proposal.get("operator") or proposal.get("mutation_type") or "")


def _is_compression_proposal(proposal: dict[str, Any] | MutationProposal) -> bool:
    if isinstance(proposal, MutationProposal):
        return proposal.mutation_family == "compression" or proposal.operator in COMPRESSION_MUTATION_TYPES
    return (
        str(proposal.get("mutation_family", "") or "") == "compression"
        or _proposal_operator(proposal) in COMPRESSION_MUTATION_TYPES
    )


def _compression_fallback_enabled(args: argparse.Namespace) -> bool:
    return bool(
        args.llm_mutation_advisor
        or args.enable_compression_mutation
        or args.mutation_mode in {"family", "cloudless_decompiler", "hybrid"}
    )


def _estimate_prompt_tokens(text: str) -> int:
    return max(1, int(math.ceil(len(str(text or "")) / 4.0)))


def _block_source_text(genome: dict[str, Any], block_id: str) -> str:
    source = str((genome.get("block_params") or {}).get(block_id, {}).get("source_file") or BLOCK_FILE_MAP.get(block_id, ""))
    if not source:
        return ""
    path = BLOCKS_DIR / source
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except Exception:
        return ""


def _build_token_breakdowns(genome: dict[str, Any], *, generation: int, model_key: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    block_rows: list[dict[str, Any]] = []
    active_blocks = normalize_active_blocks(genome.get("blocks") or [])
    params = genome.get("params") or {}
    block_params = genome.get("block_params") or {}
    for block_id in active_blocks:
        source_text = _block_source_text(genome, block_id)
        params_text = json.dumps(block_params.get(block_id, {}) or {}, ensure_ascii=False, sort_keys=True)
        char_count = len(source_text) + len(params_text)
        token_estimate = _estimate_prompt_tokens(source_text + params_text)
        micro_rules = list((block_params.get(block_id, {}) or {}).get("micro_rules") or [])
        is_core = block_id in get_core_blocks()
        is_protected = is_core or block_id in {"02", "03"}
        safe_mutations = []
        if not is_protected:
            safe_mutations.extend([
                "reduce_few_shot_count_to_zero",
                "prune_micro_rules_to_top_k",
                "compact_block_params",
                "compact_reasoning_skeleton",
                "drop_optional_block",
            ])
        block_rows.append(
            {
                "generation": generation,
                "model_key": model_key,
                "block_id": block_id,
                "block_family": BLOCK_FAMILY_LABELS.get(block_id, "Unknown"),
                "block_role": "core" if is_core else "optional",
                "is_core_block": is_core,
                "is_protected_block": is_protected,
                "char_count": char_count,
                "token_estimate": token_estimate,
                "few_shot_count": int((block_params.get(block_id, {}) or {}).get("few_shot_count") or 0),
                "micro_rule_count": len(micro_rules),
                "candidate_strategy_count": len(params.get("candidate_strategies") or []) if block_id == "genome" else 0,
                "optional_status": "active" if block_id in get_optional_blocks() else "",
                "current_params": block_params.get(block_id, {}) or {},
                "compression_allowed": bool(safe_mutations),
                "safe_mutation_types": safe_mutations,
                "measurement_method": "char_div_4_estimate",
            }
        )
    genome_params_tokens = _estimate_prompt_tokens(json.dumps(params, ensure_ascii=False, sort_keys=True))
    total_estimate = genome_params_tokens + sum(int(row["token_estimate"]) for row in block_rows)
    largest = max(block_rows, key=lambda row: int(row.get("token_estimate") or 0), default={})
    prompt_breakdown = {
        "generation": generation,
        "model_key": model_key,
        "total_prompt_token_estimate": total_estimate,
        "block_token_total_estimate": total_estimate - genome_params_tokens,
        "genome_params_token_estimate": genome_params_tokens,
        "measurement_method": "char_div_4_estimate",
        "largest_token_component": str(largest.get("block_id", "genome")),
        "largest_token_component_tokens": int(largest.get("token_estimate") or genome_params_tokens),
    }
    return prompt_breakdown, block_rows


def _compression_level(proposal: dict[str, Any] | MutationProposal) -> str:
    if isinstance(proposal, MutationProposal):
        if proposal.compression_level:
            return proposal.compression_level
        operator = proposal.operator
        target = proposal.selected_block_id or proposal.target_block_id
    else:
        if proposal.get("compression_level"):
            return str(proposal.get("compression_level"))
        operator = _proposal_operator(proposal)
        target = str(proposal.get("selected_block_id") or proposal.get("target_block_id") or "")
    if operator == "multi_block_compression_plan":
        return "multi_block"
    if operator in {"global_render_budget_down", "category_example_budget_down", "service_context_render_budget_down"}:
        return "global_budget"
    if target and target != "genome":
        return "block"
    return "micro"


def _compression_level_priority(proposal: dict[str, Any] | MutationProposal) -> tuple[int, int]:
    level_order = {"block": 0, "multi_block": 1, "global_budget": 2, "micro": 3}
    delta = 0
    if isinstance(proposal, MutationProposal):
        delta = abs(int(proposal.expected_token_delta or proposal.estimated_token_delta or 0))
    else:
        delta = abs(int(proposal.get("expected_token_delta") or proposal.get("total_expected_token_delta") or 0))
    return (level_order.get(_compression_level(proposal), 9), -delta)


def _compression_phase_for_generation(args: argparse.Namespace, *, compression_ready: bool) -> str:
    if not args.enable_compression_mutation:
        return "OFF"
    plateau = str(getattr(args, "_plateau_type", "") or "")
    action = str(getattr(args, "_next_action", "") or "")
    aggressive = (
        compression_ready
        and bool(args.allow_aggressive_compression)
        and bool(args.enable_multi_block_compression or args.enable_render_budget_compression)
        and ("plateau" in plateau or action == "switch_aggressive_compression")
    )
    if aggressive:
        return "AGGRESSIVE_COMPRESSION"
    return "COMPRESSION_READY" if compression_ready else "ACCURACY_SEARCH"


def _staged_compression_quotas(args: argparse.Namespace, *, compression_phase: str, population_size: int) -> dict[str, int]:
    slots = max(0, int(population_size) - 1)
    quotas = {"micro": 0, "block": 0, "multi_block": 0, "global_budget": 0}
    if not args.enable_compression_mutation or slots <= 0:
        return quotas
    # Case A: always-on micro compression.
    # This lane performs small, low-risk token reductions even before DETPass reaches the threshold.
    # It must not mutate protected prompt blocks or replace correctness-oriented repair mutations.
    quotas["micro"] = max(1, int(args.micro_compression_child_quota), int(math.ceil(population_size * args.micro_compression_child_ratio)))
    if compression_phase in {"COMPRESSION_READY", "AGGRESSIVE_COMPRESSION"}:
        # Case B: threshold-gated block compression.
        # Once DETPass is high enough, token optimization becomes explicit and uses
        # block_token_breakdown to target large non-protected prompt blocks.
        quotas["block"] = max(1, int(args.block_compression_child_quota), int(math.ceil(population_size * args.block_compression_child_ratio)))
    if compression_phase == "AGGRESSIVE_COMPRESSION":
        # Case C: aggressive compression.
        # This is additive to Case B: keep block compression active and add multi-block/global-budget children.
        if args.enable_multi_block_compression:
            quotas["multi_block"] = max(
                1,
                int(args.multi_block_compression_child_quota),
                int(math.ceil(population_size * args.multi_block_compression_child_ratio)),
            )
        if args.enable_render_budget_compression:
            quotas["global_budget"] = max(0, int(args.global_budget_compression_child_quota))
    used = 0
    for key in ("micro", "block", "multi_block", "global_budget"):
        allowed = max(0, slots - used)
        quotas[key] = min(quotas[key], allowed)
        used += quotas[key]
    return quotas


def _has_duplicate_micro_rules(genome: dict[str, Any], block_id: str | None = None) -> bool:
    items = (genome.get("block_params") or {}).items()
    if block_id:
        items = [(block_id, (genome.get("block_params") or {}).get(block_id, {}) or {})]
    for _bid, params in items:
        seen: set[str] = set()
        for rule in params.get("micro_rules") or []:
            key = " ".join(str(rule).lower().split())
            if key in seen:
                return True
            seen.add(key)
    return False


def _largest_compressible_block(block_token_breakdown: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [row for row in block_token_breakdown if row.get("compression_allowed")]
    return max(candidates, key=lambda row: int(row.get("token_estimate") or 0), default={})


def _make_compression_lane_proposal(
    *,
    level: str,
    generation: int,
    parent_genome: dict[str, Any],
    block_token_breakdown: list[dict[str, Any]],
    prompt_token_breakdown: dict[str, Any],
    rng: random.Random,
    source: str = "cloudless",
) -> MutationProposal | None:
    parent_id = str(parent_genome.get("id", ""))
    params = parent_genome.get("params") or {}
    block_params = parent_genome.get("block_params") or {}
    operator = ""
    selected_block_id = ""
    selected_block_ids: list[str] = []
    block_row: dict[str, Any] = {}
    if level == "micro":
        if _has_duplicate_micro_rules(parent_genome):
            operator = "dedupe_duplicate_micro_rules"
        elif list(params.get("candidate_strategies") or []) != ["minimal"]:
            operator = "compress_candidate_strategies_to_minimal"
        elif int(params.get("max_tokens") or 768) > 512:
            operator = "lower_output_max_tokens_safe"
        else:
            operator = "compact_block_params_safe"
    elif level == "block":
        block_row = _largest_compressible_block(block_token_breakdown)
        selected_block_id = str(block_row.get("block_id", ""))
        if not selected_block_id:
            return _make_compression_lane_proposal(
                level="micro",
                generation=generation,
                parent_genome=parent_genome,
                block_token_breakdown=block_token_breakdown,
                prompt_token_breakdown=prompt_token_breakdown,
                rng=rng,
                source=source,
            )
        selected_params = block_params.get(selected_block_id, {}) or {}
        if selected_block_id in get_optional_blocks() and selected_block_id not in {"02", "03"} and int(block_row.get("token_estimate") or 0) > 0:
            operator = "drop_optional_block"
        elif int(selected_params.get("few_shot_count") or 0) > 0:
            operator = "reduce_few_shot_count_to_zero"
        elif int(block_row.get("micro_rule_count") or 0) > 3:
            operator = "prune_micro_rules_to_top_k"
        elif selected_block_id in get_optional_blocks() and selected_block_id not in {"03"}:
            operator = "drop_optional_block"
        else:
            operator = "compact_block_params"
    elif level == "multi_block":
        selected_rows = sorted(
            [row for row in block_token_breakdown if row.get("compression_allowed")],
            key=lambda row: int(row.get("token_estimate") or 0),
            reverse=True,
        )[:3]
        selected_block_ids = [str(row.get("block_id")) for row in selected_rows if row.get("block_id")]
        if not selected_block_ids:
            return None
        operator = "multi_block_compression_plan"
        block_row = selected_rows[0]
    elif level == "global_budget":
        operator = "global_render_budget_down"
    else:
        return None
    expected_delta = -max(16, int((block_row.get("token_estimate") if block_row else prompt_token_breakdown.get("total_prompt_token_estimate", 0)) or 64) // 4)
    proposal = MutationProposal(
        proposal_id=f"{level}_compression_g{generation:03d}_{seeded_uuid(rng)[:8]}",
        source=source,
        mutation_family="compression",
        operator=operator,
        target_block_id=selected_block_id or "genome",
        target_block_family=str(block_row.get("block_family", "Compression") if block_row else "Compression"),
        estimated_token_delta=expected_delta,
        risk_score=0.08 if level == "micro" else (0.25 if level == "block" else 0.35),
        affected_failure_families=["token_overbudget"],
        expected_effect=f"{level} compression lane proposal.",
        generation=generation,
        parent_genome_id=parent_id,
        compression_level=level,
        compression_phase=str(prompt_token_breakdown.get("compression_phase", "")),
        selected_compression_target=selected_block_id or ",".join(selected_block_ids) or "genome",
        selected_block_id=selected_block_id,
        selected_block_ids=selected_block_ids,
        block_family=str(block_row.get("block_family", "")),
        block_token_before=int(block_row.get("token_estimate") or 0),
        block_token_after_estimate=max(0, int(block_row.get("token_estimate") or 0) + expected_delta),
        expected_token_delta=expected_delta,
        largest_token_component=str(prompt_token_breakdown.get("largest_token_component", "")),
        preserved_content=["validator-critical schema/service/temporal constraints"],
        removable_content=["duplicates, verbose hints, redundant examples"],
    )
    proposal.target_units = selected_block_ids
    return proposal


def _latest_generation_checkpoint(output_root: Path) -> Path | None:
    ckpt_dir = output_root / "checkpoints"
    if not ckpt_dir.exists():
        return None

    paths = sorted(ckpt_dir.glob("ga_generation_*.json"))
    return paths[-1] if paths else None


def _load_all_checkpoint_evaluations(output_root: Path) -> list[dict[str, Any]]:
    ckpt_dir = output_root / "checkpoints"
    if not ckpt_dir.exists():
        return []

    evaluations: list[dict[str, Any]] = []

    for path in sorted(ckpt_dir.glob("ga_generation_*.json")):
        payload = _safe_read_json(path, {})
        for item in payload.get("population", []) or []:
            if isinstance(item, dict) and "genome" in item:
                evaluations.append(item)

    return evaluations


def _find_evaluation_by_genome_id(
    evaluations: list[dict[str, Any]],
    genome_id: str,
) -> dict[str, Any] | None:
    for item in evaluations:
        genome = item.get("genome") or {}
        if str(genome.get("id", "")) == str(genome_id):
            return item
    return None


def _minimal_evaluation_from_history(row: dict[str, Any]) -> dict[str, Any] | None:
    genome = row.get("genome")
    if not isinstance(genome, dict):
        return None

    validation_avg = float(row.get("validation_avg_det_score") or 0.0)
    fitness = float(row.get("fitness") or validation_avg)

    return {
        "genome": genome,
        "fitness": fitness,
        "avg_det_score": float(row.get("avg_det_score") or validation_avg),
        "variance": 0.0,
        "validation_avg_det_score": validation_avg,
        "train_metrics": {
            "rows": [],
            "avg_det_score": float(row.get("avg_det_score") or 0.0),
            "variance": 0.0,
            "generation_summary": {"rows": []},
        },
        "validation_metrics": {
            "rows": [],
            "avg_det_score": validation_avg,
            "variance": 0.0,
            "generation_summary": {"rows": []},
        },
    }


def _estimate_no_improvement_generations(progress_rows: list[dict[str, Any]]) -> int:
    best = -float("inf")
    stale = 0

    for row in sorted(progress_rows, key=lambda item: int(float(item.get("generation") or 0))):
        try:
            value = float(row.get("validation_avg_det_score") or row.get("avg_det_score") or 0.0)
        except Exception:
            value = 0.0

        if value > best:
            best = value
            stale = 0
        else:
            stale += 1

    return stale


def _load_ga_resume_state(
    *,
    output_root: Path,
    args: argparse.Namespace,
    rng: random.Random,
    base_genome: dict[str, Any],
) -> dict[str, Any] | None:
    progress_rows = _read_csv_records(output_root / "ga_generation_progress.csv")
    latest_checkpoint = _latest_generation_checkpoint(output_root)
    resume_state_path = output_root / "checkpoints" / "ga_resume_state.json"
    resume_state = _safe_read_json(resume_state_path, {})

    completed_from_csv = [
        int(float(row.get("generation") or 0))
        for row in progress_rows
        if str(row.get("generation", "")).strip()
    ]

    completed_from_checkpoint = []
    if latest_checkpoint is not None:
        checkpoint_payload = _safe_read_json(latest_checkpoint, {})
        if checkpoint_payload.get("generation") is not None:
            completed_from_checkpoint.append(int(checkpoint_payload.get("generation") or 0))

    completed = max(completed_from_csv + completed_from_checkpoint) if (completed_from_csv or completed_from_checkpoint) else 0

    if completed <= 0:
        return None

    start_generation = completed + 1

    all_evaluations = _load_all_checkpoint_evaluations(output_root)

    best_history = _safe_read_json(output_root / "best_genomes.json", [])
    if not isinstance(best_history, list):
        best_history = []

    global_best = None
    if all_evaluations:
        global_best = max(
            all_evaluations,
            key=lambda item: float(item.get("validation_avg_det_score") or 0.0),
        )
    elif best_history:
        history_best = max(
            best_history,
            key=lambda item: float(item.get("validation_avg_det_score") or 0.0),
        )
        global_best = _minimal_evaluation_from_history(history_best)

    promotion_rows = _read_csv_records(output_root / "promotion_decisions.csv")
    accepted_best = None
    promoted_rows = [row for row in promotion_rows if _truthy(row.get("promoted"))]
    if promoted_rows:
        latest_promoted = max(
            promoted_rows,
            key=lambda item: int(float(item.get("generation") or 0)),
        )
        accepted_best = _find_evaluation_by_genome_id(
            all_evaluations,
            str(latest_promoted.get("candidate_id", "")),
        )

    if accepted_best is None:
        accepted_best = global_best

    latest_eval = None
    if latest_checkpoint is not None:
        latest_payload = _safe_read_json(latest_checkpoint, {})
        latest_population = latest_payload.get("population", []) or []
        latest_eval_candidates = [
            item for item in latest_population
            if isinstance(item, dict) and "genome" in item
        ]
        if latest_eval_candidates:
            latest_eval = max(
                latest_eval_candidates,
                key=lambda item: float(item.get("validation_avg_det_score") or 0.0),
            )

    # Preferred exact resume path: state saved after next_population was built.
    population_source = "resume_state_next_population"
    population = []
    if (
        isinstance(resume_state, dict)
        and int(resume_state.get("last_completed_generation") or -1) == completed
        and isinstance(resume_state.get("next_population"), list)
        and resume_state.get("next_population")
    ):
        population = [
            validate_genome_blocks(_copy_genome(genome))
            for genome in resume_state.get("next_population", [])
            if isinstance(genome, dict)
        ][: args.population]

        rng_state = resume_state.get("rng_state")
        if rng_state is not None:
            try:
                rng.setstate(_json_to_tuple(rng_state))
            except Exception:
                pass

    else:
        # Backward-compatible fallback for old partial runs.
        # This is not bit-identical to the interrupted next_population,
        # but it continues from the last evaluated generation.
        population_source = "fallback_from_last_evaluated_population"

        latest_population = []
        if latest_checkpoint is not None:
            latest_payload = _safe_read_json(latest_checkpoint, {})
            latest_population = latest_payload.get("population", []) or []

        evaluated = [
            item for item in latest_population
            if isinstance(item, dict) and "genome" in item
        ]
        evaluated.sort(
            key=lambda item: (
                -float(item.get("fitness") or 0.0),
                -float(item.get("validation_avg_det_score") or 0.0),
                str((item.get("genome") or {}).get("id", "")),
            )
        )

        population = [
            validate_genome_blocks(_copy_genome(item["genome"]))
            for item in evaluated[: args.population]
        ]

        while len(population) < args.population:
            population.append(_random_genome(base_genome, rng))

    if not population:
        return None

    return {
        "completed_generation": completed,
        "start_generation": start_generation,
        "population": population[: args.population],
        "population_source": population_source,
        "best_history": best_history,
        "generation_progress": progress_rows,
        "topk_rows": _read_csv_records(output_root / "ga_topk_genomes.csv"),
        "block_diff_rows": _read_jsonl_records(output_root / "ga_block_diffs.jsonl"),
        "population_diagnostic_rows": _read_csv_records(output_root / "ga_population_diagnostics.csv"),
        "structured_feedback_records": _read_jsonl_records(output_root / "structured_feedback.jsonl"),
        "structured_feedback_summary_rows": _read_csv_records(output_root / "structured_feedback_summary.csv"),
        "population_transition_rows": _read_csv_records(output_root / "population_transitions.csv"),
        "promotion_rows": promotion_rows,
        "advisor_proposal_rows": _read_jsonl_records(output_root / "advisor_mutation_proposals.jsonl"),
        "advisor_summary_rows": [],
        "global_best": global_best,
        "accepted_best": accepted_best,
        "previous_generation_best": latest_eval,
        "no_improvement_generations": _estimate_no_improvement_generations(progress_rows),
    }


def _write_ga_resume_state(
    *,
    output_root: Path,
    generation: int,
    next_population: list[dict[str, Any]],
    rng: random.Random,
    global_best: dict[str, Any] | None,
    accepted_best: dict[str, Any] | None,
    no_improvement_generations: int,
) -> None:
    payload = {
        "last_completed_generation": generation,
        "next_generation": generation + 1,
        "next_population": next_population,
        "rng_state": rng.getstate(),
        "global_best_genome_id": str(((global_best or {}).get("genome") or {}).get("id", "")),
        "accepted_best_genome_id": str(((accepted_best or {}).get("genome") or {}).get("id", "")),
        "no_improvement_generations": no_improvement_generations,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }

    dump_json(output_root / "checkpoints" / "ga_resume_state.json", payload)
    dump_json(output_root / "checkpoints" / f"ga_resume_state_generation_{generation:03d}.json", payload)

def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("empty advisor response")

    def candidate_score(value: dict[str, Any]) -> tuple[int, int]:
        proposal_keys = {
            "proposals",
            "mutation_proposals",
            "micro_compression_proposals",
            "block_compression_proposals",
            "multi_block_compression_proposals",
            "global_budget_compression_proposals",
        }
        keys = set(value.keys())
        score = 0
        if "advisor_status" in keys:
            score += 30
        if "compression_policy" in keys:
            score += 10
        if keys & proposal_keys:
            score += 40 + (5 * len(keys & proposal_keys))
        if "prompt_token_breakdown_seen" in keys:
            score += 5
        if "block_token_breakdown_seen" in keys:
            score += 5
        if keys and keys <= {
            "activate_when_detpass_ge",
            "compression_ready",
            "compression_phase",
            "prefer_compression_if_accuracy_saturated",
            "target_token_reduction_ratio",
            "allow_aggressive_compression",
            "preserve_core_blocks",
            "preserve_output_schema",
            "preserve_service_mapping",
        }:
            score -= 50
        return (score, len(json.dumps(value, ensure_ascii=False)))

    def unfence(value: str) -> str:
        stripped = value.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return stripped

    candidates: list[dict[str, Any]] = []
    for candidate_text in (raw, unfence(raw)):
        try:
            parsed = json.loads(candidate_text)
            if isinstance(parsed, dict):
                candidates.append(parsed)
        except json.JSONDecodeError:
            pass
        decoder = json.JSONDecoder()
        for idx, char in enumerate(candidate_text):
            if char != "{":
                continue
            try:
                parsed, _end = decoder.raw_decode(candidate_text[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                candidates.append(parsed)
    if candidates:
        return max(candidates, key=candidate_score)
    raise ValueError("advisor response did not contain a JSON object")


def _block_registry() -> list[dict[str, Any]]:
    registry = []
    for block_id in get_core_blocks():
        registry.append({"block_id": block_id, "role": "core", "mutable": "micro_rules_only"})
    for block_id in get_optional_blocks():
        registry.append({"block_id": block_id, "role": "optional", "mutable": "activation_and_micro_rules"})
    return registry


def _compact_failures(rows: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        for reason in row.get("failure_reasons") or []:
            counter[str(reason).split(":", 1)[0]] += 1
    return dict(counter.most_common())


def _category_diagnostics(
    *,
    generation: int,
    model_key: str,
    evaluated_population: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in evaluated_population:
        genome_id = str(item["genome"].get("id", ""))
        for row in item.get("validation_metrics", {}).get("rows", []) or []:
            category = str(row.get("category", "") or "uncategorized")
            buckets.setdefault(category, []).append({**row, "genome_id": genome_id})
    diagnostics: list[dict[str, Any]] = []
    for category, rows in sorted(buckets.items(), key=lambda kv: kv[0]):
        scores = [float(row.get("det_score") or 0.0) for row in rows]
        pass_count = sum(1 for row in rows if bool(row.get("det_gt_exact")) or float(row.get("det_score") or 0.0) >= DET_PASS_THRESHOLD)
        diagnostics.append(
            {
                "generation": generation,
                "model_key": model_key,
                "category": category,
                "row_evaluations": len(rows),
                "avg_det_score": round(statistics.fmean(scores), 4) if scores else 0.0,
                "det_pass_count": pass_count,
                "det_pass_rate": round((pass_count / len(rows)) * 100.0, 4) if rows else 0.0,
                "failure_histogram": json.dumps(_compact_failures(rows), ensure_ascii=False, sort_keys=True),
            }
        )
    return diagnostics


def _population_summary_for_advisor(
    evaluated_population: list[dict[str, Any]],
    *,
    top_k: int,
    bottom_k: int,
) -> dict[str, Any]:
    def compact(item: dict[str, Any], rank: int) -> dict[str, Any]:
        validation = _metric_summary(item["validation_metrics"])
        active = active_block_summary(item["genome"])
        meta = item["genome"].get("_ga_metadata", {}) or {}
        return {
            "rank": rank,
            "genome_id": item["genome"].get("id", ""),
            "fitness": item.get("fitness", 0.0),
            "avg_det_score": validation["avg_det_score"],
            "det_pass_rate": validation["det_pass_rate"],
            "avg_prompt_tokens": validation["avg_prompt_tokens"],
            "core_blocks": active["core"],
            "optional_blocks": active["optional"],
            "mutation_types": meta.get("mutation_types", []),
            "feedback_types_used": meta.get("feedback_types_used", []),
            "advisor_proposal_id": meta.get("advisor_proposal_id", ""),
        }

    top = [compact(item, idx) for idx, item in enumerate(evaluated_population[: max(1, top_k)], start=1)]
    bottom_slice = list(reversed(evaluated_population[-max(1, bottom_k) :])) if evaluated_population else []
    bottom = [compact(item, idx) for idx, item in enumerate(bottom_slice, start=1)]
    return {"top_genomes": top, "bottom_genomes": bottom}


def _representative_failure_rows(evaluated_population: list[dict[str, Any]], max_examples: int) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for item in evaluated_population:
        genome_id = str(item["genome"].get("id", ""))
        for row in item.get("validation_metrics", {}).get("rows", []) or []:
            reasons = row.get("failure_reasons") or []
            if not reasons:
                continue
            examples.append(
                {
                    "row_id": row.get("row_no", ""),
                    "category": row.get("category", ""),
                    "genome_id": genome_id,
                    "command_eng": row.get("command_eng", ""),
                    "failure_reasons": reasons,
                    "det_score": row.get("det_score", 0.0),
                }
            )
            if len(examples) >= max_examples:
                return examples
    return examples


def _build_advisor_prompt(
    *,
    generation: int,
    model_key: str,
    evaluated_population: list[dict[str, Any]],
    category_diagnostics: list[dict[str, Any]],
    feedback_summary: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    best = evaluated_population[0]["genome"] if evaluated_population else {}
    payload = {
        "task": "Propose prompt-block mutations only. Do not generate JOILang code.",
        "generation": generation,
        "model_key": model_key,
        "constraints": [
            "Core blocks cannot be removed.",
            "Retrieval pre-mapping is fixed runtime context and cannot be mutated.",
            "Do not suggest changing retrieval top-k, retrieval mode, or service-context construction.",
            "Propose only prompt-block-level changes, micro-rules, or block parameters.",
            "Output valid JSON only.",
        ],
        "current_best": {
            "genome_id": best.get("id", ""),
            "blocks": active_block_summary(best) if best else {},
            "params": best.get("params", {}) if best else {},
            "block_params_keys": sorted((best.get("block_params", {}) or {}).keys()) if best else [],
        },
        "population": _population_summary_for_advisor(
            evaluated_population,
            top_k=args.advisor_top_k,
            bottom_k=args.advisor_bottom_k,
        ),
        "category_diagnostics": category_diagnostics,
        "feedback_summary": feedback_summary[:10],
        "representative_failures": _representative_failure_rows(evaluated_population, args.advisor_max_examples),
        "available_prompt_blocks": _block_registry(),
        "version0_13_prompt_surgery_rules": prompt_surgery_registry(),
        "det_feedback_mapping": det_feedback_rules(),
        "required_json_schema": {
            "generation": generation,
            "model_key": model_key,
            "diagnosis": [{"category_group": "string", "main_failure": "string", "hypothesis": "string"}],
            "mutation_proposals": [
                {
                    "target_block_id": "02",
                    "target_block_family": "Service_Mapping",
                    "mutation_type": "add_micro_rule",
                    "priority": 1,
                    "reason": "short reason",
                    "edit_instruction": "prompt-block edit only",
                    "proposed_micro_rule": "concise rule text",
                }
            ],
            "do_not_change": ["core blocks", "retrieval pre-mapping"],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _mock_advisor_response(
    generation: int,
    model_key: str,
    feedback_summary: list[dict[str, Any]],
    *,
    compression_ready: bool = False,
    allow_aggressive_compression: bool = False,
    block_token_breakdown: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    top = feedback_summary[0] if feedback_summary else {
        "affected_block_family": "Service_Mapping",
        "prompt_block_id": "02",
        "suggested_mutation_type": "add_canonical_service_name_rule",
        "failure_type": "unknown_service",
    }
    family = str(top.get("affected_block_family", "Service_Mapping") or "Service_Mapping")
    block_id = str(top.get("prompt_block_id", "02") or "02")
    mutation_type = str(top.get("suggested_mutation_type", "add_micro_rule") or "add_micro_rule")
    micro_rule = str(
        top.get("rule")
        or "Use deterministic validation feedback to strengthen the implicated prompt block."
    )
    if compression_ready:
        block_token_breakdown = block_token_breakdown or []
        block_target = _largest_compressible_block(block_token_breakdown) or {"block_id": "06", "block_family": "DET_Helper", "token_estimate": 400}
        mutation_type = (
            "lower_output_max_tokens_aggressive"
            if allow_aggressive_compression
            else "compress_candidate_strategies_to_minimal"
        )
        return {
            "advisor_status": "accepted",
            "generation": generation,
            "model_key": model_key,
            "compression_policy": {
                "compression_ready": True,
                "compression_phase": "COMPRESSION_READY",
                "allow_aggressive_compression": bool(allow_aggressive_compression),
            },
            "prompt_token_breakdown_seen": True,
            "block_token_breakdown_seen": True,
            "diagnosis": [
                {
                    "category_group": "compression",
                    "main_failure": "token_overbudget",
                    "hypothesis": "Mock advisor sees saturated DETPass and proposes prompt compression.",
                }
            ],
            "proposals": [
                {
                    "proposal_id": f"advisor_g{generation:03d}_compress_01",
                    "target_block_id": "genome",
                    "target_block_family": "Compression",
                    "mutation_family": "compression",
                    "mutation_type": mutation_type,
                    "priority": 3,
                    "reason": "Mock compression proposal generated for compression-ready smoke.",
                    "affected_failure_families": ["token_overbudget"],
                    "category_scope": [1, 2],
                    "group_scope": ["basic"],
                    "proposed_micro_rule": "",
                    "expected_effect": "Reduce prompt tokens while preserving schema/service grounding.",
                    "expected_token_delta": -1000,
                    "regression_risk": 0.25,
                    "apply_mode": "create_child",
                }
            ],
            "block_compression_proposals": [
                {
                    "proposal_id": f"advisor_g{generation:03d}_block_01",
                    "mutation_family": "compression",
                    "compression_level": "block",
                    "selected_block_id": str(block_target.get("block_id", "06")),
                    "selected_block_family": str(block_target.get("block_family", "DET_Helper")),
                    "exact_mutation_operator": "compact_reasoning_skeleton",
                    "operator": "compact_reasoning_skeleton",
                    "mutation_type": "compact_reasoning_skeleton",
                    "original_token_estimate": int(block_target.get("token_estimate") or 400),
                    "proposed_token_estimate_after": max(1, int(block_target.get("token_estimate") or 400) - 120),
                    "expected_token_delta": -120,
                    "preserved_content": ["schema/service/temporal validator-critical constraints"],
                    "removable_content": ["duplicate micro-rules and verbose reasoning hints"],
                    "why_safe": "Mock block proposal targets a non-core compression-allowed block.",
                    "regression_risk": 0.2,
                    "validation_requirement": "strict DETPass gate",
                }
            ],
            "do_not_change": ["core blocks", "output schema", "retrieval pre-mapping"],
            "advisor_backend": "mock_schema",
        }
    return {
        "generation": generation,
        "model_key": model_key,
        "diagnosis": [
            {
                "category_group": "validation",
                "main_failure": str(top.get("failure_type", "unknown_service")),
                "hypothesis": f"{family} needs a targeted micro-rule from deterministic validation.",
            }
        ],
        "mutation_proposals": [
            {
                "target_block_id": block_id,
                "target_block_family": family,
                "mutation_type": mutation_type,
                "priority": int(top.get("priority", 1) or 1),
                "reason": "Mock advisor proposal generated for schema validation smoke.",
                "edit_instruction": "Add the proposed micro-rule to the target prompt block.",
                "proposed_micro_rule": micro_rule,
            }
        ],
        "do_not_change": ["core blocks", "retrieval pre-mapping"],
        "advisor_backend": "mock_schema",
    }


def _proposal_mentions_retrieval(proposal: dict[str, Any]) -> bool:
    mutation_fields = {
        "target_block_id": proposal.get("target_block_id", ""),
        "target_block_family": proposal.get("target_block_family", ""),
        "mutation_type": proposal.get("mutation_type", ""),
        "edit_instruction": proposal.get("edit_instruction", ""),
        "proposed_micro_rule": proposal.get("proposed_micro_rule", ""),
    }
    text = json.dumps(mutation_fields, ensure_ascii=False).lower()
    forbidden = ("retrieval", "top-k", "topk", "service-context", "service context", "premapping", "pre-mapping")
    return any(item in text for item in forbidden)


def _existing_micro_rules(genome: dict[str, Any]) -> set[str]:
    rules: set[str] = set()
    for params in (genome.get("block_params") or {}).values():
        for rule in params.get("micro_rules") or []:
            token = str(rule).strip().lower()
            if token:
                rules.add(token)
    return rules


ADVISOR_PROPOSAL_SCHEMA_KEYS = (
    "proposals",
    "mutation_proposals",
    "micro_compression_proposals",
    "block_compression_proposals",
    "multi_block_compression_proposals",
    "global_budget_compression_proposals",
)

MICRO_COMPRESSION_OPERATORS = {
    "compress_candidate_strategies_to_minimal",
    "template_compress_rule_family",
    "lower_output_max_tokens_safe",
    "compact_block_params_safe",
    "dedupe_duplicate_micro_rules",
    "prune_micro_rules_to_top_k_safe",
    "reduce_candidate_strategies",
}

BLOCK_COMPRESSION_OPERATORS = {
    "reduce_few_shot_count",
    "reduce_few_shot_count_to_zero",
    "reduce_few_shot_count_by_one",
    "prune_micro_rules_to_top_k",
    "compact_block_params",
    "drop_optional_block",
    "compact_reasoning_skeleton",
}

MULTI_BLOCK_COMPRESSION_OPERATORS = {
    "drop_optional_blocks_for_budget",
    "multi_block_compression_plan",
}

GLOBAL_BUDGET_COMPRESSION_OPERATORS = {
    "global_render_budget_down",
    "category_example_budget_down",
    "service_context_render_budget_down",
    "compact_service_schema_fields",
    "dedupe_service_value_enums",
    "drop_unused_device_capabilities",
}


def _schema_default_compression_level(schema_source: str) -> str:
    if schema_source == "block_compression_proposals":
        return "block"
    if schema_source == "multi_block_compression_proposals":
        return "multi_block"
    if schema_source == "global_budget_compression_proposals":
        return "global_budget"
    if schema_source == "micro_compression_proposals":
        return "micro"
    return ""


def _infer_advisor_compression_level(proposal: dict[str, Any], schema_source: str) -> str:
    explicit = str(proposal.get("compression_level") or "").strip()
    if explicit in {"micro", "block", "multi_block", "global_budget"}:
        return explicit
    operator = _proposal_operator(proposal)
    selected_block_ids = [str(value) for value in (proposal.get("selected_block_ids") or []) if str(value).strip()]
    target_block_id = str(proposal.get("selected_block_id") or proposal.get("target_block_id") or "").strip()
    schema_default = _schema_default_compression_level(schema_source)
    if operator in GLOBAL_BUDGET_COMPRESSION_OPERATORS or schema_default == "global_budget":
        return "global_budget"
    if operator in MULTI_BLOCK_COMPRESSION_OPERATORS or schema_default == "multi_block" or selected_block_ids:
        return "multi_block"
    if schema_default == "block" or operator in BLOCK_COMPRESSION_OPERATORS:
        return "block"
    if target_block_id and target_block_id != "genome":
        return "block"
    return schema_default or "micro"


def _normalize_advisor_proposal(
    raw: dict[str, Any],
    *,
    schema_source: str,
    generation: int,
    advisor_batch_id_value: str,
) -> dict[str, Any]:
    proposal = dict(raw or {})
    if proposal.get("proposal_id"):
        proposal["proposal_id"] = str(proposal.get("proposal_id"))
    proposal["schema_source"] = schema_source
    proposal["advisor_generation"] = generation
    proposal["advisor_batch_id"] = advisor_batch_id_value
    proposal["proposal_state"] = PROPOSAL_STATE_PROPOSED
    operator = str(proposal.get("exact_mutation_operator") or proposal.get("operator") or proposal.get("mutation_type") or "").strip()
    if not proposal.get("operator") and operator:
        proposal["operator"] = operator
    if not proposal.get("mutation_type") and operator:
        proposal["mutation_type"] = operator
    if proposal.get("exact_mutation_operator") and not proposal.get("operator"):
        proposal["operator"] = str(proposal.get("exact_mutation_operator"))
    target_block_id = str(proposal.get("target_block_id") or "").strip()
    if target_block_id and target_block_id != "genome" and not proposal.get("selected_block_id"):
        proposal["selected_block_id"] = target_block_id
    if proposal.get("selected_block_id") and not proposal.get("target_block_id"):
        proposal["target_block_id"] = proposal.get("selected_block_id")
    if proposal.get("selected_block_family") and not proposal.get("target_block_family"):
        proposal["target_block_family"] = proposal.get("selected_block_family")
    if proposal.get("total_expected_token_delta") is not None and proposal.get("expected_token_delta") is None:
        proposal["expected_token_delta"] = proposal.get("total_expected_token_delta")
    if _is_compression_proposal(proposal):
        proposal.setdefault("mutation_family", "compression")
        proposal["compression_level"] = _infer_advisor_compression_level(proposal, schema_source)
        proposal.setdefault("target_block_id", "genome")
        proposal.setdefault("target_block_family", "Compression")
        proposal.setdefault("affected_failure_families", ["token_overbudget"])
    if not proposal.get("affected_failure_families"):
        fallback_family = str(proposal.get("target_block_family", "") or "schema_violation")
        proposal["affected_failure_families"] = [fallback_family]
    return proposal


def _advisor_rejection_diagnostic(
    *,
    generation: int,
    advisor_batch_id_value: str,
    schema_source: str,
    rejection_reason: str,
    raw_response_path: str = "",
    advisor_prompt_path: str = "",
) -> dict[str, Any]:
    level = _schema_default_compression_level(schema_source)
    is_compression_schema = bool(level or "compression" in schema_source)
    return {
        "proposal_id": f"advisor_g{generation:03d}_{schema_source}_diagnostic",
        "schema_source": schema_source,
        "advisor_generation": generation,
        "advisor_batch_id": advisor_batch_id_value,
        "mutation_family": "compression" if is_compression_schema else "advisor_guided",
        "compression_level": level,
        "operator": "",
        "mutation_type": "",
        "target_block_id": "genome" if is_compression_schema else "",
        "target_block_family": "Compression" if is_compression_schema else "",
        "expected_token_delta": 0,
        "accepted": False,
        "proposal_state": PROPOSAL_STATE_REJECTED,
        "rejection_reason": rejection_reason,
        "raw_response_path": raw_response_path,
        "advisor_prompt_path": advisor_prompt_path,
    }


def _safe_advisor_proposals(
    payload: dict[str, Any],
    *,
    generation: int,
    advisor_batch_id_value: str = "",
    parent_genome: dict[str, Any] | None = None,
    block_token_breakdown: list[dict[str, Any]] | None = None,
    min_compression_token_delta: int = 32,
    raw_response_path: str = "",
    advisor_prompt_path: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    safe: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    valid_blocks = set(get_core_blocks()) | set(get_optional_blocks())
    raw_proposals: list[dict[str, Any]] = []
    for key in ADVISOR_PROPOSAL_SCHEMA_KEYS:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            rejected.append(
                _advisor_rejection_diagnostic(
                    generation=generation,
                    advisor_batch_id_value=advisor_batch_id_value,
                    schema_source=key,
                    rejection_reason="invalid_json_schema",
                    raw_response_path=raw_response_path,
                    advisor_prompt_path=advisor_prompt_path,
                )
            )
            continue
        for raw in value:
            if not isinstance(raw, dict):
                rejected.append(
                    _advisor_rejection_diagnostic(
                        generation=generation,
                        advisor_batch_id_value=advisor_batch_id_value,
                        schema_source=key,
                        rejection_reason="malformed_proposal",
                        raw_response_path=raw_response_path,
                        advisor_prompt_path=advisor_prompt_path,
                    )
                )
                continue
            raw_proposals.append(
                _normalize_advisor_proposal(
                    raw,
                    schema_source=key,
                    generation=generation,
                    advisor_batch_id_value=advisor_batch_id_value,
                )
            )
    if not raw_proposals and not rejected:
        rejected.append(
            _advisor_rejection_diagnostic(
                generation=generation,
                advisor_batch_id_value=advisor_batch_id_value,
                schema_source="no_schema",
                rejection_reason="no_advisor_proposals_parsed",
                raw_response_path=raw_response_path,
                advisor_prompt_path=advisor_prompt_path,
            )
        )
    existing_rules = _existing_micro_rules(parent_genome or {})
    for idx, raw in enumerate(raw_proposals or [], start=1):
        proposal = dict(raw or {})
        proposal_id = f"advisor_g{generation:03d}_{idx:02d}"
        proposal["proposal_id"] = str(proposal.get("proposal_id") or proposal_id)
        proposal["advisor_generation"] = generation
        proposal["advisor_batch_id"] = advisor_batch_id_value
        proposal["proposal_state"] = PROPOSAL_STATE_PROPOSED
        proposal["raw_response_path"] = raw_response_path
        proposal["advisor_prompt_path"] = advisor_prompt_path
        # Reject no-op/protected advisor compression before child scheduling.
        # A rejected compression proposal can still trigger compression_fallback later.
        ok, reject_reason = validate_advisor_proposal(
            proposal,
            valid_blocks=valid_blocks,
            core_blocks=set(get_core_blocks()),
            existing_rules=existing_rules,
            current_genome=parent_genome or {},
            block_token_breakdown=block_token_breakdown or [],
            min_compression_token_delta=min_compression_token_delta,
        )
        if reject_reason:
            ok = False
        if not ok:
            rejected.append(
                {
                    **proposal,
                    "accepted": False,
                    "proposal_state": PROPOSAL_STATE_REJECTED,
                    "rejection_reason": reject_reason or "malformed_proposal",
                }
            )
            continue
        safe.append({**proposal, "accepted": False, "proposal_state": PROPOSAL_STATE_PROPOSED, "rejection_reason": ""})
    return safe, rejected


def _advisor_hint_from_proposal(proposal: dict[str, Any]) -> dict[str, str]:
    return {
        "failure_type": "advisor_proposal",
        "affected_block_family": str(proposal.get("target_block_family", "")),
        "prompt_block_id": str(proposal.get("target_block_id", "02") or "02"),
        "suggested_mutation_type": str(proposal.get("mutation_type", "add_micro_rule") or "add_micro_rule"),
        "rule": str(proposal.get("proposed_micro_rule", "") or proposal.get("edit_instruction", "")),
    }


def _proposal_artifact_row(proposal: dict[str, Any] | MutationProposal) -> dict[str, Any]:
    if isinstance(proposal, MutationProposal):
        return _proposal_to_row(proposal)
    return dict(proposal)


def _write_advisor_block_compression_plan(
    output_root: Path,
    *,
    generation: int,
    compression_phase: str,
    accepted_proposals: list[dict[str, Any] | MutationProposal],
    rejected_proposals: list[dict[str, Any] | MutationProposal],
    fallback_used: bool,
    fallback_reason: str,
) -> None:
    accepted_rows = [_proposal_artifact_row(item) for item in accepted_proposals if _is_compression_proposal(item)]
    rejected_rows = [_proposal_artifact_row(item) for item in rejected_proposals if _is_compression_proposal(item)]
    dump_json(
        output_root / f"advisor_block_compression_plan_generation_{generation:03d}.json",
        {
            "generation": generation,
            "compression_phase": compression_phase,
            "accepted_block_proposals": [item for item in accepted_rows if _compression_level(item) == "block"],
            "accepted_multi_block_proposals": [item for item in accepted_rows if _compression_level(item) == "multi_block"],
            "accepted_global_budget_proposals": [item for item in accepted_rows if _compression_level(item) == "global_budget"],
            "rejected_compression_proposals": rejected_rows,
            "fallback_used": bool(fallback_used),
            "fallback_reason": str(fallback_reason or ""),
        },
    )


def _call_mutation_advisor(
    *,
    args: argparse.Namespace,
    output_root: Path,
    generation: int,
    model_key: str,
    evaluated_population: list[dict[str, Any]],
    category_diagnostics: list[dict[str, Any]],
    feedback_summary: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    prompt_path = output_root / f"advisor_prompt_generation_{generation:03d}.txt"
    response_path = output_root / f"advisor_response_generation_{generation:03d}.json"
    if not args.llm_mutation_advisor:
        prompt_path.write_text("advisor_status=skipped llm_mutation_advisor_disabled\n", encoding="utf-8")
        dump_json(response_path, {"advisor_status": "skipped", "reason": "llm_mutation_advisor_disabled"})
        return [], []
    trigger_mode = str(args.advisor_trigger_mode or "off")
    trigger_active = bool(getattr(args, "_advisor_triggered", False)) or (
        trigger_mode == "on_compression" and bool(getattr(args, "_compression_ready", False))
    )
    if trigger_mode not in {"always"} and not trigger_active:
        prompt_path.write_text(f"advisor_status=skipped trigger_mode={trigger_mode} inactive\n", encoding="utf-8")
        dump_json(response_path, {"advisor_status": "skipped", "reason": f"trigger_mode_{trigger_mode}_inactive"})
        return [], []
    best_item = evaluated_population[0] if evaluated_population else {}
    best_metric = _metric_for_eval(best_item) if best_item else None
    top_failure_types: list[str] = []
    for feedback in feedback_summary[:5]:
        failure_type = str(feedback.get("failure_type", ""))
        if failure_type:
            top_failure_types.append(failure_type)
    advisor_batch = build_advisor_feedback_batch(
        generation=generation,
        model_key=model_key,
        advisor_model_key=args.advisor_model_key,
        evaluated_population=evaluated_population,
        categories=list(args.category or []),
        limit_per_category=args.limit_per_category,
        sample_size=args.sample_size,
        validation_size=args.validation_size,
        generation_phase=str(getattr(args, "_generation_phase", "")),
        plateau_type=str(getattr(args, "_plateau_type", "")),
        next_action=str(getattr(args, "_next_action", "")),
        overall={
            "best_DETPass": float(getattr(best_metric, "validation_det_pass_rate", 0.0) or 0.0),
            "best_AvgDET": float(getattr(best_metric, "validation_avg_det_score", 0.0) or 0.0),
            "best_tokens": float(getattr(best_metric, "avg_prompt_tokens", 0.0) or 0.0),
            "best_latency": float(getattr(best_metric, "avg_latency_sec", 0.0) or 0.0),
            "best_so_far_DETPass": float(getattr(args, "_best_so_far_detpass", 0.0) or 0.0),
            "accepted_best_DETPass": float(getattr(args, "_accepted_best_detpass", 0.0) or 0.0),
            "pareto_archive_size": int(getattr(args, "_pareto_archive_size", 0) or 0),
            "top_failure_types": top_failure_types,
        },
        cloudless_feedback_summary={
            "structured_feedback_count": len(feedback_summary),
            "applied_cloudless_mutations": [],
            "active_failure_families": [str(item.get("failure_type", "")) for item in feedback_summary],
            "mutation_operator_credit": [],
        },
        best_genome_metric=best_metric,
        max_representative_failures=args.advisor_max_representative_failures,
        include_candidate_code=bool(args.advisor_include_candidate_code),
        include_prompt_summary=bool(args.advisor_include_prompt_summary),
        compression_detpass_threshold=float(args.compression_detpass_threshold),
        compression_token_reduction_target=float(args.compression_token_reduction_target),
        allow_aggressive_compression=bool(args.allow_aggressive_compression or args.aggressive_compression_after_target),
        compression_ready=bool(getattr(args, "_compression_ready", False)),
        compression_phase=str(getattr(args, "_compression_phase", "ACCURACY_SEARCH")),
        prompt_token_breakdown=getattr(args, "_prompt_token_breakdown", {}) or {},
        block_token_breakdown=getattr(args, "_block_token_breakdown", []) or [],
    )

    batch_path = output_root / "advisor_feedback_batches.jsonl"
    _append_jsonl(batch_path, advisor_batch)
    dump_json(output_root / f"advisor_feedback_batch_generation_{generation:03d}.json", advisor_batch)

    prompt_text = build_advisor_prompt_from_batch(advisor_batch, detail=args.advisor_feedback_detail)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    cloud_advisor_artifacts = _write_cloud_advisor_prompt_artifacts(
        output_root=output_root,
        generation=generation,
        prompt_text=prompt_text,
        advisor_batch=advisor_batch,
        args=args,
    )

    advisor_mode = str(getattr(args, "advisor_llm_mode", "openai") or "openai").strip().lower()
    advisor_endpoint = str(getattr(args, "advisor_llm_endpoint", "") or "").strip() or None

    if advisor_mode == "mock":
        advisor_payload = _mock_advisor_response(
            generation,
            model_key,
            feedback_summary,
            compression_ready=bool(getattr(args, "_compression_ready", False)),
            allow_aggressive_compression=bool(args.allow_aggressive_compression or args.aggressive_compression_after_target),
            block_token_breakdown=getattr(args, "_block_token_breakdown", []) or [],
        )
        raw_content = json.dumps(advisor_payload, ensure_ascii=False)
    else:
        raw_content = ""
        try:
            response = call_llm(
                "You are a prompt-block mutation advisor. Return valid JSON only.",
                prompt_text,
                model=_advisor_model_name(args.advisor_model_key),
                mode=advisor_mode,
                endpoint=advisor_endpoint,
                temperature=args.advisor_temperature,
                max_tokens=2048,
                timeout_sec=args.timeout_sec,
                retries=args.retries,
                log_path=output_root / "logs" / f"advisor_generation_{generation:03d}.json",
            )
            raw_content = str(response.get("content", ""))
            advisor_payload = _extract_json_object(raw_content)
        except Exception as exc:
            raw_dir = output_root / "advisor_raw_responses"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / f"generation_{generation:03d}_raw.txt"
            raw_path.write_text(raw_content, encoding="utf-8")
            dump_json(
                response_path,
                {
                    "raw_content": raw_content,
                    "parsed": {},
                    "compression_policy": {},
                    "advisor_batch_id": advisor_batch.get("advisor_batch_id", ""),
                    "accepted_proposals": [],
                    "rejected_proposals": [
                        {
                            "proposal_id": f"advisor_g{generation:03d}_error",
                            "accepted": False,
                            "rejection_reason": f"advisor call failed: {exc}",
                            "raw_response_path": str(raw_path),
                            "advisor_prompt_path": str(prompt_path),
                            "advisor_llm_mode": advisor_mode,
                            "advisor_model_key": args.advisor_model_key,
                            "advisor_model": _advisor_model_name(args.advisor_model_key),
                        }
                    ],
                    "advisor_llm_mode": advisor_mode,
                    "advisor_model_key": args.advisor_model_key,
                    "advisor_model": _advisor_model_name(args.advisor_model_key),
                    **cloud_advisor_artifacts,
                },
            )
            return [], [
                {
                    "proposal_id": f"advisor_g{generation:03d}_error",
                    "accepted": False,
                    "proposal_state": PROPOSAL_STATE_REJECTED,
                    "rejection_reason": f"advisor call failed: {exc}",
                    "advisor_batch_id": advisor_batch.get("advisor_batch_id", ""),
                    "advisor_llm_mode": advisor_mode,
                    "advisor_model_key": args.advisor_model_key,
                    "advisor_model": _advisor_model_name(args.advisor_model_key),
                    **cloud_advisor_artifacts,
                }
            ]
    raw_dir = output_root / "advisor_raw_responses"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"generation_{generation:03d}_raw.txt"
    raw_path.write_text(raw_content, encoding="utf-8")
    safe, rejected = _safe_advisor_proposals(
        advisor_payload,
        generation=generation,
        advisor_batch_id_value=str(advisor_batch.get("advisor_batch_id", "")),
        parent_genome=best_item.get("genome") if best_item else {},
        block_token_breakdown=getattr(args, "_block_token_breakdown", []) or [],
        min_compression_token_delta=int(args.min_compression_token_delta),
        raw_response_path=str(raw_path),
        advisor_prompt_path=str(prompt_path),
    )
    compression_policy = dict((advisor_payload or {}).get("compression_policy") or {})
    _write_advisor_block_compression_plan(
        output_root,
        generation=generation,
        compression_phase=str(getattr(args, "_compression_phase", "")),
        accepted_proposals=safe,
        rejected_proposals=rejected,
        fallback_used=False,
        fallback_reason="",
    )
    dump_json(
        response_path,
        {
            "raw_content": raw_content,
            "parsed": advisor_payload,
            "compression_policy": compression_policy,
            "advisor_batch_id": advisor_batch.get("advisor_batch_id", ""),
            "accepted_proposals": safe,
            "rejected_proposals": rejected,
            "advisor_llm_mode": advisor_mode,
            "advisor_model_key": args.advisor_model_key,
            "advisor_model": _advisor_model_name(args.advisor_model_key),
            **cloud_advisor_artifacts,
        },
    )
    return safe, rejected


def _avg_prompt_tokens(metrics: dict[str, Any]) -> float:
    generation_rows = list((metrics.get("generation_summary") or {}).get("rows") or [])
    if not generation_rows:
        return 0.0
    values = []
    for row in generation_rows:
        raw = row.get("generation_prompt_tokens_total") or row.get("prompt_tokens") or 0
        try:
            values.append(float(raw))
        except Exception:
            pass
    return round(statistics.fmean(values), 4) if values else 0.0


def _schema_fail_rate(metrics: dict[str, Any]) -> float:
    rows = list(metrics.get("rows", []))
    if not rows:
        return 0.0
    schema_failures = 0
    for row in rows:
        reasons = [str(reason).split(":", 1)[0] for reason in (row.get("failure_reasons") or [])]
        if any(reason in {"invalid_json", "schema_missing_keys", "unknown_service", "service_match", "arg_type", "enum_grounding"} for reason in reasons):
            schema_failures += 1
    return round((schema_failures / len(rows)) * 100.0, 4)


def _metric_summary(metrics: dict[str, Any], *, threshold: float = DET_PASS_THRESHOLD) -> dict[str, Any]:
    progress = _metric_progress(metrics, threshold=threshold)
    progress["avg_prompt_tokens"] = _avg_prompt_tokens(metrics)
    progress["schema_fail_rate"] = _schema_fail_rate(metrics)
    progress["strict_sdet"] = progress["avg_det_score"]
    progress["replay_fit"] = ""
    return progress


def _progress_enabled(args: argparse.Namespace, level: str = "minimal") -> bool:
    if args.progress == "quiet":
        return False
    if level == "verbose":
        return args.progress == "verbose"
    return True


def _diagnostic_label(category: str) -> str:
    token = str(category or "").strip()
    if token in {"1", "2"}:
        return "simple"
    if token in {"3", "4", "5"}:
        return "temporal"
    if token in {"6", "7", "8"}:
        return "replay-heavy"
    return f"cat{token or 'unknown'}"


def _print_run_start(args: argparse.Namespace, output_root: Path, model_key: str, categories: list[str]) -> None:
    if not _progress_enabled(args):
        return
    print("[RUN]", flush=True)
    print(f"command={' '.join(sys.argv)}", flush=True)
    print(f"model={model_key or 'genome.params.model'}", flush=True)
    print(f"categories={','.join(categories) if categories else 'all-selected'}", flush=True)
    print(f"limit_per_category={args.limit_per_category if args.limit_per_category is not None else 'N/A'}", flush=True)
    print(f"output_root={output_root}", flush=True)


def _print_generation(
    args: argparse.Namespace,
    *,
    generation: int,
    evaluated_count: int,
    transition: dict[str, Any],
    top_records: list[dict[str, Any]],
    best_diffs: list[dict[str, Any]],
    feedback_summary: list[dict[str, Any]],
    category_diagnostics: list[dict[str, Any]],
    advisor_summary: dict[str, Any] | None,
    advisor_proposals: list[dict[str, Any]],
    previous_best: dict[str, Any] | None,
) -> None:
    if not _progress_enabled(args):
        return
    best = top_records[0] if top_records else {}
    print(
        f"[GA][GEN {generation:02d}/{args.gens:02d}]\n"
        f"population={args.population} evaluated={evaluated_count} "
        f"generation_phase={transition.get('generation_phase', '')} "
        f"next_action={transition.get('next_action', '')} "
        f"best_so_far_DETPass={float(getattr(args, '_best_so_far_detpass', 0.0) or 0.0):.1f} "
        f"best={best.get('genome_id', '')} det={float(best.get('det', 0.0) or 0.0):.1f} "
        f"pass={best.get('det_pass_count', 0)}/{best.get('row_count', 0)} "
        f"tokens={float(best.get('tokens', 0.0) or 0.0):.0f}",
        flush=True,
    )
    print(
        "[GA][COMPRESSION]\n"
        f"compression_ready={transition.get('compression_ready', False)} "
        f"compression_phase={transition.get('compression_phase', '')} "
        f"threshold={float(getattr(args, 'compression_detpass_threshold', 0.0) or 0.0):.1f} "
        f"best_so_far_DETPass={float(getattr(args, '_best_so_far_detpass', 0.0) or 0.0):.1f} "
        f"micro={transition.get('new_by_micro_compression', 0)} "
        f"block={transition.get('new_by_block_compression', 0)} "
        f"multi={transition.get('new_by_multi_block_compression', 0)} "
        f"global={transition.get('new_by_global_budget_compression', 0)} "
        f"advisor_compression_proposals={transition.get('advisor_compression_proposals', 0)} "
        f"advisor_compression_children_scheduled={transition.get('advisor_compression_children_scheduled', 0)} "
        f"cloudless_compression_fallback_scheduled={transition.get('cloudless_compression_fallback_scheduled', 0)} "
        f"compression_child_quota={transition.get('compression_child_quota', 0)}",
        flush=True,
    )
    print("[GA][TOP-3]", flush=True)
    for row in top_records[: max(1, args.top_k)]:
        print(
            f"#{row.get('rank')} {row.get('genome_id')} det={float(row.get('det', 0.0) or 0.0):.1f} "
            f"pass={row.get('det_pass_count', 0)}/{row.get('row_count', 0)} "
            f"tokens={float(row.get('tokens', 0.0) or 0.0):.0f} "
            f"core=[{row.get('core_blocks', '')}] optional=[{row.get('optional_blocks', '')}] "
            f"parent={row.get('parent_ids', '')}",
            flush=True,
        )
    if category_diagnostics:
        print("[GA][DIAGNOSTIC]", flush=True)
        for item in category_diagnostics[:5]:
            failures = item.get("failure_histogram", "{}")
            label = _diagnostic_label(str(item.get("category", "")))
            print(
                f"{label}: det={float(item.get('avg_det_score', 0.0) or 0.0):.1f} "
                f"pass={item.get('det_pass_count', 0)}/{item.get('row_evaluations', 0)} "
                f"failures={failures}",
                flush=True,
            )
    if best_diffs:
        print("[GA][BLOCK-DIFF]", flush=True)
        print("changed:", flush=True)
        for diff in best_diffs[:6]:
            print(
                f"  block={diff.get('block_id')} mutation={diff.get('mutation_type')} "
                f"old={diff.get('old_value')} new={diff.get('new_value')}",
                flush=True,
            )
    if feedback_summary and args.progress == "verbose":
        print("[GA][FEEDBACK]", flush=True)
        applied = []
        for item in feedback_summary[:5]:
            applied.append(str(item.get("suggested_mutation_type", "")))
            print(
                f"{item.get('failure_type')}={item.get('failure_count')} -> "
                f"target=[{item.get('affected_block_family')}]",
                flush=True,
            )
        print(f"applied_mutations=[{', '.join(dict.fromkeys(applied))}]", flush=True)
    if advisor_summary:
        print("[GA][ADVISOR]", flush=True)
        if advisor_proposals:
            compression_proposals = [proposal for proposal in advisor_proposals if _is_compression_proposal(proposal)]
            print(
                f"advisor_status=accepted compression_proposals={len(compression_proposals)} "
                f"advisor_compression_children_scheduled={transition.get('advisor_compression_children_scheduled', 0)}",
                flush=True,
            )
            for idx, proposal in enumerate(advisor_proposals[: max(1, args.advisor_top_k)], start=1):
                print(
                    f"proposal#{idx} block={proposal.get('target_block_id', '')} "
                    f"mutation={proposal.get('mutation_type', '')} priority={proposal.get('priority', '')}",
                    flush=True,
                )
        else:
            print(
                f"advisor_status=skipped accepted={advisor_summary.get('accepted_proposals', 0)} "
                f"rejected={advisor_summary.get('rejected_proposals', 0)}",
                flush=True,
            )
    print(
        "[GA][POPULATION-UPDATE]\n"
        f"survived_elites={transition.get('survived_elites', 0)} "
        f"new_by_crossover={transition.get('new_by_crossover', 0)} "
        f"new_by_mutation={transition.get('new_by_mutation', 0)} "
        f"new_by_advisor={transition.get('new_by_advisor', 0)} "
        f"new_by_compression={transition.get('new_by_compression', 0)} "
        f"advisor_compression_children_scheduled={transition.get('advisor_compression_children_scheduled', 0)} "
        f"new_random={transition.get('new_random', 0)} "
        f"duplicates_removed={transition.get('duplicates_removed', 0)} "
        f"next_population={transition.get('next_population', 0)}",
        flush=True,
    )


def _genome_signature(genome: dict[str, Any]) -> str:
    payload = {
        "blocks": normalize_active_blocks(genome.get("blocks") or []),
        "params": genome.get("params", {}),
        "block_params": genome.get("block_params", {}),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _dedupe_population(population: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    removed = 0
    for genome in population:
        signature = _genome_signature(genome)
        if signature in seen:
            removed += 1
            continue
        seen.add(signature)
        kept.append(genome)
    return kept, removed


def _evaluate_one(
    *,
    profile: str,
    genome: dict[str, Any],
    train_rows: list[tuple[int, dict[str, str]]],
    validation_rows: list[tuple[int, dict[str, str]]],
    service_schema: dict[str, dict[str, Any]],
    candidate_k: int,
    cheap_eval_limit: int,
    llm_mode: str | None,
    llm_endpoint: str | None,
    timeout_sec: int,
    retries: int,
    alpha: float,
    seed: int,
    det_profile: str,
    output_root: Path,
) -> dict[str, Any]:
    cheap_rows = train_rows[: min(len(train_rows), cheap_eval_limit)]
    quick_metrics = evaluate_genome_on_rows(
        profile=profile,
        genome=genome,
        row_subset=cheap_rows,
        service_schema=service_schema,
        candidate_k=max(1, min(candidate_k, 2)),
        llm_mode=llm_mode,
        llm_endpoint=llm_endpoint,
        timeout_sec=timeout_sec,
        retries=retries,
        seed=seed,
        run_label="ga_quick",
        det_profile=det_profile,
        output_dir=output_root / "candidates",
    )
    metrics = quick_metrics
    if len(train_rows) > len(cheap_rows) and float(quick_metrics["avg_det_score"]) > 0.0:
        metrics = evaluate_genome_on_rows(
            profile=profile,
            genome=genome,
            row_subset=train_rows,
            service_schema=service_schema,
            candidate_k=candidate_k,
            llm_mode=llm_mode,
            llm_endpoint=llm_endpoint,
            timeout_sec=timeout_sec,
            retries=retries,
            seed=seed,
            run_label="ga_full",
            det_profile=det_profile,
            output_dir=output_root / "candidates",
        )
    validation_metrics = evaluate_genome_on_rows(
        profile=profile,
        genome=genome,
        row_subset=validation_rows,
        service_schema=service_schema,
        candidate_k=max(1, min(candidate_k, 2)),
        llm_mode=llm_mode,
        llm_endpoint=llm_endpoint,
        timeout_sec=timeout_sec,
        retries=retries,
        seed=seed + 500000,
        run_label="ga_validation",
        det_profile=det_profile,
        output_dir=output_root / "candidates",
    )
    fitness = float(metrics["avg_det_score"]) - alpha * float(metrics["variance"])
    evaluation = {
        "genome": genome,
        "fitness": round(fitness, 6),
        "avg_det_score": metrics["avg_det_score"],
        "variance": metrics["variance"],
        "validation_avg_det_score": validation_metrics["avg_det_score"],
        "train_metrics": metrics,
        "validation_metrics": validation_metrics,
    }
    dump_json(output_root / "evaluations" / f"genome_{genome['id']}.json", evaluation)
    return evaluation


def _metric_progress(metrics: dict[str, Any], *, threshold: float = DET_PASS_THRESHOLD) -> dict[str, Any]:
    rows = list(metrics.get("rows", []))
    row_count = len(rows)
    gt_exact_count = sum(1 for row in rows if bool(row.get("det_gt_exact")))
    det_pass_count = sum(
        1
        for row in rows
        if bool(row.get("det_gt_exact")) or float(row.get("det_score") or 0.0) >= float(threshold)
    )
    return {
        "row_count": row_count,
        "gt_exact_count": gt_exact_count,
        "gt_exact_rate": round((gt_exact_count / row_count) * 100.0, 4) if row_count else 0.0,
        "det_pass_count": det_pass_count,
        "det_pass_rate": round((det_pass_count / row_count) * 100.0, 4) if row_count else 0.0,
        "avg_det_score": float(metrics.get("avg_det_score") or 0.0),
        "variance": float(metrics.get("variance") or 0.0),
    }


def _redesign_enabled(args: argparse.Namespace) -> bool:
    return (
        args.selection_mode == "redesign"
        or args.fitness_mode != "legacy"
        or args.mutation_mode != "legacy"
        or args.stop_controller_mode == "active"
        or bool(args.enable_pareto_archive)
    )


def _phase_token_weight(args: argparse.Namespace, phase: str) -> float:
    if args.fitness_mode == "legacy":
        return 0.0
    if phase == "COMPRESSION_SEARCH":
        return float(args.fitness_token_weight_max)
    if phase == "ROBUSTNESS_STABILIZATION":
        return (float(args.fitness_token_weight_min) + float(args.fitness_token_weight_max)) / 2.0
    return float(args.fitness_token_weight_min)


def _metric_for_eval(item: dict[str, Any]) -> GenomeMetricBundle | None:
    metric = item.get("redesign_metrics")
    return metric if isinstance(metric, GenomeMetricBundle) else None


def _attach_redesign_metrics(
    evaluated_population: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    accepted_best: dict[str, Any] | None,
    generation_phase: str,
    token_budget: int | None,
    row_margin: float,
) -> None:
    accepted_metric = _metric_for_eval(accepted_best or {})
    parent_metrics_by_id = {
        str((item.get("genome") or {}).get("id", "")): _metric_for_eval(item)
        for item in evaluated_population
    }
    token_weight = _phase_token_weight(args, generation_phase)
    for item in evaluated_population:
        meta = (item.get("genome") or {}).get("_ga_metadata", {}) or {}
        parent_id = ""
        parents = meta.get("parent_ids") or []
        if parents:
            parent_id = str(parents[0])
        metric = metrics_from_evaluation(
            item,
            token_budget=token_budget,
            token_penalty_mode=args.token_penalty_mode,
            accepted_metrics=accepted_metric,
            parent_metrics=parent_metrics_by_id.get(parent_id),
            fitness_avgdet_weight=args.fitness_avgdet_weight,
            fitness_token_weight=token_weight,
            fitness_regression_weight=args.fitness_regression_weight,
            fitness_variance_weight=args.fitness_variance_weight,
            fitness_category_weight=(args.fitness_category_weight if args.category_balance_mode == "fitness" else 0.0),
            row_margin=row_margin,
        )
        item["redesign_metrics"] = metric
        if args.fitness_mode != "legacy":
            item["fitness"] = metric.score_main
            item["avg_det_score"] = metric.validation_avg_det_score
            item["variance"] = metric.det_score_variance
            item["validation_avg_det_score"] = metric.validation_avg_det_score


def _sort_evaluated_population(evaluated_population: list[dict[str, Any]], args: argparse.Namespace) -> None:
    if _redesign_enabled(args):
        evaluated_population.sort(
            key=lambda item: (
                -float((_metric_for_eval(item) or metrics_from_evaluation(item)).score_main),
                *best_tie_key(_metric_for_eval(item) or metrics_from_evaluation(item), generation=int(item.get("generation", 0) or 0)),
            )
        )
    else:
        evaluated_population.sort(
            key=lambda item: (-float(item["fitness"]), -float(item["validation_avg_det_score"]), item["genome"]["id"])
        )


def _best_by_redesign_tiebreak(evaluated_population: list[dict[str, Any]], generation: int) -> dict[str, Any] | None:
    if not evaluated_population:
        return None
    return min(
        evaluated_population,
        key=lambda item: best_tie_key(_metric_for_eval(item) or metrics_from_evaluation(item), generation=generation),
    )


def _accepted_metric_row(accepted_best: dict[str, Any] | None) -> GenomeMetricBundle | None:
    return _metric_for_eval(accepted_best or {})


def _safe_metric(item: dict[str, Any] | None) -> GenomeMetricBundle | None:
    if not item:
        return None
    return _metric_for_eval(item) or metrics_from_evaluation(item)


def _latest_promoted_row(promotion_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    promoted = [row for row in promotion_rows if _truthy(row.get("promoted"))]
    if not promoted:
        return None
    return max(promoted, key=lambda row: int(float(row.get("generation") or 0)))


def _summary_consistency_check(
    *,
    summary: dict[str, Any],
    promotion_rows: list[dict[str, Any]],
    detpass_margin: float,
) -> dict[str, Any]:
    errors: list[str] = []
    latest_promoted = _latest_promoted_row(promotion_rows)
    if latest_promoted:
        expected = float(latest_promoted.get("DETPass") or 0.0)
        actual = summary.get("accepted_best_DETPass")
        if actual is None or abs(float(actual or 0.0) - expected) > 1e-6:
            errors.append("accepted_best_DETPass does not match latest promoted candidate DETPass")
    if summary.get("best_DETPass") is None and summary.get("best_so_far_DETPass") not in {"", None}:
        errors.append("best_DETPass is missing despite evaluated generations")
    compact = summary.get("compact_best_DETPass")
    best_so_far = summary.get("best_so_far_DETPass")
    compact_eligible = True
    if compact not in {"", None} and best_so_far not in {"", None}:
        compact_eligible = float(compact or 0.0) >= float(best_so_far or 0.0) - detpass_margin
        if not compact_eligible:
            errors.append("compact_best is outside the DETPass eligibility margin")
    return {
        "promotion_consistent": not any("accepted_best_DETPass" in item for item in errors),
        "compact_best_eligible": compact_eligible,
        "best_fields_complete": summary.get("best_DETPass") is not None and summary.get("best_genome_id", "") != "",
        "errors": errors,
    }


def _proposal_to_row(proposal: MutationProposal) -> dict[str, Any]:
    row = proposal.to_row()
    row["operator"] = row.get("operator") or row.get("mutation_type", "")
    row["mutation_type"] = row.get("mutation_type") or row.get("operator", "")
    row.setdefault("schema_source", "")
    if not row.get("compression_level") and row.get("mutation_family") == "compression":
        row["compression_level"] = _compression_level(proposal)
    row.setdefault("compression_level", "")
    row.setdefault("selected_block_id", "")
    row.setdefault("selected_block_ids", "[]")
    row.setdefault("expected_token_delta", row.get("estimated_token_delta", 0))
    if float(row.get("measured_prompt_token_delta") or 0.0) == 0.0:
        row["measured_prompt_token_delta"] = None
        row["measured_prompt_token_delta_pct"] = None
    row.setdefault("raw_response_path", "")
    row.setdefault("advisor_prompt_path", "")
    row.setdefault("fallback_reason", "")
    return row


ADVISOR_MUTATION_SUMMARY_COLUMNS = [
    "generation",
    "proposal_id",
    "schema_source",
    "operator",
    "compression_level",
    "selected_block_id",
    "selected_block_ids",
    "expected_token_delta",
    "accepted",
    "rejection_reason",
    "raw_response_path",
    "advisor_prompt_path",
]


def _advisor_mutation_summary_rows(advisor_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary_rows: list[dict[str, Any]] = []
    for row in advisor_rows:
        summary_rows.append({key: row.get(key, "") for key in ADVISOR_MUTATION_SUMMARY_COLUMNS})
    return summary_rows


def _fill_measured_token_deltas(
    mutation_proposal_rows: list[dict[str, Any]],
    evaluated_population: list[dict[str, Any]],
) -> None:
    metrics_by_id: dict[str, Any] = {}
    for item in evaluated_population:
        genome_id = str((item.get("genome") or {}).get("id", ""))
        metric = _metric_for_eval(item)
        if genome_id and metric:
            metrics_by_id[genome_id] = metric
    for row in mutation_proposal_rows:
        if float(row.get("measured_prompt_token_delta") or 0.0) != 0.0:
            continue
        child_metric = metrics_by_id.get(str(row.get("child_genome_id", "")))
        parent_metric = metrics_by_id.get(str(row.get("parent_genome_id", "")))
        if not child_metric or not parent_metric:
            continue
        delta = float(child_metric.avg_prompt_tokens or 0.0) - float(parent_metric.avg_prompt_tokens or 0.0)
        row["measured_prompt_token_delta"] = round(delta, 4)
        row["measured_prompt_token_delta_pct"] = round((delta / max(1.0, float(parent_metric.avg_prompt_tokens or 0.0))) * 100.0, 4)


def _cloudless_mutation_proposals(
    *,
    generation: int,
    parent_genome: dict[str, Any],
    feedback_hint: dict[str, Any] | None,
    args: argparse.Namespace,
    rng: random.Random,
    active_failure_families: list[str],
) -> list[MutationProposal]:
    proposals: list[MutationProposal] = []
    family = mutation_family_for_phase(str(getattr(args, "_generation_phase", "ACCURACY_SEARCH")), rng)
    if feedback_hint and family == "accuracy_repair":
        proposals.append(
            proposal_for_family(
                family="accuracy_repair",
                generation=generation,
                parent_genome_id=str(parent_genome.get("id", "")),
                feedback_hint=feedback_hint,
                rng=rng,
            )
        )
    if args.enable_compression_mutation or args.mutation_mode in {"cloudless_decompiler", "hybrid"}:
        proposals.append(
            proposal_for_family(
                family="compression",
                generation=generation,
                parent_genome_id=str(parent_genome.get("id", "")),
                feedback_hint=None,
                rng=rng,
                aggressive_compression=bool(
                    getattr(args, "_compression_ready", False)
                    and (args.allow_aggressive_compression or args.aggressive_compression_after_target)
                ),
            )
        )
    if args.enable_prompt_decompiler or args.mutation_mode in {"cloudless_decompiler", "hybrid"}:
        prompt_like = json.dumps(
            {
                "blocks": parent_genome.get("blocks", []),
                "params": parent_genome.get("params", {}),
                "block_params": parent_genome.get("block_params", {}),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        artifact = decompile_prompt(prompt_like, active_failure_families=active_failure_families)
        proposals.extend(
            compression_proposals_from_artifact(
                artifact,
                generation=generation,
                parent_genome_id=str(parent_genome.get("id", "")),
                max_proposals=2,
            )
        )
    return proposals[: max(1, args.compression_children_per_parent)]


def _write_redesign_artifacts(
    output_root: Path,
    *,
    mutation_proposal_rows: list[dict[str, Any]],
    mutation_operator_credit_rows: list[dict[str, Any]],
    pareto_archive_rows: list[dict[str, Any]],
    prompt_unit_rows: list[dict[str, Any]],
) -> None:
    _write_jsonl(output_root / "mutation_proposals.jsonl", mutation_proposal_rows)
    if mutation_proposal_rows:
        atomic_write_csv(output_root / "mutation_proposals.csv", list(mutation_proposal_rows[0].keys()), mutation_proposal_rows)
    else:
        atomic_write_csv(output_root / "mutation_proposals.csv", ["proposal_id", "source", "mutation_family", "operator"], [])
    if mutation_operator_credit_rows:
        atomic_write_csv(output_root / "mutation_operator_credit.csv", list(mutation_operator_credit_rows[0].keys()), mutation_operator_credit_rows)
    else:
        atomic_write_csv(output_root / "mutation_operator_credit.csv", ["generation", "mutation_family", "mutation_operator"], [])
    if pareto_archive_rows:
        atomic_write_csv(output_root / "pareto_archive.csv", list(pareto_archive_rows[0].keys()), pareto_archive_rows)
    else:
        atomic_write_csv(output_root / "pareto_archive.csv", ["generation", "genome_id", "det_pass_rate", "avg_prompt_tokens"], [])
    _write_jsonl(output_root / "pareto_archive.jsonl", pareto_archive_rows)
    _write_jsonl(output_root / "cloudless_prompt_units.jsonl", prompt_unit_rows)


def _checkpoint_population(evaluated_population: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in evaluated_population:
        clone = dict(item)
        metric = _metric_for_eval(clone)
        if metric:
            clone["redesign_metrics"] = metric.to_row()
        rows.append(clone)
    return rows


def run_ga_search(args: argparse.Namespace) -> dict[str, Any]:
    ensure_workspace()
    output_root = _resolve_output_root(args.output_root)
    _guard_output_root(output_root, args)
    output_root.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    base_genome = validate_genome_blocks(load_genome(args.genome_json))
    if args.model_key:
        base_genome.setdefault("params", {})["model"] = _model_name_for_key(args.model_key)
    service_schema = load_service_schema(args.service_schema)
    rows = load_dataset_rows(args.dataset)
    selected_rows = select_rows(
        rows,
        start_row=args.start_row,
        end_row=args.end_row,
        limit=args.limit,
        limit_per_category=args.limit_per_category,
        categories=args.category,
    )
    if not selected_rows:
        raise SystemExit("No rows selected. Check --start-row/--end-row/--limit/--category.")
    categories = sorted({str(row.get("category", "")) for _row_no, row in selected_rows if str(row.get("category", ""))})
    model_key = args.model_key or str(base_genome.get("params", {}).get("model", ""))
    model_label = _model_label_for_key(args.model_key) if args.model_key else model_key
    if args.max_generations is not None:
        args.gens = int(args.max_generations)
    token_budget = args.token_budget
    budget_source = "global_fallback" if token_budget else "none"
    budget_fallback_reason = ""
    if args.model_token_budget_json:
        budget_path = Path(args.model_token_budget_json).expanduser().resolve()
        try:
            budget_map = json.loads(budget_path.read_text(encoding="utf-8"))
            if model_key in budget_map:
                token_budget = int(budget_map[model_key])
                budget_source = "model_json"
            elif token_budget:
                budget_fallback_reason = f"model_key {model_key!r} missing from model token budget JSON"
            else:
                budget_fallback_reason = f"model_key {model_key!r} missing from model token budget JSON and no --token-budget provided"
        except Exception as exc:
            budget_fallback_reason = f"failed to read model token budget JSON: {exc}"
            budget_source = "global_fallback" if token_budget else "none"

    run_manifest = {
        "profile": args.profile,
        "model_key": model_key,
        "model_label": model_label,
        "dataset": str(Path(args.dataset).expanduser().resolve()),
        "service_schema": str(Path(args.service_schema).expanduser().resolve()),
        "selected_row_count": len(selected_rows),
        "categories": categories,
        "stage": getattr(args, "stage_name", ""),
        "full_run": bool(args.full_run),
        "resume": bool(args.resume),
        "force": bool(args.force),
        "limit_per_category": args.limit_per_category,
        "core_blocks": get_core_blocks(),
        "optional_blocks": get_optional_blocks(),
        "retrieval_policy": "fixed runtime service-context construction; not mutated by GA",
        "fitness": f"AvgDET - {args.alpha} * VarDET",
        "redesign_modes": {
            "selection_mode": args.selection_mode,
            "fitness_mode": args.fitness_mode,
            "mutation_mode": args.mutation_mode,
            "stop_controller_mode": args.stop_controller_mode,
            "category_balance_mode": args.category_balance_mode,
            "token_penalty_mode": args.token_penalty_mode,
        },
        "budget_snapshot": {
            "run_id": output_root.name,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "model_key": model_key,
            "baseline_token_budget": token_budget,
            "budget_source": budget_source,
            "model_token_budget_json": str(Path(args.model_token_budget_json).expanduser().resolve()) if args.model_token_budget_json else "",
            "fallback_used": bool(budget_fallback_reason),
            "fallback_reason": budget_fallback_reason,
        },
        "command": " ".join(sys.argv),
    }
    dump_json(output_root / "ga_run_manifest.json", run_manifest)
    _write_stage_status(output_root, str(getattr(args, "stage_name", "ga")), "STARTED", {"selected_row_count": len(selected_rows)})
    _print_run_start(args, output_root, model_key, categories)

    validation_rows = sample_rows(selected_rows, sample_size=args.validation_size, seed=args.seed + 9000)
    validation_row_nos = {row_no for row_no, _ in validation_rows}

    population = [_random_genome(base_genome, rng) for _ in range(args.population)]
    best_history: list[dict[str, Any]] = []
    generation_progress: list[dict[str, Any]] = []
    topk_rows: list[dict[str, Any]] = []
    block_diff_rows: list[dict[str, Any]] = []
    population_diagnostic_rows: list[dict[str, Any]] = []
    structured_feedback_records: list[dict[str, Any]] = []
    structured_feedback_summary_rows: list[dict[str, Any]] = []
    population_transition_rows: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    advisor_proposal_rows: list[dict[str, Any]] = []
    advisor_summary_rows: list[dict[str, Any]] = []
    mutation_proposal_rows: list[dict[str, Any]] = []
    mutation_operator_credit_rows: list[dict[str, Any]] = []
    pareto_archive_rows: list[dict[str, Any]] = []
    pareto_generation_summary_rows: list[dict[str, Any]] = []
    prompt_unit_rows: list[dict[str, Any]] = []
    global_best: dict[str, Any] | None = None
    accepted_best: dict[str, Any] | None = None
    archives = ArchiveState()
    previous_generation_best: dict[str, Any] | None = None
    no_improvement_generations = 0
    start_generation = 1
    best_so_far_detpass = 0.0
    best_so_far_avgdet = 0.0
    disruptive_attempt_count = 0

    if args.resume:
        resume_state = _load_ga_resume_state(
            output_root=output_root,
            args=args,
            rng=rng,
            base_genome=base_genome,
        )

        if resume_state is not None:
            population = resume_state["population"]
            best_history = resume_state["best_history"]
            generation_progress = resume_state["generation_progress"]
            topk_rows = resume_state["topk_rows"]
            block_diff_rows = resume_state["block_diff_rows"]
            population_diagnostic_rows = resume_state["population_diagnostic_rows"]
            structured_feedback_records = resume_state["structured_feedback_records"]
            structured_feedback_summary_rows = resume_state["structured_feedback_summary_rows"]
            population_transition_rows = resume_state["population_transition_rows"]
            promotion_rows = resume_state["promotion_rows"]
            advisor_proposal_rows = resume_state["advisor_proposal_rows"]
            advisor_summary_rows = resume_state["advisor_summary_rows"]
            global_best = resume_state["global_best"]
            accepted_best = resume_state["accepted_best"]
            previous_generation_best = resume_state["previous_generation_best"]
            no_improvement_generations = int(resume_state["no_improvement_generations"] or 0)
            start_generation = int(resume_state["start_generation"])

            if args.progress != "quiet":
                print(
                    "[RESUME]\n"
                    f"output_root={output_root}\n"
                    f"completed_generation={resume_state['completed_generation']}\n"
                    f"start_generation={start_generation}\n"
                    f"target_gens={args.gens}\n"
                    f"population_source={resume_state['population_source']}\n"
                    f"population={len(population)}",
                    flush=True,
                )
        elif args.progress != "quiet":
            print("[RESUME] no usable checkpoint found; starting from generation 1", flush=True)
            
    if args.dry_run:
        dry_summary = {
            **run_manifest,
            "status": "dry_run",
            "output_root": str(output_root),
            "generation_progress_csv": str(output_root / "ga_generation_progress.csv"),
            "structured_feedback_jsonl": str(output_root / "structured_feedback.jsonl"),
            "initial_population": [
                {
                    "genome_id": genome.get("id", ""),
                    "core_blocks": active_block_summary(genome)["core"],
                    "optional_blocks": active_block_summary(genome)["optional"],
                    "params": genome.get("params", {}),
                }
                for genome in population
            ],
            "artifacts": {
                "ga_generation_progress_csv": str(output_root / "ga_generation_progress.csv"),
                "ga_population_diagnostics_csv": str(output_root / "ga_population_diagnostics.csv"),
                "structured_feedback_jsonl": str(output_root / "structured_feedback.jsonl"),
                "advisor_feedback_batches_jsonl": str(output_root / "advisor_feedback_batches.jsonl"),
                "advisor_mutation_proposals_jsonl": str(output_root / "advisor_mutation_proposals.jsonl"),
                "mutation_proposals_jsonl": str(output_root / "mutation_proposals.jsonl"),
                "pareto_archive_csv": str(output_root / "pareto_archive.csv"),
                "promotion_decisions_csv": str(output_root / "promotion_decisions.csv"),
            },
        }
        dump_json(output_root / "ga_summary.json", dry_summary)
        dump_json(output_root / "best_prompt_metadata.json", {"status": "dry_run", "core_blocks": get_core_blocks(), "optional_blocks": get_optional_blocks()})
        atomic_write_csv(output_root / "ga_generation_progress.csv", ["generation", "model_key", "genome_id"], [])
        _write_jsonl(output_root / "ga_generation_progress.jsonl", [])
        atomic_write_csv(output_root / "ga_topk_genomes.csv", ["generation", "rank", "genome_id"], [])
        _write_jsonl(output_root / "ga_block_diffs.jsonl", [])
        atomic_write_csv(output_root / "ga_population_diagnostics.csv", ["generation", "model_key", "category"], [])
        _write_jsonl(output_root / "ga_population_diagnostics.jsonl", [])
        _write_jsonl(output_root / "advisor_feedback_batches.jsonl", [])
        _write_jsonl(output_root / "advisor_mutation_proposals.jsonl", [])
        atomic_write_csv(output_root / "advisor_mutation_summary.csv", ADVISOR_MUTATION_SUMMARY_COLUMNS, [])
        _write_redesign_artifacts(
            output_root,
            mutation_proposal_rows=[],
            mutation_operator_credit_rows=[],
            pareto_archive_rows=[],
            prompt_unit_rows=[],
        )
        atomic_write_csv(output_root / "ga_pareto_frontier.csv", PARETO_COLUMNS, [])
        _write_jsonl(output_root / "ga_pareto_frontier.jsonl", [])
        atomic_write_csv(output_root / "ga_pareto_generation_summary.csv", PARETO_SUMMARY_COLUMNS, [])
        _write_jsonl(output_root / "ga_pareto_generation_summary.jsonl", [])
        _write_jsonl(output_root / "structured_feedback.jsonl", [])
        atomic_write_csv(output_root / "structured_feedback_summary.csv", ["failure_type", "failure_count"], [])
        atomic_write_csv(
            output_root / "population_transitions.csv",
            [
                "generation",
                "generation_phase",
                "next_action",
                "compression_ready",
                "compression_phase",
                "micro_compression_child_quota",
                "block_compression_child_quota",
                "multi_block_compression_child_quota",
                "global_budget_compression_child_quota",
                "compression_child_quota",
                "compression_children_scheduled",
                "advisor_compression_proposals",
                "advisor_compression_children_scheduled",
                "cloudless_compression_fallback_scheduled",
                "new_by_compression_fallback",
                "new_by_micro_compression",
                "new_by_block_compression",
                "new_by_multi_block_compression",
                "new_by_global_budget_compression",
                "next_population",
            ],
            [],
        )
        atomic_write_csv(output_root / "promotion_decisions.csv", PROMOTION_COLUMNS, [])
        dump_json(output_root / "promotion_decisions.json", {"rows": []})
        dump_json(output_root / "best_genome.json", {"status": "dry_run"})
        dump_json(output_root / "advisor_response_generation_000.json", {"advisor_status": "skipped", "reason": "dry_run"})
        (output_root / "advisor_prompt_generation_000.txt").write_text("advisor_status=skipped dry_run\n", encoding="utf-8")
        _write_stage_status(output_root, str(getattr(args, "stage_name", "dry-run")), "PASS", {"output_root": str(output_root)})
        _print_stage(args, str(getattr(args, "stage_name", "dry-run")), "PASS")
        return dry_summary

    if start_generation > args.gens and args.progress != "quiet":
        print(
            f"[RESUME] already complete: start_generation={start_generation} target_gens={args.gens}",
            flush=True,
        )

    for generation in range(start_generation, args.gens + 1):
        generation_phase = str(getattr(args, "_generation_phase", "ACCURACY_SEARCH"))
        train_rows = sample_rows(
            selected_rows,
            sample_size=args.sample_size,
            seed=args.seed + generation,
            exclude_row_nos=validation_row_nos,
        )
        if not train_rows:
            train_rows = [item for item in selected_rows if item[0] not in validation_row_nos] or selected_rows

        evaluated_population: list[dict[str, Any]] = []
        for genome in population:
            evaluation = _evaluate_one(
                profile=args.profile,
                genome=genome,
                train_rows=train_rows,
                validation_rows=validation_rows,
                service_schema=service_schema,
                candidate_k=args.candidate_k,
                cheap_eval_limit=args.cheap_eval_limit,
                llm_mode=args.llm_mode,
                llm_endpoint=args.llm_endpoint,
                timeout_sec=args.timeout_sec,
                retries=args.retries,
                alpha=args.alpha,
                seed=args.seed + generation + int(genome.get("seed", 0)) % 10000,
                det_profile=args.det_profile,
                output_root=output_root,
            )
            evaluated_population.append(evaluation)

        validation_row_margin = one_row_margin(
            len(validation_rows),
            args.detpass_row_margin if args.detpass_row_margin > 0 else None,
        )
        if _redesign_enabled(args):
            _attach_redesign_metrics(
                evaluated_population,
                args=args,
                accepted_best=accepted_best,
                generation_phase=generation_phase,
                token_budget=token_budget,
                row_margin=validation_row_margin,
            )
        _sort_evaluated_population(evaluated_population, args)
        generation_best = evaluated_population[0]
        raw_generation_best = _best_by_redesign_tiebreak(evaluated_population, generation) or generation_best
        train_progress = _metric_summary(generation_best["train_metrics"])
        validation_progress = _metric_summary(generation_best["validation_metrics"])
        redesign_metric = _metric_for_eval(generation_best)
        raw_metric = _metric_for_eval(raw_generation_best)
        if redesign_metric:
            validation_progress["det_pass_rate"] = redesign_metric.validation_det_pass_rate
            validation_progress["avg_det_score"] = redesign_metric.validation_avg_det_score
            validation_progress["variance"] = redesign_metric.det_score_variance
            validation_progress["avg_prompt_tokens"] = redesign_metric.avg_prompt_tokens
        raw_generation_detpass = raw_metric.validation_det_pass_rate if raw_metric else validation_progress["det_pass_rate"]
        best_so_far_detpass = max(best_so_far_detpass, raw_generation_detpass)
        best_so_far_avgdet = max(best_so_far_avgdet, validation_progress["avg_det_score"])
        best_meta = generation_best["genome"].get("_ga_metadata", {}) or {}
        active = active_block_summary(generation_best["genome"])
        parent_ids = ",".join(str(item) for item in best_meta.get("parent_ids", []) or [])
        mutation_types = ",".join(str(item) for item in best_meta.get("mutation_types", []) or [])
        feedback_types_used = ",".join(str(item) for item in best_meta.get("feedback_types_used", []) or [])
        progress_record = {
            "profile": args.profile,
            "generation": generation,
            "model_key": model_key,
            "genome_id": generation_best["genome"]["id"],
            "parent_ids": parent_ids,
            "model": str(generation_best["genome"].get("params", {}).get("model", "")),
            "fitness": generation_best["fitness"],
            "avg_det_score": validation_progress["avg_det_score"],
            "det_pass_rate": validation_progress["det_pass_rate"],
            "det_variance": validation_progress["variance"],
            "avg_prompt_tokens": validation_progress["avg_prompt_tokens"],
            "strict_sdet": validation_progress["strict_sdet"] if args.det_profile == "strict" else "",
            "replay_fit": validation_progress["replay_fit"],
            "schema_fail_rate": validation_progress["schema_fail_rate"],
            "train_avg_det_score": train_progress["avg_det_score"],
            "train_det_pass_rate": train_progress["det_pass_rate"],
            "validation_avg_det_score": validation_progress["avg_det_score"],
            "validation_det_pass_rate": validation_progress["det_pass_rate"],
            "validation_gt_exact_rate": validation_progress["gt_exact_rate"],
            "candidate_strategies": "|".join(str(item) for item in generation_best["genome"].get("params", {}).get("candidate_strategies", []) or []),
            "active_core_blocks": ",".join(active["core"]),
            "active_optional_blocks": ",".join(active["optional"]),
            "mutation_types": mutation_types,
            "crossover_used": bool(best_meta.get("crossover_used", False)),
            "advisor_used": bool(best_meta.get("advisor_used", False)),
            "feedback_types_used": feedback_types_used,
            "promoted_candidate": False,
            "raw_generation_best_DETPass": raw_generation_detpass,
            "best_so_far_DETPass": best_so_far_detpass,
            "accepted_best_DETPass": (_metric_for_eval(accepted_best).validation_det_pass_rate if _metric_for_eval(accepted_best or {}) else ""),
            "score_main": redesign_metric.score_main if redesign_metric else generation_best["fitness"],
            "score_accuracy": redesign_metric.score_accuracy if redesign_metric else "",
            "score_efficiency": redesign_metric.score_efficiency if redesign_metric else "",
            "score_balanced": redesign_metric.score_balanced if redesign_metric else "",
            "score_deployment": redesign_metric.score_deployment if redesign_metric else "",
            "token_penalty": redesign_metric.token_penalty if redesign_metric else "",
            "compression_gain": redesign_metric.compression_gain if redesign_metric else "",
            "category_balance_score": redesign_metric.category_balance_score if redesign_metric else "",
            "regression_penalty": redesign_metric.regression_penalty if redesign_metric else "",
            "pareto_rank": redesign_metric.pareto_rank if redesign_metric else "",
            "pareto_frontier_member": redesign_metric.pareto_frontier_member if redesign_metric else "",
            "generation_phase": generation_phase,
            "plateau_type": "",
            "next_action": "",
            "stop_candidate": False,
            "stop_reason": "",
            "unique_prompt_hash_count": "",
            "pareto_archive_size": "",
            "pareto_archive_delta": "",
        }

        generation_feedback_records: list[dict[str, Any]] = []
        for item in evaluated_population:
            generation_feedback_records.extend(
                feedback_records_from_rows(
                    list(item["validation_metrics"].get("rows", [])),
                    model_key=model_key,
                    genome_id=str(item["genome"].get("id", "")),
                    generation=generation,
                    det_profile=args.det_profile,
                )
            )
        structured_feedback_records.extend(generation_feedback_records)
        generation_feedback_summary = summarize_deterministic_feedback(generation_feedback_records)
        structured_feedback_summary_rows.extend(
            {**row, "generation": generation, "model_key": model_key} for row in generation_feedback_summary
        )
        generation_category_diagnostics = _category_diagnostics(
            generation=generation,
            model_key=model_key,
            evaluated_population=evaluated_population,
        )
        population_diagnostic_rows.extend(generation_category_diagnostics)
        if _redesign_enabled(args):
            generation_pareto_rows = build_pareto_rows(
                [_metric_for_eval(item) for item in evaluated_population if _metric_for_eval(item)],
                generation=generation,
                model_key=model_key,
                previous_frontier_ids={str(row.get("genome_id", "")) for row in pareto_archive_rows},
            )
            generation_pareto_summary = build_pareto_summary(generation_pareto_rows, generation=generation, model_key=model_key)
            pareto_generation_summary_rows.append(generation_pareto_summary)
            pareto_archive_delta = int(generation_pareto_summary.get("new_frontier", 0) or 0)
            pareto_archive_rows.extend([row for row in generation_pareto_rows if row.get("is_pareto_frontier")])
            unique_prompt_hash_count = len({(_metric_for_eval(item).prompt_hash if _metric_for_eval(item) else item["genome"]["id"]) for item in evaluated_population})
            controller = decide_next_action(
                generation_progress + [progress_record],
                generation=generation,
                max_generations=args.gens,
                min_generations=args.min_generations,
                plateau_window=args.plateau_window,
                target_detpass=args.target_detpass,
                pareto_archive_delta=pareto_archive_delta,
                unique_prompt_hash_count=unique_prompt_hash_count,
                population_size=args.population,
                advisor_enabled=bool(args.llm_mutation_advisor),
                advisor_trigger_mode=args.advisor_trigger_mode,
                disruptive_attempt_count=disruptive_attempt_count,
                disruptive_max_attempts=args.disruptive_max_attempts,
                compression_detpass_threshold=args.compression_detpass_threshold,
                compression_token_plateau_delta=args.compression_token_plateau_delta,
                aggressive_compression_after_target=args.aggressive_compression_after_target,
            )
            if controller.next_action == "trigger_disruptive_mutation":
                disruptive_attempt_count += 1
            args._generation_phase = controller.generation_phase
            args._plateau_type = controller.plateau_type
            args._next_action = controller.next_action
            args._advisor_triggered = controller.advisor_triggered
            progress_record.update(controller.to_row())
            progress_record["unique_prompt_hash_count"] = unique_prompt_hash_count
            progress_record["pareto_archive_size"] = len({str(row.get("genome_id", "")) for row in pareto_archive_rows})
            progress_record["pareto_archive_delta"] = pareto_archive_delta
            args._best_so_far_detpass = best_so_far_detpass
            accepted_metric_for_advisor = _metric_for_eval(accepted_best or {})
            args._accepted_best_detpass = (
                accepted_metric_for_advisor.validation_det_pass_rate
                if accepted_metric_for_advisor
                else 0.0
            )
            args._pareto_archive_size = len({str(row.get("genome_id", "")) for row in pareto_archive_rows})
            _attach_redesign_metrics(
                evaluated_population,
                args=args,
                accepted_best=accepted_best,
                generation_phase=controller.generation_phase,
                token_budget=token_budget,
                row_margin=validation_row_margin,
            )
            _sort_evaluated_population(evaluated_population, args)
            generation_best = evaluated_population[0]
            validation_progress = _metric_summary(generation_best["validation_metrics"])
            redesign_metric = _metric_for_eval(generation_best)
            if redesign_metric:
                validation_progress["det_pass_rate"] = redesign_metric.validation_det_pass_rate
                validation_progress["avg_det_score"] = redesign_metric.validation_avg_det_score
                validation_progress["variance"] = redesign_metric.det_score_variance
                validation_progress["avg_prompt_tokens"] = redesign_metric.avg_prompt_tokens
        # Record both estimated and measured token deltas.
        # expected_token_delta comes from the advisor/operator plan; measured deltas are
        # filled after evaluation when parent/child rendered prompt metrics are both present.
        if mutation_proposal_rows:
            _fill_measured_token_deltas(mutation_proposal_rows, evaluated_population)
        compression_ready = (
            float(best_so_far_detpass or 0.0) >= float(args.compression_detpass_threshold)
            or (
                bool(args.llm_mutation_advisor)
                and float(best_so_far_detpass or 0.0) >= float(args.advisor_prefer_compression_after_detpass)
            )
            or str(getattr(args, "_generation_phase", generation_phase)) == "COMPRESSION_SEARCH"
            or str(getattr(args, "_next_action", "")) in {"switch_compression", "switch_aggressive_compression"}
        )
        args._compression_ready = bool(compression_ready)
        progress_record["compression_ready"] = bool(compression_ready)
        progress_record["compression_detpass_threshold"] = float(args.compression_detpass_threshold)
        compression_phase = _compression_phase_for_generation(args, compression_ready=bool(compression_ready))
        args._compression_phase = compression_phase
        progress_record["compression_phase"] = compression_phase
        prompt_token_breakdown, block_token_breakdown = (
            _build_token_breakdowns(generation_best["genome"], generation=generation, model_key=model_key)
            if (args.enable_block_token_breakdown or args.enable_compression_mutation)
            else ({}, [])
        )
        args._prompt_token_breakdown = prompt_token_breakdown
        args._block_token_breakdown = block_token_breakdown
        if prompt_token_breakdown or block_token_breakdown:
            # Record block/profile estimates used by advisor target selection.
            # These are estimates until measured child token deltas are available after evaluation.
            dump_json(output_root / "prompt_token_breakdown.json", prompt_token_breakdown)
            dump_json(output_root / f"prompt_token_breakdown_generation_{generation:03d}.json", prompt_token_breakdown)
            dump_json(output_root / "block_token_breakdown.json", {"generation": generation, "rows": block_token_breakdown})
            dump_json(output_root / f"block_token_breakdown_generation_{generation:03d}.json", {"generation": generation, "rows": block_token_breakdown})

        replay_gate_pass = True
        regression_gate_pass = True
        rejection_reason = ""
        promoted = False
        if accepted_best is None:
            promoted = True
        else:
            if _redesign_enabled(args) and _metric_for_eval(generation_best):
                regression_gate_pass, rejection_reason = regression_gate(
                    _metric_for_eval(generation_best),
                    _accepted_metric_row(accepted_best),
                    margin=validation_row_margin,
                    category_balance_mode=args.category_balance_mode,
                )
                promoted = regression_gate_pass
            else:
                accepted_validation = _metric_summary(accepted_best["validation_metrics"])
                if validation_progress["avg_det_score"] < accepted_validation["avg_det_score"]:
                    regression_gate_pass = False
                    rejection_reason = "candidate regressed avg DET versus previous accepted prompt"
                elif validation_progress["det_pass_rate"] < accepted_validation["det_pass_rate"]:
                    regression_gate_pass = False
                    rejection_reason = "candidate regressed DETPass versus previous accepted prompt"
                else:
                    promoted = True
        accepted_prompt_path = ""
        previous_accepted_prompt = str((accepted_best or {}).get("genome", {}).get("id", ""))
        if promoted:
            accepted_best = generation_best
            progress_record["promoted_candidate"] = True
            accepted_prompt_path = str(output_root / "accepted_genomes" / f"generation_{generation:03d}_{generation_best['genome']['id']}.json")
            dump_json(accepted_prompt_path, generation_best["genome"])
        promotion_rows.append(
            {
                "generation": generation,
                "candidate_id": generation_best["genome"]["id"],
                "model_key": model_key,
                "DETPass": validation_progress["det_pass_rate"],
                "SDET": validation_progress["avg_det_score"],
                "avg_prompt_tokens": validation_progress["avg_prompt_tokens"],
                "replay_gate_pass": replay_gate_pass,
                "regression_gate_pass": regression_gate_pass,
                "promoted": promoted,
                "rejection_reason": rejection_reason,
                "accepted_prompt_path": accepted_prompt_path,
                "previous_accepted_prompt": previous_accepted_prompt,
            }
        )
        generation_progress.append(progress_record)
        best_history.append(
            {
                "generation": generation,
                "genome_id": generation_best["genome"]["id"],
                "fitness": generation_best["fitness"],
                "avg_det_score": generation_best["avg_det_score"],
                "validation_avg_det_score": generation_best["validation_avg_det_score"],
                "train_det_pass_rate": train_progress["det_pass_rate"],
                "train_gt_exact_rate": train_progress["gt_exact_rate"],
                "validation_det_pass_rate": validation_progress["det_pass_rate"],
                "validation_gt_exact_rate": validation_progress["gt_exact_rate"],
                "genome": generation_best["genome"],
            }
        )
        dump_json(
            output_root / "checkpoints" / f"ga_generation_{generation:03d}.json",
            {"generation": generation, "population": _checkpoint_population(evaluated_population)},
        )

        generation_top_rows: list[dict[str, Any]] = []
        for rank, item in enumerate(evaluated_population[: max(1, args.top_k)], start=1):
            validation = _metric_summary(item["validation_metrics"])
            item_active = active_block_summary(item["genome"])
            item_meta = item["genome"].get("_ga_metadata", {}) or {}
            item_metric = _metric_for_eval(item)
            top_row = {
                "generation": generation,
                "rank": rank,
                "model_key": model_key,
                "genome_id": item["genome"]["id"],
                "det": item_metric.validation_avg_det_score if item_metric else validation["avg_det_score"],
                "det_pass_rate": item_metric.validation_det_pass_rate if item_metric else validation["det_pass_rate"],
                "det_pass_count": validation["det_pass_count"],
                "row_count": validation["row_count"],
                "tokens": item_metric.avg_prompt_tokens if item_metric else validation["avg_prompt_tokens"],
                "core_blocks": ",".join(item_active["core"]),
                "optional_blocks": ",".join(item_active["optional"]),
                "parent_ids": ",".join(str(parent) for parent in item_meta.get("parent_ids", []) or []),
                "major_mutations": ",".join(str(mut) for mut in item_meta.get("mutation_types", []) or []),
                "advisor_proposal_id": item_meta.get("advisor_proposal_id", ""),
                "fitness": item["fitness"],
                "elite_reason": item.get("elite_reason", ""),
                "selection_reason": item.get("selection_reason", ""),
                "archive_membership": item.get("archive_membership", ""),
                "pareto_rank": item_metric.pareto_rank if item_metric else "",
                "prompt_hash": item_metric.prompt_hash if item_metric else "",
                "block_signature": item_metric.block_signature if item_metric else "",
                "rule_signature": item_metric.rule_signature if item_metric else "",
                "mutation_family": item_meta.get("mutation_family", ""),
                "mutation_operator": item_meta.get("mutation_operator", ""),
            }
            generation_top_rows.append(top_row)
            topk_rows.append(top_row)

        best_diffs = [
            {
                "generation": generation,
                "genome_id": generation_best["genome"]["id"],
                "base_genome_id": str((generation_best["genome"].get("_ga_metadata", {}) or {}).get("base_genome_id", "")),
                **diff,
            }
            for diff in (generation_best["genome"].get("_ga_metadata", {}) or {}).get("diffs", [])
        ]
        block_diff_rows.extend(best_diffs)

        if _redesign_enabled(args):
            archives = update_archives(
                archives,
                evaluated_population,
                accepted_best=accepted_best,
                generation=generation,
                one_row_margin=validation_row_margin,
                enable_group_specialists=bool(args.enable_group_specialist_archives or args.category_balance_mode == "routing"),
            )
            candidate_global = archives.global_best_detpass or generation_best
            if global_best is None or best_tie_key(
                _metric_for_eval(candidate_global) or metrics_from_evaluation(candidate_global),
                generation=generation,
            ) < best_tie_key(_metric_for_eval(global_best) or metrics_from_evaluation(global_best), generation=generation):
                global_best = candidate_global
                no_improvement_generations = 0
            else:
                no_improvement_generations += 1
        else:
            if global_best is None or float(generation_best["validation_avg_det_score"]) > float(global_best["validation_avg_det_score"]):
                global_best = generation_best
                no_improvement_generations = 0
            else:
                no_improvement_generations += 1

        if no_improvement_generations >= args.plateau_generations:
            feedback = run_feedback_loop(
                profile=args.profile,
                genome=generation_best["genome"],
                dataset_rows=selected_rows,
                service_schema=service_schema,
                validation_size=args.validation_size,
                candidate_k=max(1, min(args.candidate_k, 2)),
                attempts=args.feedback_attempts,
                improvement_threshold=args.feedback_threshold,
                llm_mode=args.llm_mode,
                llm_endpoint=args.llm_endpoint,
                timeout_sec=args.timeout_sec,
                retries=args.retries,
                seed=args.seed + generation,
            )
            feedback = feedback or {}
            if feedback.get("improved"):
                injected = feedback["best_genome"]
                injected_eval = _evaluate_one(
                    profile=args.profile,
                    genome=injected,
                    train_rows=train_rows,
                    validation_rows=validation_rows,
                    service_schema=service_schema,
                    candidate_k=args.candidate_k,
                    cheap_eval_limit=args.cheap_eval_limit,
                    llm_mode=args.llm_mode,
                    llm_endpoint=args.llm_endpoint,
                    timeout_sec=args.timeout_sec,
                    retries=args.retries,
                    alpha=args.alpha,
                    seed=args.seed + generation + 12345,
                    det_profile=args.det_profile,
                    output_root=output_root,
                )
                evaluated_population.append(injected_eval)
                evaluated_population.sort(
                    key=lambda item: (-float(item["fitness"]), -float(item["validation_avg_det_score"]), item["genome"]["id"])
                )
                generation_best = evaluated_population[0]
                if global_best is None or float(generation_best["validation_avg_det_score"]) > float(global_best["validation_avg_det_score"]):
                    global_best = generation_best
                no_improvement_generations = 0

        advisor_safe_proposals, advisor_rejected_proposals = _call_mutation_advisor(
            args=args,
            output_root=output_root,
            generation=generation,
            model_key=model_key,
            evaluated_population=evaluated_population,
            category_diagnostics=generation_category_diagnostics,
            feedback_summary=generation_feedback_summary,
        )
        advisor_final_proposals: list[MutationProposal] = []
        for proposal in advisor_rejected_proposals:
            rejected_mp = proposal_from_advisor(
                proposal,
                generation=generation,
                advisor_batch_id=str(proposal.get("advisor_batch_id", "")),
            )
            rejected_mp.accepted = False
            rejected_mp.proposal_state = PROPOSAL_STATE_REJECTED
            rejected_mp.rejection_reason = str(proposal.get("rejection_reason", "rejected by advisor proposal validation"))
            advisor_final_proposals.append(rejected_mp)

        advisor_can_schedule = bool(
            args.llm_mutation_advisor
            and advisor_safe_proposals
            and (args.advisor_force_child_quota or args.population >= args.advisor_min_population_for_child)
        )
        advisor_compression_proposals = sorted(
            [proposal for proposal in advisor_safe_proposals if _is_compression_proposal(proposal)],
            key=_compression_level_priority,
        )
        advisor_noncompression_proposals = [proposal for proposal in advisor_safe_proposals if not _is_compression_proposal(proposal)]
        advisor_scheduling_proposals = (
            advisor_compression_proposals + advisor_noncompression_proposals
            if compression_ready
            else advisor_safe_proposals
        )
        staged_compression_quotas = _staged_compression_quotas(
            args,
            compression_phase=str(getattr(args, "_compression_phase", "OFF")),
            population_size=args.population,
        )
        compression_child_quota = sum(staged_compression_quotas.values())
        advisor_child_quota = 1 if advisor_can_schedule else 0
        if compression_ready and advisor_can_schedule:
            if advisor_compression_proposals:
                advisor_child_quota = max(advisor_child_quota, int(args.advisor_compression_child_quota))
            elif compression_child_quota > 0:
                advisor_child_quota = 0
        advisor_child_quota = min(max(0, advisor_child_quota), max(0, args.population - 1))
        base_cloudless_child_quota = 1 if (
            args.mutation_mode in {"family", "cloudless_decompiler", "hybrid"} or args.enable_compression_mutation
        ) else 0
        cloudless_child_quota = base_cloudless_child_quota
        if _compression_fallback_enabled(args):
            cloudless_child_quota = min(
                max(0, args.population - 1),
                base_cloudless_child_quota + compression_child_quota,
            )
        if _redesign_enabled(args):
            elite_target = 3 if args.population <= 5 else max(args.elites, 5)
            reserved_children = min(args.population - 1, advisor_child_quota + cloudless_child_quota)
            elite_quota = max(1, min(args.population - reserved_children, elite_target))
            elite_items = quota_elites(
                evaluated_population,
                archives,
                population_size=elite_quota,
                category_balance_mode=args.category_balance_mode,
                one_row_margin=validation_row_margin,
            )
            elites = [item["genome"] for item in elite_items]
        else:
            elite_count = max(1, min(args.elites, args.population - advisor_child_quota))
            elite_items = evaluated_population[:elite_count]
            elites = [item["genome"] for item in elite_items]
        next_population: list[dict[str, Any]] = [_copy_genome(genome) for genome in elites]
        new_by_crossover = 0
        new_by_mutation = 0
        new_by_advisor = 0
        new_by_compression = 0
        new_by_diversity = 0
        new_by_specialist = 0
        new_by_disruptive = 0
        new_random = 0
        advisor_proposals_generated = len(advisor_safe_proposals) + len(advisor_rejected_proposals)
        advisor_proposals_accepted_applied = 0
        advisor_proposals_accepted_not_scheduled = 0
        advisor_proposals_rejected = len(advisor_rejected_proposals)
        advisor_children_scheduled = 0
        advisor_compression_children_scheduled = 0
        cloudless_compression_fallback_scheduled = 0
        fallback_used_this_generation = False
        fallback_reason_this_generation = ""
        if compression_ready and _compression_fallback_enabled(args):
            rejection_reasons = {str(item.get("rejection_reason", "")) for item in advisor_rejected_proposals}
            if "no_advisor_proposals_parsed" in rejection_reasons:
                fallback_reason_this_generation = "no_valid_advisor_proposal"
            elif advisor_rejected_proposals and not advisor_safe_proposals:
                fallback_reason_this_generation = "all_advisor_proposals_rejected"
            elif not advisor_compression_proposals:
                fallback_reason_this_generation = "no_valid_advisor_proposal"
        new_by_micro_compression = 0
        new_by_block_compression = 0
        new_by_multi_block_compression = 0
        new_by_global_budget_compression = 0
        feedback_hint = suggest_mutation_from_feedback(generation_feedback_summary) if args.feedback_guided_mutation else None
        active_failure_families = [str(item.get("affected_block_family", "")) for item in generation_feedback_summary]
        if args.enable_prompt_decompiler or args.mutation_mode in {"cloudless_decompiler", "hybrid"}:
            artifact = decompile_prompt(
                json.dumps(generation_best["genome"].get("block_params", {}), ensure_ascii=False, sort_keys=True),
                active_failure_families=active_failure_families,
            )
            for unit in artifact.units:
                row = unit.to_row()
                row.update({"generation": generation, "model_key": model_key, "genome_id": generation_best["genome"]["id"]})
                prompt_unit_rows.append(row)
        if (
            args.mutation_mode in {"family", "cloudless_decompiler", "hybrid"}
            or args.enable_compression_mutation
            or (compression_ready and _compression_fallback_enabled(args))
        ):
            cloudless_proposals = (
                _cloudless_mutation_proposals(
                    generation=generation + 1,
                    parent_genome=generation_best["genome"],
                    feedback_hint=feedback_hint,
                    args=args,
                    rng=rng,
                    active_failure_families=active_failure_families,
                )
                if args.mutation_mode in {"family", "cloudless_decompiler", "hybrid"} or args.enable_compression_mutation
                else []
            )
            for level, quota in staged_compression_quotas.items():
                existing_for_level = sum(1 for item in cloudless_proposals if _is_compression_proposal(item) and _compression_level(item) == level)
                while existing_for_level < quota:
                    lane_proposal = _make_compression_lane_proposal(
                        level=level,
                        generation=generation + 1,
                        parent_genome=generation_best["genome"],
                        block_token_breakdown=block_token_breakdown,
                        prompt_token_breakdown={**prompt_token_breakdown, "compression_phase": str(getattr(args, "_compression_phase", ""))},
                        rng=rng,
                        source="cloudless",
                    )
                    if lane_proposal is None:
                        break
                    cloudless_proposals.insert(0, lane_proposal)
                    existing_for_level += 1
            if compression_ready and not any(_is_compression_proposal(proposal) for proposal in cloudless_proposals):
                # Compression fallback path.
                # If advisor/cloudless proposals are absent or invalid, add the next safe compression operator
                # so compression-ready generations still explore meaningful token reduction.
                fallback_proposal = _make_compression_lane_proposal(
                    level="block",
                    generation=generation + 1,
                    parent_genome=generation_best["genome"],
                    block_token_breakdown=block_token_breakdown,
                    prompt_token_breakdown={**prompt_token_breakdown, "compression_phase": str(getattr(args, "_compression_phase", ""))},
                    rng=rng,
                    source="compression_fallback",
                ) or _make_compression_lane_proposal(
                    level="micro",
                    generation=generation + 1,
                    parent_genome=generation_best["genome"],
                    block_token_breakdown=block_token_breakdown,
                    prompt_token_breakdown={**prompt_token_breakdown, "compression_phase": str(getattr(args, "_compression_phase", ""))},
                    rng=rng,
                    source="compression_fallback",
                )
                if fallback_proposal is None:
                    fallback_proposal = proposal_for_family(
                        family="compression",
                        generation=generation + 1,
                        parent_genome_id=str(generation_best["genome"].get("id", "")),
                        feedback_hint=None,
                        rng=rng,
                        aggressive_compression=True,
                    )
                fallback_proposal.source = "compression_fallback"
                fallback_proposal.fallback_reason = fallback_reason_this_generation or "no_valid_advisor_proposal"
                cloudless_proposals.insert(0, fallback_proposal)
            if compression_ready:
                cloudless_proposals = sorted(cloudless_proposals, key=lambda item: 0 if _is_compression_proposal(item) else 1)
            for proposal in cloudless_proposals:
                if compression_ready and _is_compression_proposal(proposal) and not advisor_compression_proposals:
                    proposal.source = "compression_fallback"
                    if not proposal.fallback_reason:
                        proposal.fallback_reason = fallback_reason_this_generation or "no_valid_advisor_proposal"
                if len(next_population) >= args.population - advisor_child_quota:
                    proposal.accepted = False
                    proposal.rejection_reason = "population full before cloudless proposal could be added"
                    mutation_proposal_rows.append(_proposal_to_row(proposal))
                    continue
                child, child_diffs = apply_mutation_proposal(generation_best["genome"], proposal, rng=rng)
                if _is_compression_proposal(proposal) and not child_diffs:
                    # Retry no-op compression with stronger safe operators before giving up on this child.
                    for retry_operator in (
                        "drop_optional_blocks_for_budget",
                        "reduce_few_shot_count_to_zero",
                        "prune_micro_rules_to_top_k",
                        "compact_reasoning_skeleton",
                        "compact_block_params",
                        "lower_output_max_tokens_aggressive",
                        "compress_candidate_strategies_to_minimal",
                    ):
                        if retry_operator == proposal.operator:
                            continue
                        proposal.operator = retry_operator
                        child, child_diffs = apply_mutation_proposal(generation_best["genome"], proposal, rng=rng)
                        if child_diffs:
                            break
                if _is_compression_proposal(proposal) and not child_diffs:
                    proposal.accepted = False
                    proposal.rejection_reason = "compression proposal produced no genome diff"
                    mutation_proposal_rows.append(_proposal_to_row(proposal))
                    if proposal.source == "compression_fallback":
                        fallback_used_this_generation = True
                        fallback_reason_this_generation = proposal.fallback_reason or fallback_reason_this_generation or "no_valid_advisor_proposal"
                    continue
                proposal.child_genome_id = child["id"]
                proposal.accepted = True
                next_population.append(child)
                mutation_proposal_rows.append(_proposal_to_row(proposal))
                mutation_operator_credit_rows.append(
                    {
                        "generation": generation + 1,
                        "mutation_family": proposal.mutation_family,
                        "mutation_operator": proposal.operator,
                        "parent_genome_id": proposal.parent_genome_id,
                        "child_genome_id": child["id"],
                        "delta_DETPass": "",
                        "delta_AvgDET": "",
                        "delta_tokens": "",
                        "delta_latency": "",
                        "delta_basic_DETPass": "",
                        "delta_temporal_DETPass": "",
                        "delta_complex_DETPass": "",
                        "accepted": True,
                        "elite_reason": "",
                        "operator_credit": "",
                    }
                )
                new_by_mutation += 1
                if proposal.mutation_family == "compression":
                    new_by_compression += 1
                    level = _compression_level(proposal)
                    if level == "micro":
                        new_by_micro_compression += 1
                    elif level == "block":
                        new_by_block_compression += 1
                    elif level == "multi_block":
                        new_by_multi_block_compression += 1
                    elif level == "global_budget":
                        new_by_global_budget_compression += 1
                    if proposal.source == "compression_fallback":
                        cloudless_compression_fallback_scheduled += 1
                        fallback_used_this_generation = True
                        fallback_reason_this_generation = proposal.fallback_reason or fallback_reason_this_generation or "no_valid_advisor_proposal"
                elif proposal.mutation_family == "diversity":
                    new_by_diversity += 1
                elif proposal.mutation_family == "specialist":
                    new_by_specialist += 1
                if str(progress_record.get("next_action", "")).startswith("trigger_disruptive"):
                    new_by_disruptive += 1
                block_diff_rows.extend(
                    {
                        "generation": generation + 1,
                        "genome_id": child["id"],
                        "base_genome_id": str((child.get("_ga_metadata", {}) or {}).get("base_genome_id", "")),
                        **diff,
                    }
                    for diff in child_diffs
                )
        for proposal in advisor_scheduling_proposals:
            parent = _copy_genome(generation_best["genome"])
            advisor_batch_id_value = str(proposal.get("advisor_batch_id", ""))
            if not advisor_can_schedule:
                mp = proposal_from_advisor(proposal, generation=generation, advisor_batch_id=advisor_batch_id_value)
                mp.parent_genome_id = str(parent.get("id", ""))
                mp.accepted = False
                mp.proposal_state = PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED
                mp.scheduling_reason = (
                    "population below advisor_min_population_for_child"
                    if args.population < args.advisor_min_population_for_child and not args.advisor_force_child_quota
                    else "advisor child quota unavailable"
                )
                advisor_final_proposals.append(mp)
                advisor_proposals_accepted_not_scheduled += 1
                continue
            if len(next_population) >= args.population:
                mp = proposal_from_advisor(proposal, generation=generation, advisor_batch_id=advisor_batch_id_value)
                mp.parent_genome_id = str(parent.get("id", ""))
                mp.accepted = False
                mp.proposal_state = PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED
                mp.scheduling_reason = "population quota unavailable"
                advisor_final_proposals.append(mp)
                advisor_proposals_accepted_not_scheduled += 1
                continue
            try:
                child, child_diffs, mp = apply_advisor_proposal(
                    parent,
                    proposal,
                    generation=generation,
                    advisor_batch_id_value=advisor_batch_id_value,
                    rng=rng,
                )
            except Exception as exc:
                mp = proposal_from_advisor(proposal, generation=generation, advisor_batch_id=advisor_batch_id_value)
                mp.parent_genome_id = str(parent.get("id", ""))
                mp.accepted = False
                mp.proposal_state = PROPOSAL_STATE_FAILED_TO_APPLY
                mp.rejection_reason = f"failed to apply advisor proposal: {exc}"
                advisor_final_proposals.append(mp)
                continue
            existing_signatures = {_genome_signature(genome): str(genome.get("id", "")) for genome in next_population}
            child_signature = _genome_signature(child)
            if child_signature in existing_signatures:
                mp.accepted = False
                mp.proposal_state = PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED
                mp.scheduling_reason = "duplicate_removed"
                mp.advisor_child_duplicate = True
                mp.duplicate_of = existing_signatures[child_signature]
                advisor_final_proposals.append(mp)
                advisor_proposals_accepted_not_scheduled += 1
                continue
            mp.accepted = True
            mp.proposal_state = PROPOSAL_STATE_ACCEPTED_APPLIED
            mp.scheduling_reason = "scheduled_into_next_population"
            next_population.append(child)
            new_by_advisor += 1
            new_by_mutation += 1
            advisor_proposals_accepted_applied += 1
            advisor_children_scheduled += 1
            if mp.mutation_family == "compression" or mp.operator in COMPRESSION_MUTATION_TYPES:
                advisor_compression_children_scheduled += 1
                level = _compression_level(mp)
                if level == "micro":
                    new_by_micro_compression += 1
                elif level == "block":
                    new_by_block_compression += 1
                elif level == "multi_block":
                    new_by_multi_block_compression += 1
                elif level == "global_budget":
                    new_by_global_budget_compression += 1
            advisor_final_proposals.append(mp)
            mutation_operator_credit_rows.append(
                {
                    "generation": generation + 1,
                    "mutation_family": mp.mutation_family,
                    "mutation_operator": mp.operator,
                    "parent_genome_id": mp.parent_genome_id,
                    "child_genome_id": child["id"],
                    "delta_DETPass": "",
                    "delta_AvgDET": "",
                    "delta_tokens": "",
                    "delta_latency": "",
                    "delta_basic_DETPass": "",
                    "delta_temporal_DETPass": "",
                    "delta_complex_DETPass": "",
                    "accepted": True,
                    "elite_reason": "",
                    "operator_credit": "",
                }
            )
            block_diff_rows.extend(
                {
                    "generation": generation + 1,
                    "genome_id": child["id"],
                    "base_genome_id": str((child.get("_ga_metadata", {}) or {}).get("base_genome_id", "")),
                    **diff,
                }
                for diff in child_diffs
            )
        while (
            compression_ready
            and _compression_fallback_enabled(args)
            and (new_by_compression + advisor_compression_children_scheduled) < compression_child_quota
            and len(next_population) < args.population
        ):
            # Compression fallback path.
            # Rejected/no-op advisor compression should not leave a compression-ready generation unexplored.
            # Source is recorded as compression_fallback for artifact audits.
            fallback_proposal = _make_compression_lane_proposal(
                level="block",
                generation=generation + 1,
                parent_genome=generation_best["genome"],
                block_token_breakdown=block_token_breakdown,
                prompt_token_breakdown={**prompt_token_breakdown, "compression_phase": str(getattr(args, "_compression_phase", ""))},
                rng=rng,
                source="compression_fallback",
            ) or _make_compression_lane_proposal(
                level="micro",
                generation=generation + 1,
                parent_genome=generation_best["genome"],
                block_token_breakdown=block_token_breakdown,
                prompt_token_breakdown={**prompt_token_breakdown, "compression_phase": str(getattr(args, "_compression_phase", ""))},
                rng=rng,
                source="compression_fallback",
            )
            if fallback_proposal is None:
                fallback_proposal = proposal_for_family(
                    family="compression",
                    generation=generation + 1,
                    parent_genome_id=str(generation_best["genome"].get("id", "")),
                    feedback_hint=None,
                    rng=rng,
                    aggressive_compression=True,
                )
            fallback_proposal.source = "compression_fallback"
            fallback_proposal.fallback_reason = fallback_reason_this_generation or "quota_unfilled"
            child, child_diffs = apply_mutation_proposal(generation_best["genome"], fallback_proposal, rng=rng)
            if not child_diffs:
                for retry_operator in (
                    "drop_optional_blocks_for_budget",
                    "reduce_few_shot_count_to_zero",
                    "prune_micro_rules_to_top_k",
                    "compact_reasoning_skeleton",
                    "compact_block_params",
                    "lower_output_max_tokens_aggressive",
                    "compress_candidate_strategies_to_minimal",
                ):
                    fallback_proposal.operator = retry_operator
                    child, child_diffs = apply_mutation_proposal(generation_best["genome"], fallback_proposal, rng=rng)
                    if child_diffs:
                        break
            if not child_diffs:
                fallback_proposal.accepted = False
                fallback_proposal.rejection_reason = "compression fallback produced no genome diff"
                mutation_proposal_rows.append(_proposal_to_row(fallback_proposal))
                fallback_used_this_generation = True
                fallback_reason_this_generation = fallback_proposal.fallback_reason or fallback_reason_this_generation or "quota_unfilled"
                break
            fallback_proposal.child_genome_id = child["id"]
            fallback_proposal.accepted = True
            next_population.append(child)
            mutation_proposal_rows.append(_proposal_to_row(fallback_proposal))
            mutation_operator_credit_rows.append(
                {
                    "generation": generation + 1,
                    "mutation_family": fallback_proposal.mutation_family,
                    "mutation_operator": fallback_proposal.operator,
                    "parent_genome_id": fallback_proposal.parent_genome_id,
                    "child_genome_id": child["id"],
                    "delta_DETPass": "",
                    "delta_AvgDET": "",
                    "delta_tokens": "",
                    "delta_latency": "",
                    "delta_basic_DETPass": "",
                    "delta_temporal_DETPass": "",
                    "delta_complex_DETPass": "",
                    "accepted": True,
                    "elite_reason": "",
                    "operator_credit": "",
                }
            )
            new_by_mutation += 1
            new_by_compression += 1
            level = _compression_level(fallback_proposal)
            if level == "micro":
                new_by_micro_compression += 1
            elif level == "block":
                new_by_block_compression += 1
            elif level == "multi_block":
                new_by_multi_block_compression += 1
            elif level == "global_budget":
                new_by_global_budget_compression += 1
            cloudless_compression_fallback_scheduled += 1
            fallback_used_this_generation = True
            fallback_reason_this_generation = fallback_proposal.fallback_reason or fallback_reason_this_generation or "quota_unfilled"
            block_diff_rows.extend(
                {
                    "generation": generation + 1,
                    "genome_id": child["id"],
                    "base_genome_id": str((child.get("_ga_metadata", {}) or {}).get("base_genome_id", "")),
                    **diff,
                }
                for diff in child_diffs
            )
        if args.llm_mutation_advisor:
            final_rejected_for_plan = [
                proposal
                for proposal in advisor_final_proposals
                if proposal.proposal_state in {PROPOSAL_STATE_REJECTED, PROPOSAL_STATE_FAILED_TO_APPLY}
            ]
            final_accepted_for_plan = [
                proposal
                for proposal in advisor_final_proposals
                if proposal.proposal_state not in {PROPOSAL_STATE_REJECTED, PROPOSAL_STATE_FAILED_TO_APPLY}
            ]
            _write_advisor_block_compression_plan(
                output_root,
                generation=generation,
                compression_phase=str(getattr(args, "_compression_phase", "")),
                accepted_proposals=final_accepted_for_plan,
                rejected_proposals=final_rejected_for_plan,
                fallback_used=fallback_used_this_generation,
                fallback_reason=fallback_reason_this_generation,
            )
        for proposal in advisor_final_proposals:
            row = _proposal_to_row(proposal)
            advisor_proposal_rows.append(row)
            mutation_proposal_rows.append(row)
        if args.llm_mutation_advisor:
            advisor_summary_rows.append(
                {
                    "generation": generation,
                    "model_key": model_key,
                    "advisor_proposals_generated": advisor_proposals_generated,
                    "accepted_proposals": advisor_proposals_accepted_applied,
                    "rejected_proposals": advisor_proposals_rejected,
                    "advisor_proposals_accepted_applied": advisor_proposals_accepted_applied,
                    "advisor_proposals_accepted_not_scheduled": advisor_proposals_accepted_not_scheduled,
                    "advisor_proposals_rejected": advisor_proposals_rejected,
                    "advisor_children_scheduled": advisor_children_scheduled,
                    "advisor_compression_proposals": len(advisor_compression_proposals),
                    "advisor_compression_children_scheduled": advisor_compression_children_scheduled,
                    "proposal_ids": ",".join(str(item.proposal_id) for item in advisor_final_proposals),
                }
            )
        while len(next_population) < args.population:
            parent_a = _tournament_select(evaluated_population, rng)
            child_diffs: list[dict[str, Any]] = []
            if rng.random() < args.crossover_rate and len(evaluated_population) > 1:
                parent_b = _tournament_select(evaluated_population, rng)
                child, crossover_meta = _crossover(parent_a, parent_b, rng)
                new_by_crossover += 1
            else:
                child = _copy_genome(parent_a)
                child["id"] = f"gen-{seeded_uuid(rng)}"
                child["seed"] = rng.randint(1, 10**9)
                child = _annotate_genome(
                    child,
                    parent_ids=[str(parent_a.get("id", ""))],
                    mutation_types=[],
                    crossover_used=False,
                    base_genome_id=str(parent_a.get("id", "")),
                )
            if rng.random() < args.mutation_rate:
                chosen_hint = feedback_hint if args.feedback_guided_mutation and feedback_hint and rng.random() < 0.75 else None
                child, child_diffs = _mutate_genome(child, rng, feedback_hint=chosen_hint)
                new_by_mutation += 1
                block_diff_rows.extend(
                    {
                        "generation": generation + 1,
                        "genome_id": child["id"],
                        "base_genome_id": str((child.get("_ga_metadata", {}) or {}).get("base_genome_id", "")),
                        **diff,
                    }
                    for diff in child_diffs
                )
            next_population.append(child)
        next_population, duplicates_removed = _dedupe_population(next_population)
        while len(next_population) < args.population:
            next_population.append(_random_genome(base_genome, rng))
            new_random += 1
        population = next_population[: args.population]

        _write_ga_resume_state(
            output_root=output_root,
            generation=generation,
            next_population=population,
            rng=rng,
            global_best=global_best,
            accepted_best=accepted_best,
            no_improvement_generations=no_improvement_generations,
        )
        
        transition = {
            "generation": generation,
            "generation_phase": str(getattr(args, "_generation_phase", generation_phase)),
            "next_action": str(getattr(args, "_next_action", "")),
            "compression_ready": bool(compression_ready),
            "compression_phase": str(getattr(args, "_compression_phase", "")),
            "micro_compression_child_quota": staged_compression_quotas.get("micro", 0),
            "block_compression_child_quota": staged_compression_quotas.get("block", 0),
            "multi_block_compression_child_quota": staged_compression_quotas.get("multi_block", 0),
            "global_budget_compression_child_quota": staged_compression_quotas.get("global_budget", 0),
            "compression_child_quota": compression_child_quota,
            "compression_children_scheduled": new_by_compression + advisor_compression_children_scheduled,
            "advisor_compression_proposals": len(advisor_compression_proposals),
            "advisor_compression_children_scheduled": advisor_compression_children_scheduled,
            "cloudless_compression_fallback_scheduled": cloudless_compression_fallback_scheduled,
            "new_by_compression_fallback": cloudless_compression_fallback_scheduled,
            "survived_elites": len(elites),
            "survived_global_best": any(str(genome.get("id", "")) == str(((archives.global_best_detpass or {}).get("genome") or {}).get("id", "")) for genome in elites) if _redesign_enabled(args) else "",
            "survived_accepted_best": any(str(genome.get("id", "")) == str(((accepted_best or {}).get("genome") or {}).get("id", "")) for genome in elites) if _redesign_enabled(args) else "",
            "new_by_crossover": new_by_crossover,
            "new_by_mutation": new_by_mutation,
            "new_by_advisor": new_by_advisor,
            "new_by_compression": new_by_compression,
            "new_by_micro_compression": new_by_micro_compression,
            "new_by_block_compression": new_by_block_compression,
            "new_by_multi_block_compression": new_by_multi_block_compression,
            "new_by_global_budget_compression": new_by_global_budget_compression,
            "new_by_diversity": new_by_diversity,
            "new_by_specialist": new_by_specialist,
            "new_by_disruptive": new_by_disruptive,
            "new_random": new_random,
            "duplicates_removed": duplicates_removed,
            "duplicates_removed_by_prompt_hash": 0,
            "refill_reason": "dedupe_refill" if new_random else "",
            "next_population": len(population),
            "promotion_rejected": 0 if promoted else 1,
            "advisor_proposals_generated": advisor_proposals_generated,
            "advisor_proposals_accepted_applied": advisor_proposals_accepted_applied,
            "advisor_proposals_accepted_not_scheduled": advisor_proposals_accepted_not_scheduled,
            "advisor_proposals_rejected": advisor_proposals_rejected,
            "advisor_children_scheduled": advisor_children_scheduled,
        }
        population_transition_rows.append(transition)

        _print_generation(
            args,
            generation=generation,
            evaluated_count=len(evaluated_population),
            transition=transition,
            top_records=generation_top_rows,
            best_diffs=best_diffs,
            feedback_summary=generation_feedback_summary,
            category_diagnostics=generation_category_diagnostics,
            advisor_summary=advisor_summary_rows[-1] if advisor_summary_rows and advisor_summary_rows[-1].get("generation") == generation else None,
            advisor_proposals=advisor_safe_proposals,
            previous_best=previous_generation_best,
        )
        previous_generation_best = generation_best

        dump_json(output_root / "best_genomes.json", best_history)
        atomic_write_csv(
            output_root / "ga_generation_progress.csv",
            list(progress_record.keys()),
            generation_progress,
        )
        _write_jsonl(output_root / "ga_generation_progress.jsonl", generation_progress)
        atomic_write_csv(output_root / "ga_topk_genomes.csv", list(topk_rows[0].keys()), topk_rows)
        _write_jsonl(output_root / "ga_block_diffs.jsonl", block_diff_rows)
        if population_diagnostic_rows:
            atomic_write_csv(output_root / "ga_population_diagnostics.csv", list(population_diagnostic_rows[0].keys()), population_diagnostic_rows)
        else:
            atomic_write_csv(output_root / "ga_population_diagnostics.csv", ["generation", "model_key", "category"], [])
        _write_jsonl(output_root / "ga_population_diagnostics.jsonl", population_diagnostic_rows)
        _write_jsonl(output_root / "advisor_mutation_proposals.jsonl", advisor_proposal_rows)
        advisor_csv_rows = _advisor_mutation_summary_rows(advisor_proposal_rows)
        if advisor_csv_rows:
            atomic_write_csv(output_root / "advisor_mutation_summary.csv", ADVISOR_MUTATION_SUMMARY_COLUMNS, advisor_csv_rows)
        else:
            atomic_write_csv(output_root / "advisor_mutation_summary.csv", ADVISOR_MUTATION_SUMMARY_COLUMNS, [])
        _write_redesign_artifacts(
            output_root,
            mutation_proposal_rows=mutation_proposal_rows,
            mutation_operator_credit_rows=mutation_operator_credit_rows,
            pareto_archive_rows=pareto_archive_rows,
            prompt_unit_rows=prompt_unit_rows,
        )
        if pareto_archive_rows:
            atomic_write_csv(output_root / "ga_pareto_frontier.csv", list(pareto_archive_rows[0].keys()), pareto_archive_rows)
        else:
            atomic_write_csv(output_root / "ga_pareto_frontier.csv", PARETO_COLUMNS, [])
        _write_jsonl(output_root / "ga_pareto_frontier.jsonl", pareto_archive_rows)
        if pareto_generation_summary_rows:
            atomic_write_csv(output_root / "ga_pareto_generation_summary.csv", list(pareto_generation_summary_rows[0].keys()), pareto_generation_summary_rows)
        else:
            atomic_write_csv(output_root / "ga_pareto_generation_summary.csv", PARETO_SUMMARY_COLUMNS, [])
        _write_jsonl(output_root / "ga_pareto_generation_summary.jsonl", pareto_generation_summary_rows)
        _write_jsonl(output_root / "structured_feedback.jsonl", structured_feedback_records)
        if structured_feedback_summary_rows:
            atomic_write_csv(output_root / "structured_feedback_summary.csv", list(structured_feedback_summary_rows[0].keys()), structured_feedback_summary_rows)
        else:
            atomic_write_csv(output_root / "structured_feedback_summary.csv", ["generation", "model_key", "failure_type", "failure_count"], [])
        atomic_write_csv(output_root / "population_transitions.csv", list(population_transition_rows[0].keys()), population_transition_rows)
        atomic_write_csv(output_root / "promotion_decisions.csv", PROMOTION_COLUMNS, promotion_rows)
        dump_json(output_root / "promotion_decisions.json", {"rows": promotion_rows})

    final_best = archives.global_best_detpass or global_best or {}
    final_best_metric = _safe_metric(final_best)
    latest_promoted = _latest_promoted_row(promotion_rows)
    accepted_metric = _safe_metric(accepted_best)
    accepted_best_genome_id = str(((accepted_best or {}).get("genome") or {}).get("id", ""))
    accepted_best_detpass: float | None = accepted_metric.validation_det_pass_rate if accepted_metric else None
    accepted_best_avgdet: float | None = accepted_metric.validation_avg_det_score if accepted_metric else None
    accepted_best_tokens: float | None = accepted_metric.avg_prompt_tokens if accepted_metric else None
    if latest_promoted:
        accepted_best_genome_id = str(latest_promoted.get("candidate_id", "") or accepted_best_genome_id)
        accepted_best_detpass = float(latest_promoted.get("DETPass") or 0.0)
        accepted_best_avgdet = float(latest_promoted.get("SDET") or 0.0)
        accepted_best_tokens = float(latest_promoted.get("avg_prompt_tokens") or 0.0)

    compact_item = archives.compact_best_within_epsilon
    compact_metric = _safe_metric(compact_item)
    compact_eligible = bool(
        compact_metric
        and compact_metric.validation_det_pass_rate >= float(best_so_far_detpass or 0.0) - validation_row_margin
    )
    compact_best_genome_id = str(((compact_item or {}).get("genome") or {}).get("id", "")) if compact_eligible else ""
    compact_best_detpass = compact_metric.validation_det_pass_rate if compact_metric and compact_eligible else None
    compact_best_tokens = compact_metric.avg_prompt_tokens if compact_metric and compact_eligible else None
    token_minimal_unconstrained_genome_id = (
        str(((compact_item or {}).get("genome") or {}).get("id", ""))
        if compact_metric and not compact_eligible
        else ""
    )
    advisor_generated_count = sum(1 for row in mutation_proposal_rows if row.get("source") == "advisor")
    advisor_applied_count = sum(
        1
        for row in mutation_proposal_rows
        if row.get("source") == "advisor" and row.get("proposal_state") == PROPOSAL_STATE_ACCEPTED_APPLIED
    )
    advisor_not_scheduled_count = sum(
        1
        for row in mutation_proposal_rows
        if row.get("source") == "advisor" and row.get("proposal_state") == PROPOSAL_STATE_ACCEPTED_NOT_SCHEDULED
    )
    advisor_rejected_count = sum(
        1
        for row in mutation_proposal_rows
        if row.get("source") == "advisor" and row.get("proposal_state") == PROPOSAL_STATE_REJECTED
    )
    advisor_children_scheduled_count = sum(int(row.get("advisor_children_scheduled") or 0) for row in population_transition_rows)
    advisor_compression_generated_count = sum(
        1
        for row in mutation_proposal_rows
        if row.get("source") == "advisor"
        and (row.get("mutation_family") == "compression" or row.get("operator") in COMPRESSION_MUTATION_TYPES)
    )
    advisor_compression_children_scheduled_count = sum(
        int(row.get("advisor_compression_children_scheduled") or 0) for row in population_transition_rows
    )
    cloudless_compression_fallback_scheduled_count = sum(
        int(row.get("cloudless_compression_fallback_scheduled") or 0) for row in population_transition_rows
    )
    compression_fallback_count = sum(
        int(row.get("new_by_compression_fallback") or row.get("cloudless_compression_fallback_scheduled") or 0)
        for row in population_transition_rows
    )
    micro_compression_count = sum(int(row.get("new_by_micro_compression") or 0) for row in population_transition_rows)
    block_compression_count = sum(int(row.get("new_by_block_compression") or 0) for row in population_transition_rows)
    multi_block_compression_count = sum(int(row.get("new_by_multi_block_compression") or 0) for row in population_transition_rows)
    global_budget_compression_count = sum(int(row.get("new_by_global_budget_compression") or 0) for row in population_transition_rows)
    compression_ready_final = bool(
        float(best_so_far_detpass or 0.0) >= float(args.compression_detpass_threshold)
        or str(getattr(args, "_generation_phase", "")) == "COMPRESSION_SEARCH"
    )
    summary = {
        "best_history": best_history,
        "output_root": str(output_root),
        "generation_progress_csv": str(output_root / "ga_generation_progress.csv"),
        "generation_progress_jsonl": str(output_root / "ga_generation_progress.jsonl"),
        "topk_genomes_csv": str(output_root / "ga_topk_genomes.csv"),
        "block_diffs_jsonl": str(output_root / "ga_block_diffs.jsonl"),
        "population_diagnostics_csv": str(output_root / "ga_population_diagnostics.csv"),
        "population_diagnostics_jsonl": str(output_root / "ga_population_diagnostics.jsonl"),
        "advisor_feedback_batches_jsonl": str(output_root / "advisor_feedback_batches.jsonl"),
        "advisor_mutation_proposals_jsonl": str(output_root / "advisor_mutation_proposals.jsonl"),
        "advisor_mutation_summary_csv": str(output_root / "advisor_mutation_summary.csv"),
        "structured_feedback_jsonl": str(output_root / "structured_feedback.jsonl"),
        "structured_feedback_summary_csv": str(output_root / "structured_feedback_summary.csv"),
        "population_transitions_csv": str(output_root / "population_transitions.csv"),
        "promotion_decisions_csv": str(output_root / "promotion_decisions.csv"),
        "mutation_proposals_jsonl": str(output_root / "mutation_proposals.jsonl"),
        "pareto_archive_csv": str(output_root / "pareto_archive.csv"),
        "mutation_operator_credit_csv": str(output_root / "mutation_operator_credit.csv"),
        "best_genome": final_best.get("genome") if final_best else None,
        "best_fitness": final_best.get("fitness") if final_best else None,
        "best_validation_avg_det_score": final_best.get("validation_avg_det_score") if final_best else None,
        "best_DETPass": final_best_metric.validation_det_pass_rate if final_best_metric else (best_so_far_detpass if generation_progress else None),
        "best_avg_DET": final_best_metric.validation_avg_det_score if final_best_metric else (best_so_far_avgdet if generation_progress else None),
        "best_genome_id": str(((final_best or {}).get("genome") or {}).get("id", "")),
        "best_generation": next(
            (
                int(float(row.get("generation") or 0))
                for row in generation_progress
                if str(row.get("genome_id", "")) == str(((final_best or {}).get("genome") or {}).get("id", ""))
            ),
            "",
        ),
        "fitness_formula": (
            "phase-aware DETPass + AvgDET + category/compression - token/variance/regression penalties"
            if args.fitness_mode != "legacy"
            else f"AvgDET - {args.alpha} * VarDET"
        ),
        "retrieval_policy": "fixed runtime service-context construction; not mutated by GA",
        "stage": str(getattr(args, "stage_name", "ga")),
        "advisor_status": "enabled" if args.llm_mutation_advisor else "skipped",
        "final_phase": str(getattr(args, "_generation_phase", "")),
        "stop_reason": generation_progress[-1].get("stop_reason", "") if generation_progress else "",
        "best_so_far_DETPass": best_so_far_detpass,
        "accepted_best": accepted_best_genome_id,
        "accepted_best_genome_id": accepted_best_genome_id,
        "accepted_best_DETPass": accepted_best_detpass,
        "accepted_best_avg_DET": accepted_best_avgdet,
        "accepted_best_tokens": accepted_best_tokens,
        "compact_best": compact_best_genome_id,
        "compact_best_genome_id": compact_best_genome_id,
        "compact_best_DETPass": compact_best_detpass,
        "compact_best_tokens": compact_best_tokens,
        "compact_best_eligible": compact_eligible,
        "compact_best_reason": "within_detpass_margin" if compact_eligible and compact_best_genome_id else "no_eligible_compact_best",
        "token_minimal_unconstrained_genome_id": token_minimal_unconstrained_genome_id,
        "pareto_archive_size": len({str(row.get("genome_id", "")) for row in pareto_archive_rows}),
        "cloudless_mutation_used": args.mutation_mode in {"cloudless_decompiler", "hybrid"} or bool(args.enable_prompt_decompiler),
        "advisor_used": bool(args.llm_mutation_advisor),
        "advisor_proposals_generated": advisor_generated_count,
        "advisor_proposals_accepted_applied": advisor_applied_count,
        "advisor_proposals_accepted_not_scheduled": advisor_not_scheduled_count,
        "advisor_proposals_rejected": advisor_rejected_count,
        "advisor_children_scheduled": advisor_children_scheduled_count,
        "compression_ready_final": compression_ready_final,
        "compression_detpass_threshold": float(args.compression_detpass_threshold),
        "aggressive_compression_after_target": bool(args.aggressive_compression_after_target),
        "compression_token_reduction_target": float(args.compression_token_reduction_target),
        "advisor_compression_proposals_generated": advisor_compression_generated_count,
        "advisor_compression_children_scheduled": advisor_compression_children_scheduled_count,
        "cloudless_compression_fallback_scheduled": cloudless_compression_fallback_scheduled_count,
        "new_by_compression_fallback": compression_fallback_count,
        "new_by_micro_compression": micro_compression_count,
        "new_by_block_compression": block_compression_count,
        "new_by_multi_block_compression": multi_block_compression_count,
        "new_by_global_budget_compression": global_budget_compression_count,
        "prompt_token_breakdown_json": str(output_root / "prompt_token_breakdown.json"),
        "block_token_breakdown_json": str(output_root / "block_token_breakdown.json"),
        "category_balance_mode": args.category_balance_mode,
        "token_penalty_mode": args.token_penalty_mode,
        "mutation_family_counts": dict(Counter(str(row.get("mutation_family", "")) for row in mutation_proposal_rows if str(row.get("mutation_family", "")))),
        "compression_success_count": sum(1 for row in mutation_proposal_rows if row.get("mutation_family") == "compression" and _truthy(row.get("accepted"))),
        "compression_rejection_count": sum(1 for row in mutation_proposal_rows if row.get("mutation_family") == "compression" and not _truthy(row.get("accepted"))),
    }
    summary["summary_consistency_check"] = _summary_consistency_check(
        summary=summary,
        promotion_rows=promotion_rows,
        detpass_margin=validation_row_margin if "validation_row_margin" in locals() else one_row_margin(len(validation_rows)),
    )
    dump_json(output_root / "ga_summary.json", summary)
    if summary["best_genome"] is not None:
        best_metric = _metric_for_eval(final_best) if final_best else None
        if best_metric:
            summary["best_genome"].setdefault("_ga_metadata", {})
            summary["best_genome"]["_ga_metadata"].update(
                {
                    "prompt_hash": best_metric.prompt_hash,
                    "block_signature": best_metric.block_signature,
                    "rule_signature": best_metric.rule_signature,
                }
            )
        dump_json(output_root / "best_genome.json", summary["best_genome"])
        best_summary = active_block_summary(summary["best_genome"])
        dump_json(
            output_root / "best_prompt_metadata.json",
            {
                "genome_id": summary["best_genome"].get("id", ""),
                "core_blocks": best_summary["core"],
                "optional_blocks": best_summary["optional"],
                "params": summary["best_genome"].get("params", {}),
                "block_params": summary["best_genome"].get("block_params", {}),
                "prompt_hash": best_metric.prompt_hash if best_metric else "",
                "block_signature": best_metric.block_signature if best_metric else "",
                "rule_signature": best_metric.rule_signature if best_metric else "",
                "full_prompt_printed": False,
            },
        )
    else:
        dump_json(output_root / "best_genome.json", {"status": "no_best_genome"})
        dump_json(output_root / "best_prompt_metadata.json", {"status": "no_best_genome", "full_prompt_printed": False})
    _write_stage_status(output_root, str(getattr(args, "stage_name", "ga")), "PASS", {"output_root": str(output_root)})
    _print_stage(args, str(getattr(args, "stage_name", "ga")), "PASS")
    return summary


def main() -> int:
    parser = build_parser()
    args = _normalize_stage_args(parser.parse_args())
    summary = run_ga_search(args)
    print("[FINAL]")
    print("artifacts:")
    for name, path in _final_artifacts(summary):
        print(f"- {name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
