#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .candidate_generation import generate_candidates_for_rows, write_candidate_csv
    from .evaluation import evaluate_candidate_records, write_evaluation_outputs
except ImportError:
    from candidate_generation import generate_candidates_for_rows, write_candidate_csv  # type: ignore
    from evaluation import evaluate_candidate_records, write_evaluation_outputs  # type: ignore


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fallback_genome(genome_id: str = "base") -> dict[str, Any]:
    return {
        "id": genome_id,
        "blocks": ["01", "02", "03", "06"],
        "params": {"candidate_strategies": ["mock_gt_copy"]},
        "block_params": {},
        "seed": 0,
    }


def run_mock_search(
    *,
    rows: list[tuple[int, dict[str, Any]]],
    rendered_package: dict[str, Any],
    out_dir: str | Path,
    population: int = 2,
    gens: int = 1,
    candidate_k: int = 1,
    llm_mode: str = "mock",
    det_threshold: float = 70.0,
    search_mode: str = "monolith",
) -> dict[str, Any]:
    root = Path(out_dir)
    genomes_dir = root / "genomes"
    candidates_dir = root / "candidates"
    genomes_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)

    initial_population = [fallback_genome(f"genome_{idx:03d}") for idx in range(max(1, population))]
    _write_json(genomes_dir / "initial_population.json", initial_population)
    all_eval_rows: list[dict[str, Any]] = []
    progress_rows: list[dict[str, Any]] = []
    best_history: list[dict[str, Any]] = []

    total_gens = max(1, gens)
    for generation in range(total_gens):
        _write_json(genomes_dir / f"generation_{generation:03d}.json", initial_population)
        generation_records = []
        for genome in initial_population:
            records = generate_candidates_for_rows(
                rows=rows,
                rendered_package=rendered_package,
                out_dir=root,
                llm_mode=llm_mode,
                candidate_k=candidate_k,
                generation=generation,
                genome_id=str(genome["id"]),
                candidate_strategy="mock_gt_copy" if llm_mode == "mock" else "unsupported",
            )
            generation_records.extend(records)
        write_candidate_csv(candidates_dir / f"generation_{generation:03d}.csv", generation_records)
        eval_rows = evaluate_candidate_records(generation_records, det_threshold=det_threshold)
        all_eval_rows.extend(eval_rows)
        avg_det = sum(float(row.get("det_score") or 0) for row in eval_rows) / len(eval_rows) if eval_rows else 0.0
        pass_rate = sum(1 for row in eval_rows if row.get("det_pass")) / len(eval_rows) if eval_rows else 0.0
        progress = {
            "generation": generation,
            "candidate_rows": len(eval_rows),
            "avg_det_score": avg_det,
            "train_det_pass_rate": pass_rate,
            "best_genome_id": initial_population[0]["id"],
        }
        progress_rows.append(progress)
        best_history.append(progress)

    eval_summary = write_evaluation_outputs(root, all_eval_rows)
    best_genome = initial_population[0]
    _write_json(root / "best_genome.json", best_genome)
    (root / "ga_generation_progress.csv").write_text(
        "generation,candidate_rows,avg_det_score,train_det_pass_rate,best_genome_id\n"
        + "\n".join(
            f"{row['generation']},{row['candidate_rows']},{row['avg_det_score']},{row['train_det_pass_rate']},{row['best_genome_id']}"
            for row in progress_rows
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "ga_block_diffs.jsonl").write_text("", encoding="utf-8")
    summary = {
        "run_id": root.name,
        "model_id": rendered_package.get("model_id") or rendered_package.get("model_package_id"),
        "model_package_path": rendered_package.get("source_model_package") or rendered_package.get("model_package"),
        "model_key": "",
        "search_mode": search_mode,
        "ga_engine_mode": "mock_foundation",
        "official_metric": "strict_det",
        "ground_truth_column": "gt",
        "rows": len(rows),
        "best_DETPass": eval_summary.get("det_pass_rate", 0.0),
        "best_avg_DET": eval_summary.get("avg_det_score", 0.0),
        "best_avg_prompt_tokens": 0,
        "stop_reason": "completed_requested_generations",
        "best_history": best_history,
        "cloud_is_auxiliary": True,
    }
    _write_json(root / "ga_summary.json", summary)
    _write_json(root / "promotion_decisions.json", {"promoted": False, "reason": "smoke foundation run"})
    (root / "promotion_decisions.csv").write_text("promoted,reason\nfalse,smoke foundation run\n", encoding="utf-8")
    (root / "mutation_events.csv").write_text("generation,mutation_type,details\n", encoding="utf-8")
    (root / "mutation_events.jsonl").write_text("", encoding="utf-8")
    return summary
