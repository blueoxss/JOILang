from __future__ import annotations

import sys
from pathlib import Path


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.ga_metrics import (  # noqa: E402
    assign_pareto,
    best_tie_key,
    compression_acceptance_decision,
    compression_gain,
    metrics_from_evaluation,
    stable_genome_signature,
    token_penalty,
)
from scripts.ga_mutation import apply_mutation_proposal  # noqa: E402
from scripts.ga_selection import ArchiveState, metric_of, quota_elites, regression_gate, update_archives  # noqa: E402
from scripts.ga_stop_controller import decide_next_action  # noqa: E402
from scripts.mutation_proposals import MutationProposal, validate_proposal  # noqa: E402
from scripts.prompt_decompiler import compression_proposals_from_artifact, decompile_prompt  # noqa: E402


def _eval(genome_id: str, detpass_rows: list[float], tokens: int, category: str = "1"):
    rows = [
        {
            "row_no": idx + 1,
            "category": category,
            "det_score": score,
            "det_gt_exact": score >= 100,
            "failure_reasons": [] if score >= 70 else ["unknown_service"],
        }
        for idx, score in enumerate(detpass_rows)
    ]
    return {
        "genome": {
            "id": genome_id,
            "blocks": ["01", "02", "03", "06"],
            "params": {"candidate_strategies": ["direct", "compact_json"]},
            "block_params": {"02": {"micro_rules": ["Use canonical names exactly."]}},
        },
        "fitness": 0.0,
        "validation_avg_det_score": sum(detpass_rows) / len(detpass_rows),
        "validation_metrics": {
            "rows": rows,
            "avg_det_score": sum(detpass_rows) / len(detpass_rows),
            "variance": 0.0,
            "generation_summary": {"rows": [{"generation_prompt_tokens_total": tokens, "generation_llm_latency_sec": 1.0}]},
        },
    }


def _with_metric(item, **kwargs):
    item["redesign_metrics"] = metrics_from_evaluation(item, **kwargs)
    return item


def test_pareto_frontier_and_compact_tradeoff():
    a = _with_metric(_eval("a", [100, 100, 100], 2000))
    b = _with_metric(_eval("b", [100, 100, 70], 900))
    c = _with_metric(_eval("c", [70, 70, 70], 2500))
    metrics = assign_pareto([metric_of(a), metric_of(b), metric_of(c)])
    frontier = {m.genome_id for m in metrics if m.pareto_frontier_member}
    assert frontier == {"a", "b"}
    archives = update_archives(ArchiveState(), [a, b, c], accepted_best=a, generation=1, one_row_margin=33.3334, enable_group_specialists=False)
    assert archives.compact_best_within_epsilon["genome"]["id"] == "b"


def test_best_tiebreak_prefers_avgdet_then_tokens():
    high_avg = _with_metric(_eval("high_avg", [100, 95], 2000))
    low_tokens = _with_metric(_eval("low_tokens", [100, 90], 1000))
    assert min([high_avg, low_tokens], key=lambda item: best_tie_key(metric_of(item)))["genome"]["id"] == "high_avg"
    a = _with_metric(_eval("a", [100, 90], 2000))
    b = _with_metric(_eval("b", [100, 90], 1000))
    assert min([a, b], key=lambda item: best_tie_key(metric_of(item)))["genome"]["id"] == "b"


def test_token_penalty_and_compression_gain_margin():
    assert token_penalty(1200, token_budget=1000, accepted_tokens=None, mode="budget") == 0.2
    assert token_penalty(1200, token_budget=1000, accepted_tokens=1100, mode="hybrid") == 0.2
    assert compression_gain(900, 1200, detpass=90, parent_detpass=95, margin=10) > 0
    assert compression_gain(900, 1200, detpass=80, parent_detpass=95, margin=10) == 0.0


def test_compression_acceptance_and_rollback_reason():
    ok, reason, saving = compression_acceptance_decision(
        parent_detpass=90,
        child_detpass=85,
        parent_tokens=2000,
        child_tokens=1700,
        margin=10,
        min_token_reduction=0.05,
    )
    assert ok and reason == "" and saving == 0.15
    ok, reason, _saving = compression_acceptance_decision(
        parent_detpass=90,
        child_detpass=70,
        parent_tokens=2000,
        child_tokens=1000,
        margin=10,
        min_token_reduction=0.05,
    )
    assert not ok
    assert "DETPass" in reason


def test_archive_elites_preserve_accepted_and_global_best():
    accepted = _with_metric(_eval("accepted", [100, 70, 70], 1200))
    champion = _with_metric(_eval("champion", [100, 100, 100], 3000))
    compact = _with_metric(_eval("compact", [100, 100, 70], 800))
    archives = update_archives(ArchiveState(), [accepted, champion, compact], accepted_best=accepted, generation=1, one_row_margin=33.3334, enable_group_specialists=True)
    elites = quota_elites([accepted, champion, compact], archives, population_size=3, category_balance_mode="routing", one_row_margin=33.3334)
    ids = {item["genome"]["id"] for item in elites}
    assert {"accepted", "champion", "compact"} <= ids


def test_category_guard_regression_gate():
    accepted = _with_metric(_eval("accepted", [100, 100], 1000, category="3"))
    candidate = _with_metric(_eval("candidate", [40, 40], 900, category="3"))
    ok, reason = regression_gate(metric_of(candidate), metric_of(accepted), margin=50.0, category_balance_mode="guard")
    assert not ok
    assert "DETPass" in reason


def test_mutation_proposal_schema_shared_and_rejects_retrieval_mutation():
    proposal = MutationProposal(
        proposal_id="p1",
        source="cloudless",
        mutation_family="compression",
        operator="drop_optional_block",
        target_block_id="03",
    )
    ok, reason = validate_proposal(proposal, valid_blocks={"01", "02", "03"}, core_blocks={"01", "02"})
    assert ok, reason
    bad = MutationProposal(
        proposal_id="p2",
        source="advisor",
        mutation_family="advisor_guided",
        operator="change",
        replacement_text="Change retrieval top-k to 5",
    )
    ok, reason = validate_proposal(bad, valid_blocks={"01", "02", "03"}, core_blocks={"01", "02"})
    assert not ok
    assert "retrieval" in reason


def test_prompt_decompiler_protects_schema_and_proposes_duplicate_prune():
    prompt = """
Return exactly one JSON object only.
- Use canonical service names exactly.
- Remove unrelated actions.
- Remove unrelated actions.
"""
    artifact = decompile_prompt(prompt)
    assert any(unit.protected for unit in artifact.units if "json" in unit.text_normalized)
    proposals = compression_proposals_from_artifact(artifact, generation=1, parent_genome_id="g1")
    assert any(proposal.operator == "prune_stale_micro_rules" for proposal in proposals)


def test_apply_compression_mutation_preserves_core_blocks():
    genome = {"id": "g1", "blocks": ["01", "02", "03", "05", "06"], "params": {}, "block_params": {}}
    proposal = MutationProposal(
        proposal_id="p1",
        source="cloudless",
        mutation_family="compression",
        operator="drop_optional_block",
        parent_genome_id="g1",
    )
    child, _diffs = apply_mutation_proposal(genome, proposal, rng=__import__("random").Random(1))
    assert "01" in child["blocks"] and "02" in child["blocks"]
    assert len(child["blocks"]) < len(genome["blocks"])


def test_rendered_prompt_hash_dedupe_signature_is_stable():
    genome = {"id": "a", "blocks": ["01", "02"], "params": {"temperature": 0}, "block_params": {}}
    same = {"id": "b", "blocks": ["01", "02"], "params": {"temperature": 0}, "block_params": {}}
    assert stable_genome_signature(genome)[0] == stable_genome_signature(same)[0]


def test_stop_controller_actions():
    rows = [
        {"generation": 1, "best_so_far_DETPass": 100, "validation_avg_det_score": 90, "avg_prompt_tokens": 2000},
        {"generation": 2, "best_so_far_DETPass": 100, "validation_avg_det_score": 90, "avg_prompt_tokens": 2000},
        {"generation": 3, "best_so_far_DETPass": 100, "validation_avg_det_score": 90, "avg_prompt_tokens": 2000},
    ]
    decision = decide_next_action(
        rows,
        generation=3,
        max_generations=10,
        min_generations=3,
        plateau_window=3,
        target_detpass=95,
        pareto_archive_delta=0,
        unique_prompt_hash_count=3,
        population_size=4,
        advisor_enabled=False,
        advisor_trigger_mode="off",
        disruptive_attempt_count=0,
        disruptive_max_attempts=2,
    )
    assert decision.generation_phase == "COMPRESSION_SEARCH"
    assert decision.next_action == "switch_compression"
