#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import csv
from pathlib import Path
from typing import Any

try:
    from .candidate_generation import generate_candidates_for_rows, write_candidate_csv
    from .evaluation import evaluate_candidate_records, write_evaluation_outputs
    from .prompt_patch_apply import rendered_prompt_with_genome
    from .rerank import aggregate_genome_scores
except ImportError:
    from candidate_generation import generate_candidates_for_rows, write_candidate_csv  # type: ignore
    from evaluation import evaluate_candidate_records, write_evaluation_outputs  # type: ignore
    from prompt_patch_apply import rendered_prompt_with_genome  # type: ignore
    from rerank import aggregate_genome_scores  # type: ignore


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


def _copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _csv_cell(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _write_rows_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: _csv_cell(row.get(col, "")) for col in columns})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _render_for_genome(rendered_package: dict[str, Any], genome: dict[str, Any]) -> dict[str, Any]:
    patched = _copy_json(rendered_package)
    prompt = rendered_prompt_with_genome(rendered_package, genome)
    patched["prompt_text"] = prompt
    patched["system_prompt"] = prompt if not patched.get("user_prompt") else patched.get("system_prompt", "")
    patched["genome"] = genome
    messages = patched.get("messages")
    if isinstance(messages, list) and messages:
        new_messages = _copy_json(messages)
        for message in new_messages:
            if isinstance(message, dict) and message.get("role") == "system":
                message["content"] = prompt if not patched.get("user_prompt") else str(message.get("content") or "") + "\n\n" + prompt.split("[GA Prompt Patch Overlay]", 1)[-1]
                break
        else:
            new_messages.insert(0, {"role": "system", "content": prompt})
        patched["messages"] = new_messages
    return patched


def _initial_population(population: int, initial_genomes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if initial_genomes:
        out = []
        for index, genome in enumerate(initial_genomes[: max(1, population)]):
            item = _copy_json(genome)
            item["id"] = str(item.get("id") or f"genome_{index:03d}")
            out.append(item)
        while len(out) < max(1, population):
            out.append(fallback_genome(f"genome_{len(out):03d}"))
        return out
    return [fallback_genome(f"genome_{idx:03d}") for idx in range(max(1, population))]


MUTATION_RULES = [
    "Prefer canonical service names exactly as given by the service schema.",
    "Before final JSON, verify every receiver tag mentioned by the user is still present.",
    "Derive cron and period before writing code; do not invent repeated loops for one-shot commands.",
    "Use unquoted numeric literals for numeric service arguments.",
    "Return one JSON object only with name, cron, period, and code.",
]


def _mutate_genome(parent: dict[str, Any], rng: random.Random, generation: int, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    child = _copy_json(parent)
    child["id"] = f"{parent.get('id', 'genome')}_g{generation:03d}_m{index:03d}"
    child.setdefault("params", {})
    child.setdefault("block_params", {})
    mutation_type = rng.choice(["micro_rule", "toggle_optional", "candidate_strategy", "max_tokens"])
    details: dict[str, Any] = {}
    if mutation_type == "micro_rule":
        block_id = rng.choice(["02", "03", "06"])
        rules = child.setdefault("block_params", {}).setdefault(block_id, {}).setdefault("micro_rules", [])
        rule = rng.choice(MUTATION_RULES)
        if rule not in rules:
            rules.append(rule)
        details = {"block_id": block_id, "rule": rule}
    elif mutation_type == "toggle_optional":
        block_id = rng.choice(["03", "05", "06"])
        blocks = [str(block).zfill(2) for block in child.get("blocks", [])]
        if block_id in blocks and block_id not in {"01", "02"}:
            blocks.remove(block_id)
        elif block_id not in blocks:
            blocks.append(block_id)
        child["blocks"] = [block for block in ["01", "02", "03", "05", "06"] if block in set(blocks) or block in {"01", "02"}]
        details = {"block_id": block_id, "active_blocks": child["blocks"]}
    elif mutation_type == "candidate_strategy":
        strategies = child.setdefault("params", {}).setdefault("candidate_strategies", ["direct"])
        for strategy in ["direct", "compact_json", "canonical_names_first", "temporal_first"]:
            if strategy not in strategies:
                strategies.append(strategy)
                details = {"added_strategy": strategy}
                break
    else:
        current = int(child.setdefault("params", {}).get("max_tokens", 512) or 512)
        child["params"]["max_tokens"] = min(2048, current + 128)
        details = {"max_tokens": child["params"]["max_tokens"]}
    return child, {"generation": generation, "parent_id": parent.get("id", ""), "child_id": child["id"], "mutation_type": mutation_type, "details": details}


def _candidate_strategy(genome: dict[str, Any]) -> str:
    strategies = (genome.get("params") or {}).get("candidate_strategies")
    if isinstance(strategies, list) and strategies:
        return str(strategies[0])
    if isinstance(strategies, str) and strategies.strip():
        return strategies.strip()
    return "direct"


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
    service_schema: str | Path | None = None,
    service_context_mode: str = "schema_fallback",
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
                service_schema=service_schema,
                service_context_mode=service_context_mode,
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
        "llm_mode": llm_mode,
        "official_metric": "strict_det",
        "ground_truth_column": "gt",
        "rows": len(rows),
        "best_DETPass": eval_summary.get("det_pass_rate", 0.0),
        "best_avg_DET": eval_summary.get("avg_det_score", 0.0),
        "best_avg_prompt_tokens": 0,
        "generation_error_rate": eval_summary.get("generation_error_rate", 0.0),
        "stop_reason": "completed_requested_generations",
        "best_history": best_history,
        "cloud_is_auxiliary": True,
        "known_limitations": ["mock mode copies official gt as a deterministic pipeline fixture; do not use it for model quality claims"],
    }
    _write_json(root / "ga_summary.json", summary)
    _write_json(root / "promotion_decisions.json", {"promoted": False, "reason": "smoke foundation run"})
    (root / "promotion_decisions.csv").write_text("promoted,reason\nfalse,smoke foundation run\n", encoding="utf-8")
    (root / "mutation_events.csv").write_text("generation,mutation_type,details\n", encoding="utf-8")
    (root / "mutation_events.jsonl").write_text("", encoding="utf-8")
    return summary


def run_search(
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
    engine_mode: str = "auto",
    model_key: str = "",
    service_schema: str | Path | None = None,
    service_context_mode: str = "schema_fallback",
    timeout_sec: int = 1800,
    retries: int = 0,
    llm_endpoint: str = "",
    llm_extra: dict[str, Any] | None = None,
    repair_attempts: int = 0,
    initial_genomes: list[dict[str, Any]] | None = None,
    seed: int = 0,
    feedback_guided_mutation: bool = False,
    compression_mutation: bool = False,
) -> dict[str, Any]:
    requested_engine_mode = str(engine_mode or "auto").lower()
    if requested_engine_mode == "mock" or (requested_engine_mode == "auto" and llm_mode == "mock"):
        return run_mock_search(
            rows=rows,
            rendered_package=rendered_package,
            out_dir=out_dir,
            population=population,
            gens=gens,
            candidate_k=candidate_k,
            llm_mode=llm_mode,
            det_threshold=det_threshold,
            search_mode=search_mode,
            service_schema=service_schema,
            service_context_mode=service_context_mode,
        )

    root = Path(out_dir)
    genomes_dir = root / "genomes"
    candidates_dir = root / "candidates"
    genomes_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    current_population = _initial_population(population, initial_genomes=initial_genomes)
    _write_json(genomes_dir / "initial_population.json", current_population)

    all_eval_rows: list[dict[str, Any]] = []
    progress_rows: list[dict[str, Any]] = []
    best_history: list[dict[str, Any]] = []
    mutation_events: list[dict[str, Any]] = []
    promotion_rows: list[dict[str, Any]] = []
    best_genome = current_population[0]
    best_score = -1.0
    known_limitations = [
        "real engine skeleton evaluates genomes with strict DET and records selection/mutation artifacts",
        "advanced crossover, pareto archive, and compression mutation policies are hooks, not full legacy parity",
    ]
    if feedback_guided_mutation:
        known_limitations.append("feedback_guided_mutation flag recorded; advisor-generated genomes must be passed through prompt patches/advisor artifacts")
    if compression_mutation:
        known_limitations.append("compression mutation hook recorded; no prompt decompiler compression policy is executed yet")

    for generation in range(max(1, gens)):
        _write_json(genomes_dir / f"generation_{generation:03d}.json", current_population)
        generation_records: list[dict[str, Any]] = []
        for genome in current_population:
            rendered_for_genome = _render_for_genome(rendered_package, genome)
            records = generate_candidates_for_rows(
                rows=rows,
                rendered_package=rendered_for_genome,
                out_dir=root,
                llm_mode=llm_mode,
                model_key=model_key,
                candidate_k=candidate_k,
                generation=generation,
                genome_id=str(genome.get("id") or "genome"),
                candidate_strategy=_candidate_strategy(genome),
                service_schema=service_schema,
                service_context_mode=service_context_mode,
                timeout_sec=timeout_sec,
                retries=retries,
                llm_endpoint=llm_endpoint,
                llm_extra=llm_extra,
                repair_attempts=repair_attempts,
            )
            generation_records.extend(records)
        write_candidate_csv(candidates_dir / f"generation_{generation:03d}.csv", generation_records)
        eval_rows = evaluate_candidate_records(generation_records, det_threshold=det_threshold)
        all_eval_rows.extend(eval_rows)
        genome_scores = aggregate_genome_scores(eval_rows)
        generation_best = genome_scores[0] if genome_scores else {"genome_id": "", "avg_det_score": 0.0, "det_pass_rate": 0.0, "fitness": 0.0}
        if float(generation_best.get("fitness") or 0.0) > best_score:
            best_score = float(generation_best.get("fitness") or 0.0)
            best_id = str(generation_best.get("genome_id") or "")
            best_genome = next((genome for genome in current_population if str(genome.get("id")) == best_id), current_population[0])
        progress = {
            "generation": generation,
            "candidate_rows": len(eval_rows),
            "avg_det_score": sum(float(row.get("det_score") or 0) for row in eval_rows) / len(eval_rows) if eval_rows else 0.0,
            "train_det_pass_rate": sum(1 for row in eval_rows if row.get("det_pass")) / len(eval_rows) if eval_rows else 0.0,
            "best_genome_id": generation_best.get("genome_id", ""),
            "best_avg_det_score": generation_best.get("avg_det_score", 0.0),
            "best_fitness": generation_best.get("fitness", 0.0),
        }
        progress_rows.append(progress)
        best_history.append(progress)
        promotion_rows.append(
            {
                "generation": generation,
                "promoted_genome_id": generation_best.get("genome_id", ""),
                "reason": "highest_strict_det_fitness",
                "avg_det_score": generation_best.get("avg_det_score", 0.0),
            }
        )
        if generation < max(1, gens) - 1:
            ranked_ids = [str(item["genome_id"]) for item in genome_scores] or [str(genome.get("id")) for genome in current_population]
            ranked_genomes = [next((genome for genome in current_population if str(genome.get("id")) == genome_id), current_population[0]) for genome_id in ranked_ids]
            next_population = [_copy_json(ranked_genomes[0])]
            while len(next_population) < max(1, population):
                parent = rng.choice(ranked_genomes[: max(1, min(3, len(ranked_genomes)))])
                child, event = _mutate_genome(parent, rng, generation + 1, len(next_population))
                mutation_events.append(event)
                next_population.append(child)
            current_population = next_population

    eval_summary = write_evaluation_outputs(root, all_eval_rows)
    _write_json(root / "best_genome.json", best_genome)
    _write_json(root / "best_genomes.json", best_history)
    _write_rows_csv(
        root / "ga_generation_progress.csv",
        progress_rows,
        ["generation", "candidate_rows", "avg_det_score", "train_det_pass_rate", "best_genome_id", "best_avg_det_score", "best_fitness"],
    )
    _write_rows_csv(root / "promotion_decisions.csv", promotion_rows, ["generation", "promoted_genome_id", "reason", "avg_det_score"])
    _write_json(root / "promotion_decisions.json", {"decisions": promotion_rows, "final_best_genome_id": best_genome.get("id")})
    _write_rows_csv(root / "mutation_events.csv", mutation_events, ["generation", "parent_id", "child_id", "mutation_type", "details"])
    _write_jsonl(root / "mutation_events.jsonl", mutation_events)
    _write_jsonl(root / "ga_block_diffs.jsonl", [])
    generation_error_rate = eval_summary.get("generation_error_rate", 0.0)
    summary = {
        "run_id": root.name,
        "model_id": rendered_package.get("model_id") or rendered_package.get("model_package_id"),
        "model_package_path": rendered_package.get("source_model_package") or rendered_package.get("model_package"),
        "model_key": model_key,
        "search_mode": search_mode,
        "ga_engine_mode": "real_generation_skeleton",
        "requested_engine_mode": requested_engine_mode,
        "llm_mode": llm_mode,
        "official_metric": "strict_det",
        "ground_truth_column": "gt",
        "rows": len(rows),
        "best_DETPass": eval_summary.get("det_pass_rate", 0.0),
        "best_avg_DET": eval_summary.get("avg_det_score", 0.0),
        "best_avg_prompt_tokens": sum(float(row.get("generation_prompt_tokens_total") or 0) for row in all_eval_rows) / len(all_eval_rows) if all_eval_rows else 0.0,
        "generation_error_rate": generation_error_rate,
        "stop_reason": "completed_requested_generations",
        "best_history": best_history,
        "cloud_is_auxiliary": True,
        "known_limitations": known_limitations,
    }
    _write_json(root / "ga_summary.json", summary)
    return summary
