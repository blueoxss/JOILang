#!/usr/bin/env bash
# ==============================================================================
# run_ga_search_check.sh
# ------------------------------------------------------------------------------
# Canonical GA search smoke/medium/full check for utils.ga_search.
#
# This script intentionally routes through:
#
#   python -m utils.ga_search.cli search
#
# It does not call legacy model-package-local GA runners.
# ==============================================================================

set -u
set -o pipefail

MODE="${1:-smoke}"
ARG_BASE_DIR="${2:-}"
ARG_DEVICE="${3:-}"

case "$MODE" in
  smoke|medium|full) ;;
  *)
    echo "[ERROR] Unknown mode: $MODE" >&2
    echo "Usage: $0 {smoke|medium|full} [BASE_DIR] [DEVICE]" >&2
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

cd "$BASE_DIR" || exit 1
source ~/.bashrc >/dev/null 2>&1 || true

PY="${PY:-$(command -v python)}"
MODEL="${MODEL:-gpt_mg.version0_13}"
MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
LLM_MODE="${LLM_MODE:-mock}"
DATASET="${DATASET:-datasets/JOICommands-280.csv}"
SERVICE_SCHEMA="${SERVICE_SCHEMA:-datasets/service_list_ver2.0.1.json}"
SCRIPT_TS="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="${RUN_ROOT:-$BASE_DIR/artifacts/ga_search_checks_${SCRIPT_TS}_${MODE}}"
LOG_DIR="$RUN_ROOT/_logs"
SUMMARY_TSV="$RUN_ROOT/check_summary.tsv"
mkdir -p "$LOG_DIR"
: > "$SUMMARY_TSV"

record() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  printf "%-42s : %-5s %s\n" "$name" "$status" "$detail"
  printf "%s\t%s\t%s\n" "$name" "$status" "$detail" >> "$SUMMARY_TSV"
}

has_failures() {
  awk -F'\t' '$2=="FAIL"{found=1} END{exit found ? 0 : 1}' "$SUMMARY_TSV"
}

case "$MODE" in
  smoke)
    POPULATION=2
    GENS=1
    LIMIT_PER_CATEGORY=1
    CATEGORIES=(5)
    ;;
  medium)
    POPULATION=6
    GENS=3
    LIMIT_PER_CATEGORY=2
    CATEGORIES=(1 2)
    ;;
  full)
    POPULATION=16
    GENS=10
    LIMIT_PER_CATEGORY=""
    CATEGORIES=(1 2 3 4 5 6 7 8)
    ;;
esac

OUT_DIR="$RUN_ROOT/search_${MODE}"
LOG_FILE="$LOG_DIR/search_${MODE}.log"

echo "=============================================================================="
echo "GA Search Check"
echo "=============================================================================="
echo "MODE=$MODE"
echo "BASE_DIR=$BASE_DIR"
echo "MODEL=$MODEL"
echo "MODEL_KEY=$MODEL_KEY"
echo "LLM_MODE=$LLM_MODE"
echo "DATASET=$DATASET"
echo "SERVICE_SCHEMA=$SERVICE_SCHEMA"
echo "OUT_DIR=$OUT_DIR"
echo "LOG_FILE=$LOG_FILE"
echo "=============================================================================="

"$PY" -m compileall "$BASE_DIR/utils/ga_search" > "$LOG_DIR/compileall.log" 2>&1
[ "$?" -eq 0 ] && record "compileall utils.ga_search" "PASS" "$LOG_DIR/compileall.log" || record "compileall utils.ga_search" "FAIL" "$LOG_DIR/compileall.log"

ARGS=(
  -m utils.ga_search.cli search
  --model "$MODEL"
  --dataset "$DATASET"
  --service-schema "$SERVICE_SCHEMA"
  --search-mode auto
  --llm-mode "$LLM_MODE"
  --model-key "$MODEL_KEY"
  --det-profile strict
  --population "$POPULATION"
  --gens "$GENS"
  --candidate-k 1
  --repair-attempts 0
  --out-dir "$OUT_DIR"
  --print-mode summary
)

if [ -n "${LIMIT_PER_CATEGORY:-}" ]; then
  ARGS+=(--limit-per-category "$LIMIT_PER_CATEGORY")
fi
for category in "${CATEGORIES[@]}"; do
  ARGS+=(--category "$category")
done

echo "[COMMAND] $PY ${ARGS[*]}"
"$PY" "${ARGS[@]}" > "$LOG_FILE" 2>&1
rc=$?
[ "$rc" -eq 0 ] && record "ga search command" "PASS" "rc=0" || record "ga search command" "FAIL" "rc=$rc log=$LOG_FILE"

for f in ga_summary.json best_genome.json ga_generation_progress.csv candidates/generation_000.csv eval/row_evaluation.csv eval/failure_reason_summary.csv eval/category_summary.csv ga_run_manifest.json; do
  [ -f "$OUT_DIR/$f" ] && record "artifact $f" "PASS" "$OUT_DIR/$f" || record "artifact $f" "FAIL" "missing"
done

"$PY" - "$OUT_DIR" <<'PY' > "$LOG_DIR/artifact_health.log" 2>&1
import csv
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
summary = json.loads((out / "ga_summary.json").read_text(encoding="utf-8"))
with (out / "candidates" / "generation_000.csv").open(encoding="utf-8-sig", newline="") as f:
    candidate_rows = list(csv.DictReader(f))
with (out / "eval" / "row_evaluation.csv").open(encoding="utf-8-sig", newline="") as f:
    eval_rows = list(csv.DictReader(f))
print("candidate_rows", len(candidate_rows))
print("eval_rows", len(eval_rows))
print("official_metric", summary.get("official_metric"))
print("ground_truth_column", summary.get("ground_truth_column"))
if not candidate_rows or not eval_rows:
    print("STATUS|FAIL|empty candidate/eval rows")
    raise SystemExit(1)
if summary.get("official_metric") != "strict_det" or summary.get("ground_truth_column") != "gt":
    print("STATUS|FAIL|official metric or gt policy mismatch")
    raise SystemExit(1)
print("STATUS|PASS|candidate/eval artifacts are readable")
PY

status_line="$(grep 'STATUS|' "$LOG_DIR/artifact_health.log" | tail -1 || true)"
if [ -n "$status_line" ]; then
  record "artifact health" "$(echo "$status_line" | cut -d'|' -f2)" "$(echo "$status_line" | cut -d'|' -f3-)"
else
  record "artifact health" "FAIL" "$LOG_DIR/artifact_health.log"
fi

echo
echo "=============================================================================="
echo "FINAL SUMMARY"
echo "=============================================================================="
column -t -s $'\t' "$SUMMARY_TSV" 2>/dev/null || cat "$SUMMARY_TSV"
echo
echo "Artifacts:"
echo "- RUN_ROOT=$RUN_ROOT"
echo "- OUT_DIR=$OUT_DIR"
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
