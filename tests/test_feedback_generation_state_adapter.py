import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from utils.feedback_generation_state import classify_generation_state, component_score_policy
from utils.merge_strict_det_with_cloud_judges import (
    assess_join_quality,
    build_advisor_row,
    cloud_score_status,
)
from utils.prompt_advisor.build_advisor_prompt import row_clusters
from utils.ga_search.advisor_evidence import build_cloud_evidence


def test_empty_generation_routes_to_generation_health_not_output_schema():
    row = {
        "row_no": "1",
        "gt_code": "(#Light).on()",
        "gt_cron": "",
        "gt_period": "0",
        "det_gt_similarity": "0",
        "det_gt_service_coverage": "",
    }
    state = classify_generation_state(row)
    assert state["class"] == "generation_empty_output"
    assert state["skip_cloud_judge"] is True
    assert state["advisor_target_family"] == "Generation_Health"
    assert state["allow_output_schema_mutation"] is False
    scores = component_score_policy(row, state=state)
    assert scores["gt_similarity"] == 0.0
    assert scores["gt_service_coverage"] is None


def test_parsed_output_fields_are_not_misclassified_as_empty_generation():
    row = {
        "row_no": "2",
        "gt_code": "(#Light).on()",
        "gt_period": "0",
        "output_code": "(#Light).on()",
        "output_cron": "",
        "output_period": "0",
    }
    assert classify_generation_state(row)["class"] == "valid_json_nonempty"


def test_invalid_json_raw_text_allows_output_schema_route():
    row = {
        "row_no": "3",
        "raw_candidate": "not json",
        "gt_code": "(#Light).on()",
    }
    state = classify_generation_state(row)
    assert state["class"] == "invalid_json.non_json_text"
    assert state["advisor_target_family"] == "Output_Schema"
    assert state["allow_output_schema_mutation"] is True


def test_cloud_error_score_is_null_not_zero():
    cloud_row = {
        "overall_lang": "0",
        "ls_judge_status": "judge_runtime_error",
        "ls_valid_score": "false",
        "ls_error_type": "RateLimitError",
        "ls_judge_reasoning": "error (rate limit)",
    }
    status = cloud_score_status(
        cloud_row,
        score_key="overall_lang",
        status_key="ls_judge_status",
        valid_key="ls_valid_score",
        error_key="ls_error_type",
        skip_key="ls_skip_reason",
        reasoning_key="ls_judge_reasoning",
    )
    assert status["valid_score"] is False
    assert status["score"] is None
    assert status["status"] == "judge_runtime_error"


def test_bad_join_forces_strict_only_priority_and_keeps_cloud_auxiliary_null():
    strict_row = {
        "row_no": "10",
        "command_eng": "turn on the light",
        "gt_code": "(#Light).on()",
        "gt_period": "0",
        "output_code": "",
        "output_period": "0",
        "det_score": "0",
        "det_pass": "false",
        "failure_reasons": json.dumps(["semantic"]),
    }
    join_quality = assess_join_quality(
        strict_rows=[strict_row],
        cloud_rows=[],
        strict_keys={"10"},
        cloud_keys=set(),
        joined_keys=set(),
        chosen_join_key="row_no",
        cloud_duplicates=0,
    )
    advisor_row = build_advisor_row(
        strict_row=strict_row,
        cloud_row=None,
        report_row={},
        model_key="gpt41_mini",
        join_quality=join_quality,
    )
    assert advisor_row["evidence_quality"]["effective_feedback_mode"] == "strict_only_fallback"
    assert advisor_row["lang_judge"]["overall_lang"] is None
    assert "strict_only_fallback" in advisor_row["advisor_priority"]["reason"]


def test_advisor_prompt_clusters_use_root_cause_summary():
    row = {
        "strict_det": {"failure_reasons": ["invalid_json"]},
        "root_cause_summary": {
            "root_cause": "generation_cuda_oom",
            "target_block_family": "Prompt_Budget",
            "output_schema_suppressed": True,
        },
        "suppressed_mutations": ["Output_Schema"],
    }
    clusters = row_clusters(row)
    assert "Prompt_Budget" in clusters
    assert "Output_Schema" not in clusters


def test_cloud_evidence_ignores_skipped_scores(tmp_path):
    csv_path = tmp_path / "cloud.csv"
    csv_path.write_text(
        "row_no,overall_lang,ls_valid_score,ls_judge_status,ls_judge_reasoning,overall_gpt,gpt_valid_score,gpt_judge_status,gpt_judge_reasoning\n"
        "1,0,false,skipped,skipped empty,0,false,skipped,skipped empty\n",
        encoding="utf-8-sig",
    )
    packet = build_cloud_evidence(cloud_judge_csv=str(csv_path), top_k=5)
    assert packet["high_priority_rows"] == []
    assert packet["global_summary"]["failure_count"] == 0
