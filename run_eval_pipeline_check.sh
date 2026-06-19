#!/usr/bin/env bash
# ==============================================================================
# run_eval_pipeline_check.sh
# ------------------------------------------------------------------------------
# Purpose:
#   Evaluation Pipeline을 GA search 전에 smoke부터 검증한다.
#
# Flow:
#   1) local model preflight
#   2) strict DET benchmark
#   3) local DET failure report export
#   4) cloud semantic judge
#   5) strict/cloud merge adapter
#   6) advisor_rich_feedback.json schema / generation-state / evidence-quality check
#
# Usage:
#   chmod +x run_eval_pipeline_check.sh
#
#   # 2-row smoke, auto-detect repository path
#   ./run_eval_pipeline_check.sh smoke2
#
#   # 2-row smoke, explicit local path
#   ./run_eval_pipeline_check.sh smoke2 /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
#   # 20-row medium smoke
#   ./run_eval_pipeline_check.sh smoke20 /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
#   # 280-row full evaluation pipeline
#   ./run_eval_pipeline_check.sh full /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
# Optional env overrides:
#   MODEL_KEY=qwen25_coder_14b
#   PROMPT_VERSION=version0_13
#   DATASET_CSV=datasets/JOICommands-280.csv
#   EVAL_LIMIT=2
#   RUN_CLOUD=1
#   JOI_V15_PYTHON=/path/to/python
#   JOI_V15_WORKER_PYTHON=/path/to/python
#   JOI_V15_LOCAL_DTYPE=bf16
#   JOI_V15_LOCAL_LOAD_IN_4BIT=false
#   JOI_V15_LOCAL_FILES_ONLY=true
#
# PASS/FAIL 기준:
#   - preflight: local model status=ready, cuda_available=True
#   - strict DET: row_comparison.csv 생성, row 수 >= EVAL_LIMIT 또는 제한된 row 존재
#   - local report: local_det_failure_report.json 생성
#   - cloud judge: result_gpt_mg_<version>.csv 생성, row_no/status 관련 컬럼 가능하면 확인
#   - merge: advisor_rich_feedback.json 생성
#   - schema: generation_state/generation_health/evidence_quality/root cause 관련 필드 확인
#
# Note:
#   gpt_mg/version0_15_update20260413는 reference/legacy runner로 사용하되,
#   이 스크립트는 해당 폴더의 코드를 수정하지 않는다.
# ==============================================================================

set -u
set -o pipefail

MODE="${1:-smoke2}"
ARG_BASE_DIR="${2:-}"
ARG_DEVICE="${3:-}"

SCRIPT_TS="$(date +%Y%m%d_%H%M%S)"

case "$MODE" in
  smoke2)
    DEFAULT_LIMIT=2
    ;;
  smoke20)
    DEFAULT_LIMIT=20
    ;;
  full)
    DEFAULT_LIMIT=280
    ;;
  *)
    echo "[ERROR] Unknown mode: $MODE" >&2
    echo "Usage: $0 {smoke2|smoke20|full} [BASE_DIR] [DEVICE]" >&2
    exit 2
    ;;
esac

MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
PROMPT_VERSION="${PROMPT_VERSION:-version0_13}"
EVAL_LIMIT="${EVAL_LIMIT:-$DEFAULT_LIMIT}"
RUN_CLOUD="${RUN_CLOUD:-1}"

# ------------------------------------------------------------------------------
# Repository auto-detection
# ------------------------------------------------------------------------------
detect_base_dir() {
  local candidates=(
    "$ARG_BASE_DIR"
    "/home/mgjeong/Desktop/llm/JOILang-Server"
    "/root/llm/JOILang-Server"
    "$HOME/Desktop/llm/JOILang-Server"
    "$HOME/llm/JOILang-Server"
    "$PWD"
  )

  local d
  for d in "${candidates[@]}"; do
    [ -z "$d" ] && continue
    if [ -f "$d/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py" ] && \
       [ -f "$d/utils/export_local_det_failure_report.py" ] && \
       [ -f "$d/utils/merge_strict_det_with_cloud_judges.py" ]; then
      echo "$d"
      return 0
    fi
  done

  return 1
}

BASE_DIR="$(detect_base_dir || true)"
if [ -z "$BASE_DIR" ]; then
  echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
  echo "Example: $0 smoke2 /home/mgjeong/Desktop/llm/JOILang-Server cuda:0" >&2
  exit 1
fi

cd "$BASE_DIR" || {
  echo "[ERROR] Cannot cd to BASE_DIR=$BASE_DIR" >&2
  exit 1
}

source ~/.bashrc >/dev/null 2>&1 || true

PY="${JOI_V15_PYTHON:-$(command -v python)}"
WORKER_PY="${JOI_V15_WORKER_PYTHON:-$PY}"

STRICT_SCRIPT="$BASE_DIR/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py"
V13_ASSETS="$BASE_DIR/gpt_mg/version0_13"
DATASET_CSV="${DATASET_CSV:-datasets/JOICommands-280.csv}"
DATASET_ABS="$BASE_DIR/$DATASET_CSV"

LOCAL_MODELS_BASE="${JOI_V15_LOCAL_MODEL_BASE_DIR:-$(realpath "$BASE_DIR/../local_models" 2>/dev/null || echo "$BASE_DIR/../local_models")}"
LOCAL_MODEL_DIR="${JOI_V15_LOCAL_MODEL_NAME:-$LOCAL_MODELS_BASE/$MODEL_KEY}"

export JOI_V15_PYTHON="$PY"
export JOI_V15_WORKER_PYTHON="$WORKER_PY"
export JOI_V15_LOCAL_MODEL_BASE_DIR="$LOCAL_MODELS_BASE"
export JOI_V15_LOCAL_MODEL_NAME="$LOCAL_MODEL_DIR"
export JOI_V15_LOCAL_FILES_ONLY="${JOI_V15_LOCAL_FILES_ONLY:-true}"
export JOI_V15_LOCAL_DEVICE="${ARG_DEVICE:-${JOI_V15_LOCAL_DEVICE:-cuda:0}}"
export JOI_V15_LOCAL_DTYPE="${JOI_V15_LOCAL_DTYPE:-bf16}"
export JOI_V15_LOCAL_LOAD_IN_4BIT="${JOI_V15_LOCAL_LOAD_IN_4BIT:-false}"
export JOI_V15_LOCAL_TRUST_REMOTE_CODE="${JOI_V15_LOCAL_TRUST_REMOTE_CODE:-true}"

CHECK_ROOT="$BASE_DIR/artifacts/eval_pipeline_checks_${SCRIPT_TS}_${MODE}"
LOG_DIR="$CHECK_ROOT/logs"
STRICT_DIR="$CHECK_ROOT/strict_det"
CLOUD_OUT_DIR="$CHECK_ROOT/cloud_judge"
MERGE_OUT_DIR="$CHECK_ROOT/merged_feedback"
CLOUD_CSV="$CLOUD_OUT_DIR/result_gpt_mg_${PROMPT_VERSION}.csv"

mkdir -p "$LOG_DIR" "$STRICT_DIR" "$CLOUD_OUT_DIR" "$MERGE_OUT_DIR"

SUMMARY_TSV="$CHECK_ROOT/check_summary.tsv"
: > "$SUMMARY_TSV"

LLM_EXTRA_JSON="$(mktemp)"
trap 'rm -f "$LLM_EXTRA_JSON"' EXIT

cat > "$LLM_EXTRA_JSON" <<JSON
{
  "local_model_name": "$LOCAL_MODEL_DIR",
  "local_files_only": true,
  "local_device": "$JOI_V15_LOCAL_DEVICE",
  "local_dtype": "$JOI_V15_LOCAL_DTYPE",
  "local_load_in_4bit": $JOI_V15_LOCAL_LOAD_IN_4BIT,
  "local_trust_remote_code": true
}
JSON

record() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  printf "%-46s : %-5s %s\n" "$name" "$status" "$detail"
  printf "%s\t%s\t%s\n" "$name" "$status" "$detail" >> "$SUMMARY_TSV"
}

has_failures() {
  awk -F'\t' '$2=="FAIL"{found=1} END{exit found ? 0 : 1}' "$SUMMARY_TSV"
}

run_step() {
  local name="$1"
  local logfile="$2"
  shift 2

  echo
  echo "=============================================================================="
  echo "[STEP] $name"
  echo "=============================================================================="
  echo "[LOG] $logfile"
  echo "[CMD] $*"
  echo

  "$@" > "$logfile" 2>&1
  local rc=$?

  if [ "$rc" -eq 0 ]; then
    record "$name command" "PASS" "rc=0"
  else
    record "$name command" "FAIL" "rc=$rc log=$logfile"
  fi
  return "$rc"
}

print_context() {
  echo "=============================================================================="
  echo "Evaluation Pipeline Check"
  echo "=============================================================================="
  echo "MODE=$MODE"
  echo "BASE_DIR=$BASE_DIR"
  echo "MODEL_KEY=$MODEL_KEY"
  echo "PROMPT_VERSION=$PROMPT_VERSION"
  echo "EVAL_LIMIT=$EVAL_LIMIT"
  echo "RUN_CLOUD=$RUN_CLOUD"
  echo "PY=$PY"
  echo "WORKER_PY=$WORKER_PY"
  echo "STRICT_SCRIPT=$STRICT_SCRIPT"
  echo "V13_ASSETS=$V13_ASSETS"
  echo "DATASET_ABS=$DATASET_ABS"
  echo "LOCAL_MODELS_BASE=$LOCAL_MODELS_BASE"
  echo "LOCAL_MODEL_DIR=$LOCAL_MODEL_DIR"
  echo "JOI_V15_LOCAL_DEVICE=$JOI_V15_LOCAL_DEVICE"
  echo "JOI_V15_LOCAL_DTYPE=$JOI_V15_LOCAL_DTYPE"
  echo "JOI_V15_LOCAL_LOAD_IN_4BIT=$JOI_V15_LOCAL_LOAD_IN_4BIT"
  echo "CHECK_ROOT=$CHECK_ROOT"
  echo "STRICT_DIR=$STRICT_DIR"
  echo "CLOUD_OUT_DIR=$CLOUD_OUT_DIR"
  echo "MERGE_OUT_DIR=$MERGE_OUT_DIR"
  echo "LLM_EXTRA_JSON=$LLM_EXTRA_JSON"
  echo "=============================================================================="
}

print_context

# ------------------------------------------------------------------------------
# Basic file/path checks
# ------------------------------------------------------------------------------
[ -f "$STRICT_SCRIPT" ] && record "strict runner exists" "PASS" "$STRICT_SCRIPT" || record "strict runner exists" "FAIL" "$STRICT_SCRIPT missing"
[ -d "$V13_ASSETS" ] && record "prompt assets exist" "PASS" "$V13_ASSETS" || record "prompt assets exist" "FAIL" "$V13_ASSETS missing"
[ -f "$DATASET_ABS" ] && record "dataset exists" "PASS" "$DATASET_ABS" || record "dataset exists" "FAIL" "$DATASET_ABS missing"
[ -d "$LOCAL_MODEL_DIR" ] && record "local model dir exists" "PASS" "$LOCAL_MODEL_DIR" || record "local model dir exists" "FAIL" "$LOCAL_MODEL_DIR missing"

"$PY" - <<PY > "$LOG_DIR/dataset_check.log" 2>&1
import pandas as pd
from pathlib import Path
p = Path("$DATASET_ABS")
df = pd.read_csv(p, encoding="utf-8-sig")
print("dataset_path", p)
print("dataset_rows", len(df))
print("eval_limit", int("$EVAL_LIMIT"))
raise SystemExit(0 if len(df) >= int("$EVAL_LIMIT") else 1)
PY
if [ "$?" -eq 0 ]; then
  record "dataset row count" "PASS" "rows >= EVAL_LIMIT"
else
  record "dataset row count" "FAIL" "see $LOG_DIR/dataset_check.log"
fi

# ------------------------------------------------------------------------------
# 0) Preflight local model availability
# ------------------------------------------------------------------------------
run_step "preflight local model" "$LOG_DIR/preflight.log" \
  "$PY" "$STRICT_SCRIPT" \
    --suite paper_local5 \
    --model-key "$MODEL_KEY" \
    --prompt-render-mode legacy_v13_monolith \
    --prompt-assets-dir "$V13_ASSETS" \
    --llm-extra-json "$LLM_EXTRA_JSON" \
    --preflight-only \
    --print-worker-info \
    --strict-availability

grep -q "status=ready" "$LOG_DIR/preflight.log" \
  && record "preflight status ready" "PASS" "status=ready" \
  || record "preflight status ready" "FAIL" "status=ready not found"

grep -q "cuda_available=True" "$LOG_DIR/preflight.log" \
  && record "preflight cuda available" "PASS" "cuda_available=True" \
  || record "preflight cuda available" "WARN" "cuda_available=True not found"

# ------------------------------------------------------------------------------
# 1) Strict DET benchmark
# ------------------------------------------------------------------------------
run_step "strict DET benchmark" "$LOG_DIR/strict_det.log" \
  "$PY" "$STRICT_SCRIPT" \
    --suite paper_local5 \
    --model-key "$MODEL_KEY" \
    --candidate-k 1 \
    --repair-attempts 0 \
    --det-profile strict \
    --prompt-render-mode legacy_v13_monolith \
    --prompt-assets-dir "$V13_ASSETS" \
    --llm-extra-json "$LLM_EXTRA_JSON" \
    --limit "$EVAL_LIMIT" \
    --output-dir "$STRICT_DIR" \
    --print-mode paths \
    --strict-availability

for f in row_comparison.csv failure_reason_summary.csv; do
  [ -f "$STRICT_DIR/$f" ] \
    && record "strict artifact $f" "PASS" "$STRICT_DIR/$f" \
    || record "strict artifact $f" "FAIL" "$STRICT_DIR/$f missing"
done

"$PY" - "$STRICT_DIR/row_comparison.csv" "$EVAL_LIMIT" <<'PY' > "$LOG_DIR/strict_row_count.log" 2>&1
import sys
from pathlib import Path
import pandas as pd
p = Path(sys.argv[1])
limit = int(sys.argv[2])
if not p.exists():
    print("missing", p)
    raise SystemExit(1)
df = pd.read_csv(p)
print("rows", len(df))
print("columns", list(df.columns)[:20])
raise SystemExit(0 if len(df) > 0 else 1)
PY
[ "$?" -eq 0 ] && record "strict row comparison readable" "PASS" "see $LOG_DIR/strict_row_count.log" || record "strict row comparison readable" "FAIL" "see $LOG_DIR/strict_row_count.log"

# ------------------------------------------------------------------------------
# 2) Export local strict DET failure report
# ------------------------------------------------------------------------------
run_step "export local DET failure report" "$LOG_DIR/export_local_det_failure_report.log" \
  "$PY" "$BASE_DIR/utils/export_local_det_failure_report.py" \
    --results-dir "$STRICT_DIR" \
    --model-key "$MODEL_KEY"

for f in local_det_failure_report.json local_det_failure_report.md local_det_failure_report.csv; do
  [ -f "$STRICT_DIR/$f" ] \
    && record "local report $f" "PASS" "$STRICT_DIR/$f" \
    || record "local report $f" "WARN" "$STRICT_DIR/$f missing"
done

# ------------------------------------------------------------------------------
# 3) Cloud semantic judges
# ------------------------------------------------------------------------------
CLOUD_API_KEY="${OPENAI_API_KEY_PROJ_BENCH:-${JOI_EVAL_OPENAI_API_KEY:-${JOI_V15_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}}}"
if [ "$RUN_CLOUD" = "1" ]; then
  if [ -z "$CLOUD_API_KEY" ]; then
    record "cloud API key" "FAIL" "OPENAI_API_KEY/JOI_EVAL_OPENAI_API_KEY/JOI_V15_OPENAI_API_KEY not set"
  else
    export OPENAI_API_KEY="$CLOUD_API_KEY"
    export OPENAI_API_KEY_PROJ_BENCH="$CLOUD_API_KEY"
    export JOI_EVAL_OPENAI_API_KEY="$CLOUD_API_KEY"
    export LANGSMITH_TRACING="${LANGSMITH_TRACING:-false}"
    export LANGCHAIN_TRACING_V2="${LANGCHAIN_TRACING_V2:-false}"
    record "cloud API key" "PASS" "configured from environment"

    run_step "cloud semantic judges" "$LOG_DIR/cloud_judge.log" \
      env EVAL_LIMIT="$EVAL_LIMIT" PYTHONPATH="$BASE_DIR${PYTHONPATH:+:$PYTHONPATH}" \
      "$PY" "$BASE_DIR/utils/evaluation_cloud/main_evaluator.py" \
        lang gpt joi "$PROMPT_VERSION" \
        --out-dir "$CLOUD_OUT_DIR"
  fi
else
  record "cloud semantic judges" "SKIP" "RUN_CLOUD=0"
fi

if [ -f "$CLOUD_CSV" ]; then
  record "cloud CSV exists" "PASS" "$CLOUD_CSV"
  "$PY" - "$CLOUD_CSV" <<'PY' > "$LOG_DIR/cloud_csv_schema.log" 2>&1
import sys
from pathlib import Path
import pandas as pd
p = Path(sys.argv[1])
df = pd.read_csv(p)
cols = set(df.columns)
print("rows", len(df))
print("columns", sorted(cols))
required_any = {"row_no", "index", "command_eng"}
judge_cols = {"ls_semantic_intent", "ls_conditions", "ls_time_period", "ls_device_service", "overall_gpt", "gpt_judge_reasoning"}
print("has_join_candidate", bool(cols & required_any))
print("judge_cols_present", sorted(cols & judge_cols))
raise SystemExit(0 if len(df) > 0 and bool(cols & required_any) else 1)
PY
  [ "$?" -eq 0 ] && record "cloud CSV schema" "PASS" "see $LOG_DIR/cloud_csv_schema.log" || record "cloud CSV schema" "WARN" "see $LOG_DIR/cloud_csv_schema.log"
else
  record "cloud CSV exists" "FAIL" "$CLOUD_CSV missing"
fi

# ------------------------------------------------------------------------------
# 4) Merge strict DET + cloud judge results
# ------------------------------------------------------------------------------
if [ -f "$CLOUD_CSV" ]; then
  run_step "merge strict/cloud feedback" "$LOG_DIR/merge.log" \
    "$PY" "$BASE_DIR/utils/merge_strict_det_with_cloud_judges.py" \
      --strict-results-dir "$STRICT_DIR" \
      --cloud-judge-csv "$CLOUD_CSV" \
      --model-key "$MODEL_KEY" \
      --out-dir "$MERGE_OUT_DIR"
else
  record "merge strict/cloud feedback" "FAIL" "cloud CSV missing; cannot merge"
fi

for f in advisor_rich_feedback.json hybrid_strict_cloud_report.csv hybrid_strict_cloud_report.md; do
  [ -f "$MERGE_OUT_DIR/$f" ] \
    && record "merge artifact $f" "PASS" "$MERGE_OUT_DIR/$f" \
    || record "merge artifact $f" "FAIL" "$MERGE_OUT_DIR/$f missing"
done

# ------------------------------------------------------------------------------
# 5) Deep schema/policy checks for revised feedback design
# ------------------------------------------------------------------------------
"$PY" - "$MERGE_OUT_DIR/advisor_rich_feedback.json" <<'PY' > "$LOG_DIR/feedback_policy_check.log" 2>&1
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
if not p.exists():
    print("missing", p)
    raise SystemExit(2)

data = json.loads(p.read_text(encoding="utf-8"))

def iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_dicts(v)

dicts = list(iter_dicts(data))

has_generation_state = any("generation_state" in d for d in dicts)
has_generation_health = any("generation_health" in d for d in dicts)
has_evidence_quality = any("evidence_quality" in d for d in dicts)
has_root_cause = any(k in data for k in ["root_cause_summary", "top_root_causes", "generation_failure_summary"])
has_suppressed = any(k in data for k in ["suppressed_mutations", "top_mutation_blocks_suppressed"]) or any("suppressed" in d for d in dicts)

print("has_generation_state", has_generation_state)
print("has_generation_health", has_generation_health)
print("has_evidence_quality", has_evidence_quality)
print("has_root_cause_summary", has_root_cause)
print("has_suppressed_mutations", has_suppressed)

# Check that empty/generation failure rows do not claim all semantic components are perfect.
bad_empty_component_rows = []
for d in dicts:
    st = d.get("generation_state")
    if not isinstance(st, dict):
        continue
    cls = str(st.get("class") or st.get("state") or st.get("root_cause") or "")
    if "empty" not in cls and "oom" not in cls and "timeout" not in cls and "generation" not in cls:
        continue
    comp = d.get("component_scores")
    if not isinstance(comp, dict):
        continue
    suspect_keys = ["gt_service_coverage", "gt_receiver_coverage", "dataflow_score", "numeric_grounding", "enum_grounding"]
    all_perfect = all(comp.get(k) == 1.0 for k in suspect_keys if k in comp)
    if all_perfect and any(k in comp for k in suspect_keys):
        bad_empty_component_rows.append(d.get("row_no") or d.get("index") or "unknown")

print("bad_empty_component_rows", bad_empty_component_rows[:10])
required = [has_generation_state, has_generation_health, has_evidence_quality]
if not all(required):
    raise SystemExit(1)
if bad_empty_component_rows:
    raise SystemExit(3)
PY

policy_rc=$?
if [ "$policy_rc" -eq 0 ]; then
  record "feedback policy schema" "PASS" "generation_state/generation_health/evidence_quality present"
elif [ "$policy_rc" -eq 3 ]; then
  record "feedback policy schema" "FAIL" "empty/generation failure rows still have misleading perfect component scores"
else
  record "feedback policy schema" "FAIL" "missing revised schema keys; see $LOG_DIR/feedback_policy_check.log"
fi

# ------------------------------------------------------------------------------
# Final report
# ------------------------------------------------------------------------------
echo
echo "=============================================================================="
echo "FINAL SUMMARY"
echo "=============================================================================="
column -t -s $'\t' "$SUMMARY_TSV" 2>/dev/null || cat "$SUMMARY_TSV"
echo
echo "Artifacts:"
echo "- CHECK_ROOT=$CHECK_ROOT"
echo "- STRICT_DIR=$STRICT_DIR"
echo "- CLOUD_OUT_DIR=$CLOUD_OUT_DIR"
echo "- MERGE_OUT_DIR=$MERGE_OUT_DIR"
echo "- SUMMARY_TSV=$SUMMARY_TSV"
echo "- logs=$LOG_DIR"

if has_failures; then
  echo
  echo "[FINAL] FAIL"
  exit 1
else
  echo
  echo "[FINAL] PASS"
  exit 0
fi
