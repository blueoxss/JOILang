from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from pathlib import Path


VERSION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = VERSION_ROOT.parents[1]
if str(VERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(VERSION_ROOT))

from scripts.advisor_feedback import (  # noqa: E402
    apply_advisor_proposal,
    build_advisor_feedback_batch,
    category_feedback,
    validate_advisor_proposal,
)
from scripts.ga_metrics import metrics_from_evaluation  # noqa: E402
from scripts.mutation_proposals import PROPOSAL_STATE_ACCEPTED_APPLIED  # noqa: E402


def _eval(genome_id: str = "g1", *, category: str = "3", det_score: float = 42.0):
    item = {
        "genome": {
            "id": genome_id,
            "blocks": ["01", "02", "03", "06"],
            "params": {"candidate_strategies": ["direct", "compact_json"]},
            "block_params": {"02": {"micro_rules": ["Use canonical names exactly."]}},
        },
        "fitness": det_score,
        "validation_avg_det_score": det_score,
        "validation_metrics": {
            "avg_det_score": det_score,
            "variance": 0.0,
            "rows": [
                {
                    "row_no": 101,
                    "category": category,
                    "command_eng": "Turn on the device.",
                    "gt": "(#Switch).switch_on()",
                    "output": "(#Device).bad_service()",
                    "det_score": det_score,
                    "det_gt_exact": False,
                    "failure_reasons": ["unknown_service"],
                }
            ],
            "generation_summary": {"rows": [{"generation_prompt_tokens_total": 1000, "generation_llm_latency_sec": 1.2}]},
        },
    }
    item["redesign_metrics"] = metrics_from_evaluation(item)
    return item


def test_advisor_batch_packet_schema():
    item = _eval()
    batch = build_advisor_feedback_batch(
        generation=1,
        model_key="qwen25_coder_7b",
        advisor_model_key="gpt41_mini",
        evaluated_population=[item],
        categories=[3],
        limit_per_category=1,
        sample_size=1,
        validation_size=1,
        generation_phase="ACCURACY_SEARCH",
        plateau_type="failure_family_plateau",
        next_action="trigger_advisor_if_enabled",
        overall={"best_DETPass": 0.0, "top_failure_types": ["unknown_service"]},
        cloudless_feedback_summary={"structured_feedback_count": 1},
        best_genome_metric=item["redesign_metrics"],
        include_candidate_code=True,
    )
    assert batch["advisor_batch_id"].startswith("advisor_batch_g001_")
    assert batch["category_diagnostics"]
    assert batch["group_diagnostics"]["temporal"]["row_count"] == 1
    assert batch["representative_failures"][0]["candidate_code"]
    assert batch["advisor_request"]["allowed_mutation_types"]


def test_category_feedback_mapping():
    assert category_feedback({"schema_violation": 2})["suggested_target_block_family"] == "Service_Mapping"
    assert category_feedback({"enum_type_mismatch": 2})["suggested_target_block_family"] == "Enum_Grounding"
    assert category_feedback({"temporal_error": 1, "dataflow": 2})["suggested_target_block_family"] == "Temporal_Rule"
    assert category_feedback({"owner_device_mismatch": 2})["suggested_target_block_family"] == "Owner_Device_Rule"
    assert category_feedback({"extraneous_action": 2})["suggested_target_block_family"] == "Minimality"


def test_advisor_response_validation():
    valid = {
        "target_block_id": "02",
        "target_block_family": "Service_Mapping",
        "mutation_type": "add_micro_rule",
        "proposed_micro_rule": "Prefer canonical service names from service_list.",
        "affected_failure_families": ["unknown_service"],
    }
    ok, reason = validate_advisor_proposal(valid, valid_blocks={"01", "02", "03"}, core_blocks={"01", "02"})
    assert ok, reason
    bad_unknown = {**valid, "target_block_id": "99"}
    ok, reason = validate_advisor_proposal(bad_unknown, valid_blocks={"01", "02", "03"}, core_blocks={"01", "02"})
    assert not ok and "unknown" in reason
    bad_remove = {**valid, "mutation_type": "remove_core_block"}
    ok, reason = validate_advisor_proposal(bad_remove, valid_blocks={"01", "02", "03"}, core_blocks={"01", "02"})
    assert not ok and "protected" in reason
    ok, reason = validate_advisor_proposal(
        valid,
        valid_blocks={"01", "02", "03"},
        core_blocks={"01", "02"},
        existing_rules={"prefer canonical service names from service_list."},
    )
    assert not ok and "duplicate" in reason


def test_advisor_proposal_creates_child_and_diff():
    parent = _eval()["genome"]
    proposal = {
        "proposal_id": "advisor_g001_01",
        "target_block_id": "02",
        "target_block_family": "Service_Mapping",
        "mutation_type": "add_micro_rule",
        "proposed_micro_rule": "When a service is unknown, prefer the closest canonical service_list function name.",
        "affected_failure_families": ["unknown_service"],
        "category_scope": [1, 2],
        "group_scope": ["basic"],
    }
    child, diffs, mp = apply_advisor_proposal(
        parent,
        proposal,
        generation=1,
        advisor_batch_id_value="advisor_batch_g001_test",
        rng=random.Random(7),
    )
    assert mp.parent_genome_id
    assert mp.child_genome_id == child["id"]
    assert child["_ga_metadata"]["mutation_family"] == "advisor_guided"
    assert any(diff["llm_advised"] is True for diff in diffs)
    assert all(diff["advisor_proposal_id"] == "advisor_g001_01" for diff in diffs)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_advisor_population_transition_and_summary(tmp_path: Path):
    out = tmp_path / "advisor_smoke"
    cmd = [
        sys.executable,
        "-u",
        str(VERSION_ROOT / "scripts" / "run_ga_search.py"),
        "--profile",
        "version0_15",
        "--model-key",
        "qwen25_coder_7b",
        "--population",
        "4",
        "--gens",
        "2",
        "--sample-size",
        "4",
        "--validation-size",
        "4",
        "--cheap-eval-limit",
        "1",
        "--candidate-k",
        "1",
        "--repair-attempts",
        "0",
        "--det-profile",
        "strict",
        "--feedback-guided-mutation",
        "--selection-mode",
        "redesign",
        "--fitness-mode",
        "phase_aware",
        "--mutation-mode",
        "cloudless_decompiler",
        "--enable-compression-mutation",
        "--enable-rendered-prompt-dedupe",
        "--stop-controller-mode",
        "active",
        "--enable-pareto-archive",
        "--category-balance-mode",
        "guard",
        "--llm-mutation-advisor",
        "--advisor-trigger-mode",
        "always",
        "--advisor-min-population-for-child",
        "4",
        "--progress",
        "quiet",
        "--llm-mode",
        "mock",
        "--timeout-sec",
        "60",
        "--retries",
        "0",
        "--category",
        "3",
        "--category",
        "4",
        "--limit-per-category",
        "1",
        "--full-run",
        "--force",
        "--output-root",
        str(out),
    ]
    subprocess.run(cmd, cwd=REPO_ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    transitions = _read_csv(out / "population_transitions.csv")
    assert any(int(row.get("new_by_advisor") or 0) > 0 for row in transitions)
    assert any(int(row.get("advisor_children_scheduled") or 0) > 0 for row in transitions)
    proposals = _read_jsonl(out / "mutation_proposals.jsonl")
    advisor_applied = [
        row for row in proposals
        if row.get("source") == "advisor" and row.get("proposal_state") == PROPOSAL_STATE_ACCEPTED_APPLIED
    ]
    assert advisor_applied
    assert advisor_applied[0]["parent_genome_id"]
    assert advisor_applied[0]["child_genome_id"]
    diffs = _read_jsonl(out / "ga_block_diffs.jsonl")
    assert any(row.get("llm_advised") is True for row in diffs)
    assert _read_jsonl(out / "advisor_feedback_batches.jsonl")
    summary = json.loads((out / "ga_summary.json").read_text(encoding="utf-8"))
    assert summary["advisor_used"] is True
    assert summary["advisor_proposals_accepted_applied"] > 0
    assert summary["advisor_children_scheduled"] > 0
    assert summary["summary_consistency_check"]["best_fields_complete"] is True
    assert summary["summary_consistency_check"]["promotion_consistent"] is True


def test_advisor_not_scheduled_reason(tmp_path: Path):
    out = tmp_path / "advisor_pop2"
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
        "--stop-controller-mode",
        "active",
        "--llm-mutation-advisor",
        "--advisor-trigger-mode",
        "always",
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
    proposals = _read_jsonl(out / "mutation_proposals.jsonl")
    advisor_rows = [row for row in proposals if row.get("source") == "advisor"]
    assert advisor_rows
    assert any(row.get("proposal_state") == "accepted_not_scheduled" for row in advisor_rows)
    assert all(not row.get("child_genome_id") for row in advisor_rows if row.get("proposal_state") == "accepted_not_scheduled")


def test_best_so_far_non_decreasing(tmp_path: Path):
    out = tmp_path / "advisor_non_decreasing"
    cmd = [
        sys.executable,
        "-u",
        str(VERSION_ROOT / "scripts" / "run_ga_search.py"),
        "--profile",
        "version0_15",
        "--model-key",
        "qwen25_coder_7b",
        "--population",
        "3",
        "--gens",
        "2",
        "--sample-size",
        "2",
        "--validation-size",
        "2",
        "--cheap-eval-limit",
        "1",
        "--selection-mode",
        "redesign",
        "--fitness-mode",
        "phase_aware",
        "--stop-controller-mode",
        "active",
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
    rows = _read_csv(out / "ga_generation_progress.csv")
    values = [float(row.get("best_so_far_DETPass") or 0.0) for row in rows]
    assert values == sorted(values)
