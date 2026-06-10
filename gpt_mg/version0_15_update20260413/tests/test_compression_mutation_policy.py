from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path


VERSION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = VERSION_ROOT.parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.advisor_feedback import build_advisor_feedback_batch, build_advisor_prompt_from_batch, validate_advisor_proposal  # noqa: E402
from scripts.ga_mutation import (  # noqa: E402
    COMPRESSION_MUTATION_TYPES,
    FAMILY_RATIOS,
    apply_mutation_proposal,
)
from scripts.ga_stop_controller import decide_next_action  # noqa: E402
from scripts.mutation_proposals import MutationProposal, proposal_from_advisor  # noqa: E402
from scripts.run_ga_search import (  # noqa: E402
    _advisor_mutation_summary_rows,
    _build_token_breakdowns,
    _extract_json_object,
    _make_compression_lane_proposal,
    _proposal_to_row,
    _safe_advisor_proposals,
    _staged_compression_quotas,
)


def _compression_genome() -> dict:
    return {
        "id": "g1",
        "blocks": ["01", "02", "03", "05", "06"],
        "params": {
            "max_tokens": 1024,
            "candidate_strategies": ["direct", "minimal", "canonical_names_first", "compact_json"],
        },
        "block_params": {
            "02": {
                "few_shot_count": 3,
                "micro_rules": [
                    "Return exactly one JSON object only with required keys: name, cron, period, code.",
                    "Use canonical names exactly.",
                    "Use canonical names exactly.",
                    "Keep code minimal.",
                ],
                "layout_notes": "verbose notes",
            },
            "06": {"micro_rules": ["Keep code minimal.", "Keep code minimal.", "Bind sensor values."]},
        },
    }


def _apply(operator: str):
    proposal = MutationProposal(
        proposal_id=f"p_{operator}",
        source="cloudless",
        mutation_family="compression",
        operator=operator,
        parent_genome_id="g1",
    )
    return apply_mutation_proposal(_compression_genome(), proposal, rng=random.Random(3))


def test_stop_controller_aggressive_compression_switch():
    rows = [
        {"generation": 1, "best_so_far_DETPass": 91, "validation_avg_det_score": 88, "avg_prompt_tokens": 2000},
        {"generation": 2, "best_so_far_DETPass": 91, "validation_avg_det_score": 88, "avg_prompt_tokens": 2000},
    ]
    decision = decide_next_action(
        rows,
        generation=2,
        max_generations=10,
        min_generations=2,
        plateau_window=2,
        target_detpass=95,
        pareto_archive_delta=1,
        unique_prompt_hash_count=4,
        population_size=4,
        advisor_enabled=True,
        advisor_trigger_mode="on_compression",
        disruptive_attempt_count=0,
        disruptive_max_attempts=2,
        compression_detpass_threshold=90,
        aggressive_compression_after_target=True,
    )
    assert decision.generation_phase == "COMPRESSION_SEARCH"
    assert decision.next_action == "switch_aggressive_compression"
    assert decision.plateau_type == "compression_ready_token_plateau"
    assert decision.advisor_triggered is True


def test_compression_search_ratio_is_dominant():
    assert FAMILY_RATIOS["COMPRESSION_SEARCH"]["compression"] > FAMILY_RATIOS["ACCURACY_SEARCH"]["compression"]
    assert FAMILY_RATIOS["COMPRESSION_SEARCH"]["compression"] >= 0.70


def test_compression_operators_make_diffs_and_preserve_core_schema_blocks():
    operators = [
        "drop_optional_blocks_for_budget",
        "reduce_few_shot_count_to_zero",
        "prune_micro_rules_to_top_k",
        "compress_candidate_strategies_to_minimal",
        "lower_output_max_tokens_aggressive",
        "compact_block_params",
    ]
    for operator in operators:
        child, diffs = _apply(operator)
        assert diffs, operator
        assert {"01", "02", "03"} <= set(child["blocks"])
        assert all(diff["mutation_family"] == "compression" for diff in diffs)


def test_advisor_compression_validation_allows_empty_rule_and_genome_target():
    proposal = {
        "target_block_id": "genome",
        "target_block_family": "Compression",
        "mutation_family": "compression",
        "mutation_type": "compress_candidate_strategies_to_minimal",
        "proposed_micro_rule": "",
        "affected_failure_families": ["token_overbudget"],
        "expected_token_delta": -1000,
    }
    ok, reason = validate_advisor_proposal(proposal, valid_blocks={"01", "02", "03", "05", "06"}, core_blocks={"01", "02"})
    assert ok, reason

    bad_retrieval = {**proposal, "reason": "Change retrieval top-k while compressing."}
    ok, reason = validate_advisor_proposal(bad_retrieval, valid_blocks={"01", "02", "03", "05", "06"}, core_blocks={"01", "02"})
    assert not ok and "retrieval" in reason

    bad_schema_drop = {**proposal, "target_block_id": "03", "target_block_family": "Output_Schema", "mutation_type": "drop_optional_block"}
    ok, reason = validate_advisor_proposal(bad_schema_drop, valid_blocks={"01", "02", "03", "05", "06"}, core_blocks={"01", "02"})
    assert not ok and "protected" in reason


def test_noop_candidate_strategy_compression_rejected():
    proposal = {
        "target_block_id": "genome",
        "target_block_family": "Compression",
        "mutation_family": "compression",
        "compression_level": "micro",
        "mutation_type": "compress_candidate_strategies_to_minimal",
        "affected_failure_families": ["token_overbudget"],
        "expected_token_delta": -100,
    }
    genome = _compression_genome()
    genome["params"]["candidate_strategies"] = ["minimal"]
    ok, reason = validate_advisor_proposal(
        proposal,
        valid_blocks={"01", "02", "03", "05", "06"},
        core_blocks={"01", "02"},
        current_genome=genome,
    )
    assert not ok
    assert reason == "no_op_candidate_strategies_already_minimal"


def _quota_args(**overrides):
    defaults = {
        "enable_compression_mutation": True,
        "micro_compression_child_quota": 1,
        "micro_compression_child_ratio": 0.05,
        "block_compression_child_quota": 1,
        "block_compression_child_ratio": 0.2,
        "multi_block_compression_child_quota": 1,
        "multi_block_compression_child_ratio": 0.2,
        "global_budget_compression_child_quota": 0,
        "enable_multi_block_compression": False,
        "enable_render_budget_compression": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_micro_compression_scheduled_before_threshold():
    quotas = _staged_compression_quotas(_quota_args(), compression_phase="ACCURACY_SEARCH", population_size=4)
    assert quotas["micro"] >= 1
    assert quotas["block"] == 0


def test_block_compression_enabled_after_threshold():
    genome = _compression_genome()
    prompt_breakdown, block_breakdown = _build_token_breakdowns(genome, generation=1, model_key="mock")
    quotas = _staged_compression_quotas(_quota_args(), compression_phase="COMPRESSION_READY", population_size=4)
    assert quotas["micro"] >= 1
    assert quotas["block"] >= 1
    assert prompt_breakdown["total_prompt_token_estimate"] > 0
    assert block_breakdown


def test_aggressive_compression_is_superset():
    ready = _staged_compression_quotas(_quota_args(), compression_phase="COMPRESSION_READY", population_size=5)
    aggressive = _staged_compression_quotas(
        _quota_args(enable_multi_block_compression=True),
        compression_phase="AGGRESSIVE_COMPRESSION",
        population_size=5,
    )
    assert aggressive["micro"] > 0
    assert aggressive["block"] >= ready["block"]
    assert aggressive["multi_block"] > 0


def test_advisor_prompt_contains_token_breakdowns():
    genome = _compression_genome()
    prompt_breakdown, block_breakdown = _build_token_breakdowns(genome, generation=1, model_key="mock")
    item = {
        "genome": genome,
        "validation_metrics": {"rows": [], "generation_summary": {"rows": []}},
        "redesign_metrics": None,
    }
    batch = build_advisor_feedback_batch(
        generation=1,
        model_key="mock",
        advisor_model_key="mock_advisor",
        evaluated_population=[item],
        categories=[1],
        limit_per_category=1,
        sample_size=1,
        validation_size=1,
        generation_phase="COMPRESSION_SEARCH",
        plateau_type="compression_ready_token_plateau",
        next_action="switch_aggressive_compression",
        overall={"best_DETPass": 100.0},
        cloudless_feedback_summary={},
        best_genome_metric=None,
        compression_ready=True,
        compression_phase="COMPRESSION_READY",
        prompt_token_breakdown=prompt_breakdown,
        block_token_breakdown=block_breakdown,
    )
    prompt = build_advisor_prompt_from_batch(batch)
    assert "prompt_token_breakdown" in prompt
    assert "block_token_breakdown" in prompt
    assert "block_compression_proposals" in prompt
    assert "do not return only genome-level candidate_strategies compression" in prompt
    assert "is_protected_block=true" in prompt
    assert "Advisor Case B" in prompt


def test_full_parsed_advisor_response_is_preserved():
    raw = """
    Advisor output:
    {
      "advisor_status": "accepted",
      "compression_policy": {"compression_ready": true},
      "prompt_token_breakdown_seen": true,
      "block_token_breakdown_seen": true,
      "proposals": [
        {
          "proposal_id": "g001_compress_01",
          "target_block_id": "genome",
          "target_block_family": "Compression",
          "mutation_family": "compression",
          "mutation_type": "compress_candidate_strategies_to_minimal",
          "expected_token_delta": -100
        }
      ]
    }
    """
    parsed = _extract_json_object(raw)
    assert parsed["advisor_status"] == "accepted"
    assert parsed["compression_policy"]["compression_ready"] is True
    assert parsed["proposals"][0]["proposal_id"] == "g001_compress_01"


def test_legacy_advisor_proposals_are_normalized_and_recorded():
    payload = {
        "advisor_status": "accepted",
        "proposals": [
            {
                "proposal_id": "legacy_1",
                "target_block_id": "genome",
                "target_block_family": "Compression",
                "mutation_family": "compression",
                "mutation_type": "lower_output_max_tokens_aggressive",
                "expected_token_delta": -256,
            }
        ],
    }
    safe, rejected = _safe_advisor_proposals(
        payload,
        generation=1,
        advisor_batch_id_value="batch",
        parent_genome=_compression_genome(),
        raw_response_path="/tmp/raw.txt",
        advisor_prompt_path="/tmp/prompt.txt",
    )
    assert not rejected
    assert safe[0]["operator"] == "lower_output_max_tokens_aggressive"
    assert safe[0]["mutation_type"] == "lower_output_max_tokens_aggressive"
    proposal = proposal_from_advisor(safe[0], generation=1, advisor_batch_id="batch")
    row = _proposal_to_row(proposal)
    assert row["schema_source"] == "proposals"
    assert row["raw_response_path"] == "/tmp/raw.txt"


def test_block_compression_proposals_are_normalized_and_recorded():
    payload = {
        "block_compression_proposals": [
            {
                "proposal_id": "block_1",
                "selected_block_id": "06",
                "selected_block_family": "DET_Helper",
                "exact_mutation_operator": "prune_micro_rules_to_top_k",
                "original_token_estimate": 400,
                "proposed_token_estimate_after": 200,
                "expected_token_delta": -200,
                "affected_failure_families": ["token_overbudget"],
            }
        ]
    }
    safe, rejected = _safe_advisor_proposals(
        payload,
        generation=1,
        advisor_batch_id_value="batch",
        parent_genome=_compression_genome(),
    )
    assert not rejected
    assert safe[0]["compression_level"] == "block"
    assert safe[0]["selected_block_id"] == "06"
    assert safe[0]["operator"] == "prune_micro_rules_to_top_k"


def test_protected_block_proposal_is_rejected_and_recorded():
    payload = {
        "block_compression_proposals": [
            {
                "proposal_id": "bad_02",
                "selected_block_id": "02",
                "selected_block_family": "Service_Mapping",
                "exact_mutation_operator": "reduce_few_shot_count_to_zero",
                "expected_token_delta": -100,
                "affected_failure_families": ["token_overbudget"],
            }
        ]
    }
    safe, rejected = _safe_advisor_proposals(
        payload,
        generation=1,
        advisor_batch_id_value="batch",
        parent_genome=_compression_genome(),
    )
    assert not safe
    assert rejected[0]["rejection_reason"] == "protected_block_target"


def test_invalid_schema_and_empty_schema_are_diagnostic_rows():
    bad_payload = {"block_compression_proposals": {"proposal_id": "not_a_list"}}
    safe, rejected = _safe_advisor_proposals(bad_payload, generation=1, advisor_batch_id_value="batch")
    assert not safe
    assert rejected[0]["rejection_reason"] == "invalid_json_schema"

    empty_safe, empty_rejected = _safe_advisor_proposals({}, generation=1, advisor_batch_id_value="batch")
    assert not empty_safe
    assert empty_rejected[0]["rejection_reason"] == "no_advisor_proposals_parsed"


def test_advisor_mutation_summary_is_not_header_only_for_rejected_proposals():
    payload = {
        "proposals": [
            {
                "proposal_id": "noop",
                "target_block_id": "genome",
                "target_block_family": "Compression",
                "mutation_family": "compression",
                "mutation_type": "compress_candidate_strategies_to_minimal",
                "expected_token_delta": -100,
            }
        ]
    }
    genome = _compression_genome()
    genome["params"]["candidate_strategies"] = ["minimal"]
    safe, rejected = _safe_advisor_proposals(payload, generation=1, parent_genome=genome)
    rows = [_proposal_to_row(proposal_from_advisor(item, generation=1)) for item in safe + rejected]
    summary_rows = _advisor_mutation_summary_rows(rows)
    assert summary_rows
    assert summary_rows[0]["proposal_id"] == "noop"
    assert summary_rows[0]["rejection_reason"] == "no_op_candidate_strategies_already_minimal"


def test_fallback_lane_prefers_block_compression_before_tiny_genome_compression():
    genome = _compression_genome()
    prompt_breakdown, block_breakdown = _build_token_breakdowns(genome, generation=1, model_key="mock")
    proposal = _make_compression_lane_proposal(
        level="block",
        generation=2,
        parent_genome=genome,
        block_token_breakdown=block_breakdown,
        prompt_token_breakdown=prompt_breakdown,
        rng=random.Random(7),
        source="compression_fallback",
    )
    assert proposal is not None
    assert proposal.source == "compression_fallback"
    assert proposal.compression_level == "block"
    assert proposal.operator in {"drop_optional_block", "reduce_few_shot_count_to_zero", "prune_micro_rules_to_top_k", "compact_block_params"}


def test_advisor_block_proposal_schema():
    proposal = {
        "proposal_id": "block_1",
        "mutation_family": "compression",
        "compression_level": "block",
        "selected_block_id": "06",
        "selected_block_family": "DET_Helper",
        "exact_mutation_operator": "prune_micro_rules_to_top_k",
        "original_token_estimate": 500,
        "proposed_token_estimate_after": 300,
        "expected_token_delta": -200,
        "preserved_content": ["temporal constraints"],
        "removable_content": ["duplicate hints"],
        "affected_failure_families": ["token_overbudget"],
    }
    ok, reason = validate_advisor_proposal(
        proposal,
        valid_blocks={"01", "02", "03", "05", "06"},
        core_blocks={"01", "02"},
        current_genome=_compression_genome(),
        min_compression_token_delta=32,
    )
    assert ok, reason


def test_advisor_compression_family_inferred_from_operator():
    raw = {
        "proposal_id": "advisor_g001_compress",
        "target_block_id": "genome",
        "target_block_family": "Compression",
        "mutation_type": "lower_output_max_tokens_aggressive",
        "affected_failure_families": ["token_overbudget"],
        "expected_token_delta": -512,
    }
    proposal = proposal_from_advisor(raw, generation=1, advisor_batch_id="batch")
    assert proposal.operator in COMPRESSION_MUTATION_TYPES
    assert proposal.mutation_family == "compression"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_run_ga_search_compression_ready_mock_smoke(tmp_path: Path):
    out = tmp_path / "compression_ready_smoke"
    cmd = [
        sys.executable,
        "-u",
        str(VERSION_ROOT / "scripts" / "run_ga_search.py"),
        "--profile",
        "version0_15",
        "--model-key",
        "qwen25_coder_7b",
        "--population",
        "2",
        "--gens",
        "1",
        "--sample-size",
        "2",
        "--validation-size",
        "2",
        "--cheap-eval-limit",
        "1",
        "--candidate-k",
        "1",
        "--repair-attempts",
        "0",
        "--selection-mode",
        "redesign",
        "--fitness-mode",
        "phase_aware",
        "--mutation-mode",
        "cloudless_decompiler",
        "--enable-compression-mutation",
        "--stop-controller-mode",
        "active",
        "--llm-mutation-advisor",
        "--advisor-trigger-mode",
        "always",
        "--advisor-force-child-quota",
        "--advisor-min-population-for-child",
        "2",
        "--compression-detpass-threshold",
        "0",
        "--aggressive-compression-after-target",
        "--compression-child-quota",
        "1",
        "--advisor-compression-child-quota",
        "1",
        "--compression-token-reduction-target",
        "0.15",
        "--allow-aggressive-compression",
        "--progress",
        "quiet",
        "--llm-mode",
        "mock",
        "--category",
        "1",
        "--limit-per-category",
        "1",
        "--full-run",
        "--force",
        "--output-root",
        str(out),
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    advisor_response = json.loads((out / "advisor_response_generation_001.json").read_text(encoding="utf-8"))
    assert advisor_response["parsed"]["advisor_status"]
    assert "compression_policy" in advisor_response
    assert advisor_response["parsed"].get("proposals") or advisor_response["parsed"].get("block_compression_proposals")
    advisor_rows = _read_jsonl(out / "advisor_mutation_proposals.jsonl")
    assert advisor_rows
    advisor_summary_rows = _read_csv(out / "advisor_mutation_summary.csv")
    assert advisor_summary_rows
    plan = json.loads((out / "advisor_block_compression_plan_generation_001.json").read_text(encoding="utf-8"))
    assert "accepted_block_proposals" in plan
    assert "rejected_compression_proposals" in plan
    assert "fallback_used" in plan
    transitions = _read_csv(out / "population_transitions.csv")
    assert any(str(row.get("compression_ready")).lower() == "true" for row in transitions)
    assert "new_by_compression_fallback" in transitions[0]
    assert any(
        int(row.get("new_by_compression") or 0) > 0
        or int(row.get("advisor_compression_children_scheduled") or 0) > 0
        for row in transitions
    )
    proposals = _read_jsonl(out / "mutation_proposals.jsonl")
    assert any(row.get("mutation_family") == "compression" for row in proposals)
    summary = json.loads((out / "ga_summary.json").read_text(encoding="utf-8"))
    assert summary["compression_success_count"] > 0 or summary["advisor_compression_children_scheduled"] > 0
