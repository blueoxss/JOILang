#!/usr/bin/env bash
# ==============================================================================
# run_eval_pipeline_check.sh
# ------------------------------------------------------------------------------
# Canonical strict DET evaluation pipeline check for utils.ga_search.
#
# This script validates the repository-wide evaluation path:
#
#   python -m utils.ga_search.cli eval
#
# It does not call legacy model-package-local benchmark runners.
# ==============================================================================

set -u
set -o pipefail

MODE="${1:-smoke2}"
ARG_BASE_DIR="${2:-}"
ARG_DEVICE="${3:-}"

case "$MODE" in
  smoke2) DEFAULT_SAMPLE_SIZE=2 ;;
  smoke20) DEFAULT_SAMPLE_SIZE=20 ;;
  full) DEFAULT_SAMPLE_SIZE="" ;;
  *)
    echo "[ERROR] Unknown mode: $MODE" >&2
    echo "Usage: $0 {smoke2|smoke20|full} [BASE_DIR] [DEVICE]" >&2
    exit 2
    ;;
esac

detect_base_dir() {
  local candidates=(
    "$ARG_BASE_DIR"
    "$PWD"
    "$HOME/Desktop/llm/JOILang-Server"
    "$HOME/llm/JOILang-Server"
    "/home/mgjeong/Desktop/llm/JOILang-Server"
  )
  local d
  for d in "${candidates[@]}"; do
    [ -z "$d" ] && continue
    if [ -f "$d/utils/ga_search/cli.py" ] && [ -f "$d/datasets/JOICommands-280.csv" ]; then
      echo "$d"
      return 0
    fi
  done
  return 1
}

BASE_DIR="$(detect_base_dir || true)"
if [ -z "$BASE_DIR" ]; then
  echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
  exit 1
fi
if [ -n "$ARG_BASE_DIR" ]; then
  ARG_CANON="$(cd "$ARG_BASE_DIR" 2>/dev/null && pwd -P || true)"
  BASE_CANON="$(cd "$BASE_DIR" 2>/dev/null && pwd -P || true)"
  if [ -z "$ARG_CANON" ] || [ "$ARG_CANON" != "$BASE_CANON" ]; then
    echo "[WARN] Requested base dir '$ARG_BASE_DIR' was not usable; falling back to '$BASE_DIR'." >&2
  fi
fi

cd "$BASE_DIR" || exit 1
source ~/.bashrc >/dev/null 2>&1 || true

PY="${PY:-$(command -v python)}"
MODEL="${MODEL:-gpt_mg.version0_13}"
MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
LLM_MODE="${LLM_MODE:-mock}"
DATASET_CSV="${DATASET_CSV:-datasets/JOICommands-280.csv}"
SERVICE_SCHEMA="${SERVICE_SCHEMA:-datasets/service_list_ver2.0.1.json}"
EVAL_SAMPLE_SIZE="${EVAL_SAMPLE_SIZE:-$DEFAULT_SAMPLE_SIZE}"
SCRIPT_TS="$(date +%Y%m%d_%H%M%S)"
CHECK_ROOT="$BASE_DIR/artifacts/eval_pipeline_checks_${SCRIPT_TS}_${MODE}"
LOG_DIR="$CHECK_ROOT/logs"
EVAL_DIR="$CHECK_ROOT/strict_det"
SUMMARY_TSV="$CHECK_ROOT/check_summary.tsv"
mkdir -p "$LOG_DIR" "$EVAL_DIR"
: > "$SUMMARY_TSV"

record() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  printf "%-42s : %-5s %s\n" "$name" "$status" "$detail"
  printf "%s\t%s\t%s\n" "$name" "$status" "$detail" >> "$SUMMARY_TSV"
}

print_cmd() {
  printf '[COMMAND]'
  local arg
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
}

has_failures() {
  awk -F'\t' '$2=="FAIL"{found=1} END{exit found ? 0 : 1}' "$SUMMARY_TSV"
}

echo "=============================================================================="
echo "Evaluation Pipeline Check"
echo "=============================================================================="
echo "MODE=$MODE"
echo "BASE_DIR=$BASE_DIR"
echo "MODEL=$MODEL"
echo "MODEL_KEY=$MODEL_KEY"
echo "LLM_MODE=$LLM_MODE"
echo "DATASET_CSV=$DATASET_CSV"
echo "SERVICE_SCHEMA=$SERVICE_SCHEMA"
echo "EVAL_SAMPLE_SIZE=${EVAL_SAMPLE_SIZE:-full}"
echo "EVAL_DIR=$EVAL_DIR"
echo "LOG_DIR=$LOG_DIR"
echo "=============================================================================="

[ -f "$DATASET_CSV" ] && record "dataset exists" "PASS" "$DATASET_CSV" || record "dataset exists" "FAIL" "$DATASET_CSV missing"
[ -f "$SERVICE_SCHEMA" ] && record "service schema exists" "PASS" "$SERVICE_SCHEMA" || record "service schema exists" "WARN" "$SERVICE_SCHEMA missing"

"$PY" - <<PY > "$LOG_DIR/dataset_policy_check.log" 2>&1
import csv
from pathlib import Path
p = Path("$DATASET_CSV")
with p.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    fields = reader.fieldnames or []
    rows = list(reader)
print("fields", fields)
print("rows", len(rows))
print("has_gt", "gt" in fields)
print("has_gt_raw", "gt_raw" in fields)
raise SystemExit(0 if "gt" in fields and rows else 1)
PY
[ "$?" -eq 0 ] && record "dataset gt policy" "PASS" "gt column present" || record "dataset gt policy" "FAIL" "$LOG_DIR/dataset_policy_check.log"

"$PY" -m compileall "$BASE_DIR/utils/ga_search" "$BASE_DIR/utils/det_evaluator.py" > "$LOG_DIR/compileall.log" 2>&1
[ "$?" -eq 0 ] && record "compileall eval path" "PASS" "$LOG_DIR/compileall.log" || record "compileall eval path" "FAIL" "$LOG_DIR/compileall.log"

"$PY" - <<'PY' > "$LOG_DIR/import_origin.log" 2>&1
import importlib.util
names = [
    "utils.ga_search.cli",
    "utils.ga_search.model_resolver",
    "utils.ga_search.render_adapter",
    "utils.ga_search.candidate_generation",
    "utils.ga_search.evaluation",
    "utils.ga_search.ga_engine",
    "utils.det_evaluator",
]
for name in names:
    spec = importlib.util.find_spec(name)
    print(name, "=>", spec.origin if spec else None)
    assert spec is not None
    legacy = "version0_15_update" + "20260413"
    assert legacy not in str(spec.origin)
PY
[ "$?" -eq 0 ] && record "canonical import origins" "PASS" "$LOG_DIR/import_origin.log" || record "canonical import origins" "FAIL" "$LOG_DIR/import_origin.log"

LEGACY_TOKEN='version0_15_update''20260413'
LEGACY_MODULE='gpt_mg\.version0_15_update''20260413'
LEGACY_RUNNER='run_ga_search''\.py'
rg -n "$LEGACY_TOKEN|$LEGACY_MODULE|$LEGACY_RUNNER" \
  utils/ga_search utils/det_evaluator.py run_ga_search_check.sh run_eval_pipeline_check.sh \
  --glob '!**/__pycache__/**' > "$LOG_DIR/stale_reference_grep.log" 2>&1
rg_rc=$?
[ "$rg_rc" -eq 1 ] && record "canonical stale reference grep" "PASS" "no stale references" || record "canonical stale reference grep" "FAIL" "$LOG_DIR/stale_reference_grep.log"

"$PY" -m utils.ga_search.cli render --model gpt_mg.version0_13 --user-input "Turn on the light." --dry-run > "$LOG_DIR/render_gpt_mg_v13.log" 2>&1
[ "$?" -eq 0 ] && record "render gpt_mg.version0_13" "PASS" "$LOG_DIR/render_gpt_mg_v13.log" || record "render gpt_mg.version0_13" "FAIL" "$LOG_DIR/render_gpt_mg_v13.log"

"$PY" - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("gpt_cap.stage_2.config_loader") else 1)
PY
if [ "$?" -eq 0 ]; then
  "$PY" -m utils.ga_search.cli render --model gpt_cap.stage_2 --user-input "Turn on the light." --dry-run > "$LOG_DIR/render_gpt_cap_stage2.log" 2>&1
  [ "$?" -eq 0 ] && record "render gpt_cap.stage_2" "PASS" "$LOG_DIR/render_gpt_cap_stage2.log" || record "render gpt_cap.stage_2" "WARN" "$LOG_DIR/render_gpt_cap_stage2.log"
else
  record "render gpt_cap.stage_2" "WARN" "package absent"
fi

ARGS=(
  -m utils.ga_search.cli eval
  --model "$MODEL"
  --dataset "$DATASET_CSV"
  --service-schema "$SERVICE_SCHEMA"
  --llm-mode "$LLM_MODE"
  --model-key "$MODEL_KEY"
  --det-profile strict
  --det-threshold 70
  --out-dir "$EVAL_DIR"
  --print-mode summary
)

if [ -n "${EVAL_SAMPLE_SIZE:-}" ]; then
  ARGS+=(--sample-size "$EVAL_SAMPLE_SIZE")
fi

print_cmd "$PY" "${ARGS[@]}"
"$PY" "${ARGS[@]}" > "$LOG_DIR/eval.log" 2>&1
rc=$?
[ "$rc" -eq 0 ] && record "strict eval command" "PASS" "rc=0" || record "strict eval command" "FAIL" "rc=$rc log=$LOG_DIR/eval.log"

for f in candidates/generation_000.csv eval/row_evaluation.csv eval/failure_reason_summary.csv eval/category_summary.csv eval/summary.json manifest.json; do
  [ -f "$EVAL_DIR/$f" ] && record "artifact $f" "PASS" "$EVAL_DIR/$f" || record "artifact $f" "FAIL" "missing"
done

"$PY" - "$EVAL_DIR" <<'PY' > "$LOG_DIR/eval_policy_check.log" 2>&1
import csv
import json
import sys
from pathlib import Path
root = Path(sys.argv[1])
summary = json.loads((root / "eval" / "summary.json").read_text(encoding="utf-8"))
with (root / "eval" / "row_evaluation.csv").open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
print("rows", len(rows))
print("summary", summary)
if not rows:
    print("STATUS|FAIL|no evaluation rows")
    raise SystemExit(1)
if summary.get("official_metric") != "strict_det" or summary.get("ground_truth_column") != "gt":
    print("STATUS|FAIL|official metric/gt policy mismatch")
    raise SystemExit(1)
if any("gt_raw" in row for row in rows):
    print("STATUS|FAIL|gt_raw leaked into official evaluation rows")
    raise SystemExit(1)
print("STATUS|PASS|strict DET uses official gt policy")
PY

status_line="$(grep 'STATUS|' "$LOG_DIR/eval_policy_check.log" | tail -1 || true)"
if [ -n "$status_line" ]; then
  record "eval policy health" "$(echo "$status_line" | cut -d'|' -f2)" "$(echo "$status_line" | cut -d'|' -f3-)"
else
  record "eval policy health" "FAIL" "$LOG_DIR/eval_policy_check.log"
fi

echo
echo "=============================================================================="
echo "FINAL SUMMARY"
echo "=============================================================================="
column -t -s $'\t' "$SUMMARY_TSV" 2>/dev/null || cat "$SUMMARY_TSV"
echo
echo "Artifacts:"
echo "- CHECK_ROOT=$CHECK_ROOT"
echo "- EVAL_DIR=$EVAL_DIR"
echo "- SUMMARY_TSV=$SUMMARY_TSV"
echo "- logs=$LOG_DIR"

if has_failures; then
  echo
  echo "[FINAL] FAIL"
  exit 1
fi

echo
echo "[FINAL] PASS"
exit 0
