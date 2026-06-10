from __future__ import annotations

import random
import sys
from pathlib import Path


VERSION_ROOT = Path(__file__).resolve().parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.advisor_feedback import build_advisor_feedback_batch, build_advisor_prompt_from_batch, validate_advisor_proposal  # noqa: E402
from scripts.ga_metrics import metrics_from_evaluation  # noqa: E402
from scripts.ga_mutation import apply_mutation_proposal  # noqa: E402
from scripts.mutation_proposals import MutationProposal  # noqa: E402
from scripts.prompt_profiler import profile_prompt_blocks_for_genome, prompt_token_breakdown_for_genome  # noqa: E402
from scripts.run_ga_search import _fallback_compression_proposal  # noqa: E402


def _genome() -> dict:
    return {
        "id": "g-compress",
        "blocks": ["01", "02", "03", "05", "06"],
        "params": {"candidate_strategies": ["minimal"], "max_tokens": 768, "few_shot_count": 3},
        "block_params": {
            "02": {"few_shot_count": 3, "micro_rules": ["A", "A", "B"]},
            "05": {"few_shot_count": 2},
            "06": {"micro_rules": ["r1", "r2", "r3", "r4", "r5"]},
        },
    }


def _eval_item(genome: dict) -> dict:
    item = {
        "genome": genome,
        "fitness": 100.0,
        "validation_avg_det_score": 100.0,
        "validation_metrics": {
            "avg_det_score": 100.0,
            "variance": 0.0,
            "rows": [{"row_no": 1, "category": "3", "det_score": 100.0, "det_gt_exact": True, "failure_reasons": []}],
            "generation_summary": {"rows": [{"generation_prompt_tokens_total": 1000, "generation_llm_latency_sec": 1.0}]},
        },
    }
    item["redesign_metrics"] = metrics_from_evaluation(item)
    return item


def test_block_profiler_marks_schema_protected_and_det_helper_compressible():
    rows = profile_prompt_blocks_for_genome(_genome())
    by_id = {row["block_id"]: row for row in rows}
    assert by_id["03"]["is_protected_block"] is True
    assert by_id["06"]["compression_allowed"] is True
    assert "prune_micro_rules_to_top_k" in by_id["06"]["safe_mutation_types"]


def test_advisor_rejects_noop_candidate_strategy_compression():
    genome = _genome()
    rows = profile_prompt_blocks_for_genome(genome)
    proposal = {
        "mutation_family": "compression",
        "compression_level": "micro",
        "mutation_type": "compress_candidate_strategies_to_minimal",
        "expected_token_delta": -12,
        "affected_failure_families": ["compression"],
    }
    ok, reason = validate_advisor_proposal(
        proposal,
        valid_blocks={"01", "02", "03", "05", "06"},
        core_blocks={"01", "02"},
        parent_genome=genome,
        block_token_breakdown=rows,
    )
    assert not ok
    assert "already equals" in reason


def test_advisor_accepts_concrete_block_compression_plan():
    genome = _genome()
    rows = profile_prompt_blocks_for_genome(genome)
    proposal = {
        "mutation_family": "compression",
        "compression_level": "block",
        "selected_block_id": "06",
        "selected_block_family": "DET_Helper",
        "exact_mutation_operator": "prune_micro_rules_to_top_k",
        "expected_token_delta": -80,
        "affected_failure_families": ["compression"],
    }
    ok, reason = validate_advisor_proposal(
        proposal,
        valid_blocks={"01", "02", "03", "05", "06"},
        core_blocks={"01", "02"},
        parent_genome=genome,
        block_token_breakdown=rows,
    )
    assert ok, reason


def test_block_few_shot_compression_applies_to_target_block():
    genome = _genome()
    proposal = MutationProposal(
        proposal_id="p-block",
        source="cloudless",
        mutation_family="compression",
        operator="reduce_few_shot_count_to_zero",
        target_block_id="05",
        target_block_family="Repair_Clause",
        compression_level="block",
        expected_token_delta=-120,
    )
    child, _diffs = apply_mutation_proposal(genome, proposal, rng=random.Random(3))
    assert child["block_params"]["05"]["few_shot_count"] == 0
    assert child["block_params"]["02"]["few_shot_count"] == 3


def test_compression_ready_fallback_uses_safe_block_operator():
    genome = _genome()
    rows = profile_prompt_blocks_for_genome(genome)
    proposal = _fallback_compression_proposal(
        generation=2,
        parent_genome=genome,
        block_token_breakdown=rows,
        rng=random.Random(4),
    )
    assert proposal is not None
    assert proposal.source == "compression_fallback"
    assert proposal.operator in {
        "drop_optional_blocks_for_budget",
        "reduce_few_shot_count_to_zero",
        "prune_micro_rules_to_top_k",
        "compact_block_params",
        "lower_output_max_tokens_aggressive",
        "compress_candidate_strategies_to_minimal",
    }


def test_advisor_prompt_case_b_includes_breakdowns():
    genome = _genome()
    item = _eval_item(genome)
    blocks = profile_prompt_blocks_for_genome(genome)
    prompt_breakdown = prompt_token_breakdown_for_genome(genome, block_token_breakdown=blocks, measured_prompt_tokens=1000)
    batch = build_advisor_feedback_batch(
        generation=1,
        model_key="qwen25_coder_7b",
        advisor_model_key="gpt41_mini",
        evaluated_population=[item],
        categories=[3],
        limit_per_category=1,
        sample_size=1,
        validation_size=1,
        generation_phase="COMPRESSION_SEARCH",
        plateau_type="accuracy_target_reached",
        next_action="switch_compression",
        overall={"best_DETPass": 100.0, "top_failure_types": []},
        cloudless_feedback_summary={"structured_feedback_count": 0},
        best_genome_metric=item["redesign_metrics"],
        compression_policy={"state": "COMPRESSION_READY", "compression_ready": True},
        block_token_breakdown=blocks,
        prompt_token_breakdown=prompt_breakdown,
    )
    text = build_advisor_prompt_from_batch(batch)
    assert "Advisor Case B" in text
    assert "block_token_breakdown" in text
    assert "block_compression_proposals" in text
