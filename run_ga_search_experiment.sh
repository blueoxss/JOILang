#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# JOILang GA Search Experiment Runner
# - Uses legacy GA core:
#   gpt_mg/version0_15_update20260413/scripts/run_ga_search.py
# - Does NOT modify version0_15_update20260413.
# - Runs:
#   0) parser/env check
#   1) cloudless small GA
#   2) mock-advisor small GA
#   3) optional real cloud-advisor small GA
# ============================================================

# Usage:
#   ./run_ga_search_experiment.sh
#   ./run_ga_search_experiment.sh /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
# Optional env:
#   MODEL_KEY=qwen25_coder_14b
#   ADVISOR_MODEL_KEY=gpt41_mini
#   GA_CATEGORIES="1 2"
#   GA_LIMIT_PER_CATEGORY=1
#   GA_POPULATION=4
#   GA_GENS=2
#   GA_SAMPLE_SIZE=2
#   GA_VALIDATION_SIZE=2
#   RUN_REAL_CLOUD_ADVISOR=0|1

ARG_BASE_DIR="${1:-}"
ARG_DEVICE="${2:-}"

if [ -n "$ARG_BASE_DIR" ]; then
  BASE_DIR="$ARG_BASE_DIR"
else
  CANDIDATES=(
    "/home/mgjeong/Desktop/llm/JOILang-Server"
    "/root/llm/JOILang-Server"
    "$HOME/Desktop/llm/JOILang-Server"
    "$HOME/llm/JOILang-Server"
    "$PWD"
  )
  BASE_DIR=""
  for d in "${CANDIDATES[@]}"; do
    if [ -f "$d/gpt_mg/version0_15_update20260413/scripts/run_ga_search.py" ]; then
      BASE_DIR="$d"
      break
    fi
  done
  if [ -z "$BASE_DIR" ]; then
    echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
    echo "Run with explicit path:" >&2
    echo "  $0 /home/mgjeong/Desktop/llm/JOILang-Server cuda:0" >&2
    exit 1
  fi
fi

cd "$BASE_DIR"
source ~/.bashrc || true

PYTHON_BIN="${PYTHON_BIN:-$(which python)}"
SCRIPT="$BASE_DIR/gpt_mg/version0_15_update20260413/scripts/run_ga_search.py"

MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
ADVISOR_MODEL_KEY="${ADVISOR_MODEL_KEY:-gpt41_mini}"

GA_CATEGORIES="${GA_CATEGORIES:-1 2}"
GA_LIMIT_PER_CATEGORY="${GA_LIMIT_PER_CATEGORY:-1}"
GA_POPULATION="${GA_POPULATION:-4}"
GA_GENS="${GA_GENS:-2}"
GA_SAMPLE_SIZE="${GA_SAMPLE_SIZE:-2}"
GA_VALIDATION_SIZE="${GA_VALIDATION_SIZE:-2}"
GA_CHEAP_EVAL_LIMIT="${GA_CHEAP_EVAL_LIMIT:-1}"
GA_TIMEOUT_SEC="${GA_TIMEOUT_SEC:-2400}"

RUN_REAL_CLOUD_ADVISOR="${RUN_REAL_CLOUD_ADVISOR:-0}"

LOCAL_MODELS_BASE_RAW="${LOCAL_MODELS_BASE:-$BASE_DIR/../local_models}"
LOCAL_MODELS_BASE="$(realpath -m "$LOCAL_MODELS_BASE_RAW")"
LOCAL_MODEL_DIR="$LOCAL_MODELS_BASE/$MODEL_KEY"

export JOI_V15_PYTHON="${JOI_V15_PYTHON:-$PYTHON_BIN}"
export JOI_V15_WORKER_PYTHON="${JOI_V15_WORKER_PYTHON:-$PYTHON_BIN}"
export JOI_V15_LOCAL_MODEL_BASE_DIR="$LOCAL_MODELS_BASE"
export JOI_V15_LOCAL_MODEL_NAME="$LOCAL_MODEL_DIR"
export JOI_V15_LOCAL_FILES_ONLY="${JOI_V15_LOCAL_FILES_ONLY:-true}"
export JOI_V15_LOCAL_DEVICE="${ARG_DEVICE:-${JOI_V15_LOCAL_DEVICE:-cuda:0}}"
export JOI_V15_LOCAL_DTYPE="${JOI_V15_LOCAL_DTYPE:-bf16}"
export JOI_V15_LOCAL_LOAD_IN_4BIT="${JOI_V15_LOCAL_LOAD_IN_4BIT:-false}"
export JOI_V15_LOCAL_TRUST_REMOTE_CODE="${JOI_V15_LOCAL_TRUST_REMOTE_CODE:-true}"

case "${JOI_V15_LOCAL_LOAD_IN_4BIT,,}" in
  1|true|yes|on) JOI_V15_LOCAL_LOAD_IN_4BIT_JSON=true ;;
  *) JOI_V15_LOCAL_LOAD_IN_4BIT_JSON=false ;;
esac

case "${JOI_V15_LOCAL_FILES_ONLY,,}" in
  1|true|yes|on) JOI_V15_LOCAL_FILES_ONLY_JSON=true ;;
  *) JOI_V15_LOCAL_FILES_ONLY_JSON=false ;;
esac

case "${JOI_V15_LOCAL_TRUST_REMOTE_CODE,,}" in
  1|true|yes|on) JOI_V15_LOCAL_TRUST_REMOTE_CODE_JSON=true ;;
  *) JOI_V15_LOCAL_TRUST_REMOTE_CODE_JSON=false ;;
esac

LLM_EXTRA_JSON="$(mktemp)"
trap 'rm -f "$LLM_EXTRA_JSON"' EXIT

cat > "$LLM_EXTRA_JSON" <<JSON
{
  "local_model_name": "$LOCAL_MODEL_DIR",
  "local_files_only": $JOI_V15_LOCAL_FILES_ONLY_JSON,
  "local_device": "$JOI_V15_LOCAL_DEVICE",
  "local_dtype": "$JOI_V15_LOCAL_DTYPE",
  "local_load_in_4bit": $JOI_V15_LOCAL_LOAD_IN_4BIT_JSON,
  "local_trust_remote_code": $JOI_V15_LOCAL_TRUST_REMOTE_CODE_JSON
}
JSON

export TRANSFORMERS_OFFLINE="${TRANSFORMERS_OFFLINE:-1}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export TOKENIZERS_PARALLELISM=false
export PYTHONUNBUFFERED=1

TS="$(date +%Y%m%d_%H%M%S)"
RESULTS_ROOT="$BASE_DIR/artifacts/ga_search_runs_${TS}"
LIVE_LOG_DIR="$RESULTS_ROOT/_live_logs"
mkdir -p "$RESULTS_ROOT" "$LIVE_LOG_DIR"

echo "============================================================"
echo "JOILang GA Search Experiment Runner"
echo "============================================================"
echo "BASE_DIR=$BASE_DIR"
echo "PYTHON_BIN=$PYTHON_BIN"
echo "SCRIPT=$SCRIPT"
echo "MODEL_KEY=$MODEL_KEY"
echo "ADVISOR_MODEL_KEY=$ADVISOR_MODEL_KEY"
echo "GA_CATEGORIES=$GA_CATEGORIES"
echo "GA_LIMIT_PER_CATEGORY=$GA_LIMIT_PER_CATEGORY"
echo "GA_POPULATION=$GA_POPULATION"
echo "GA_GENS=$GA_GENS"
echo "GA_SAMPLE_SIZE=$GA_SAMPLE_SIZE"
echo "GA_VALIDATION_SIZE=$GA_VALIDATION_SIZE"
echo "LOCAL_MODELS_BASE=$LOCAL_MODELS_BASE"
echo "LOCAL_MODEL_DIR=$LOCAL_MODEL_DIR"
echo "JOI_V15_LOCAL_DEVICE=$JOI_V15_LOCAL_DEVICE"
echo "JOI_V15_LOCAL_DTYPE=$JOI_V15_LOCAL_DTYPE"
echo "JOI_V15_LOCAL_LOAD_IN_4BIT=$JOI_V15_LOCAL_LOAD_IN_4BIT"
echo "LLM_EXTRA_JSON=$LLM_EXTRA_JSON"
echo "RESULTS_ROOT=$RESULTS_ROOT"
echo "RUN_REAL_CLOUD_ADVISOR=$RUN_REAL_CLOUD_ADVISOR"
echo "============================================================"

if [ ! -f "$SCRIPT" ]; then
  echo "[ERROR] run_ga_search.py not found: $SCRIPT" >&2
  exit 1
fi

if [ ! -d "$LOCAL_MODEL_DIR" ]; then
  echo "[ERROR] local model dir not found: $LOCAL_MODEL_DIR" >&2
  echo "Available local models:" >&2
  ls -lh "$LOCAL_MODELS_BASE" >&2 || true
  exit 1
fi

# ------------------------------------------------------------
# Helper: append repeated --category flags
# ------------------------------------------------------------
append_categories() {
  local -n _arr=$1
  for c in $GA_CATEGORIES; do
    _arr+=("--category" "$c")
  done
}

# ------------------------------------------------------------
# Helper: artifact-based live monitor
# ------------------------------------------------------------
print_ga_status() {
  local out_dir="$1"

  local cand_count=0
  local advisor_prompt_count=0
  local advisor_response_count=0

  if [ -d "$out_dir/candidates" ]; then
    cand_count="$(find "$out_dir/candidates" -type f -name '*.csv' 2>/dev/null | wc -l | tr -d ' ')"
  fi
  advisor_prompt_count="$(find "$out_dir" -maxdepth 1 -type f -name 'advisor_prompt_generation_*.txt' 2>/dev/null | wc -l | tr -d ' ')"
  advisor_response_count="$(find "$out_dir" -maxdepth 1 -type f -name 'advisor_response_generation_*.json' 2>/dev/null | wc -l | tr -d ' ')"

  echo "[LIVE] out=$out_dir | cand=$cand_count | advisor=$advisor_prompt_count/$advisor_response_count"

  if [ -f "$out_dir/ga_generation_progress.csv" ]; then
    echo "[LIVE] ga_generation_progress.csv last:"
    tail -n 1 "$out_dir/ga_generation_progress.csv" || true
  fi

  if [ -f "$out_dir/population_transitions.csv" ]; then
    echo "[LIVE] population_transitions.csv last:"
    tail -n 1 "$out_dir/population_transitions.csv" || true
  fi

  if [ -f "$out_dir/ga_summary.json" ]; then
    echo "[LIVE] ga_summary.json exists"
  fi
}

run_with_monitor() {
  local name="$1"
  local out_dir="$2"
  shift 2

  mkdir -p "$out_dir"
  local log_path="$LIVE_LOG_DIR/${name}_${TS}.log"

  echo
  echo "============================================================"
  echo "[RUN] $name"
  echo "============================================================"
  echo "OUT_DIR=$out_dir"
  echo "LOG=$log_path"
  echo "[COMMAND]"
  printf '%q ' "$@"
  echo

  set +e
  "$@" > >(tee "$log_path") 2>&1 &
  local pid=$!
  set -e

  while kill -0 "$pid" 2>/dev/null; do
    print_ga_status "$out_dir"
    sleep "${STATUS_INTERVAL:-20}"
  done

  wait "$pid"
  local rc=$?

  echo
  echo "============================================================"
  echo "[FINISHED] $name rc=$rc"
  echo "============================================================"
  print_ga_status "$out_dir"

  if [ "$rc" -ne 0 ]; then
    echo "[ERROR] $name failed. See log: $log_path" >&2
    exit "$rc"
  fi
}

# ------------------------------------------------------------
# Base GA command builder
# ------------------------------------------------------------
build_base_cmd() {
  local out_dir="$1"
  local -n cmd_ref=$2

  cmd_ref=(
    "$PYTHON_BIN" "-u" "$SCRIPT"
    "--profile" "version0_15"
    "--model-key" "$MODEL_KEY"
    "--target-detpass" "90"
    "--llm-mode" "worker"
    "--population" "$GA_POPULATION"
    "--gens" "$GA_GENS"
    "--min-generations" "$GA_GENS"
    "--max-generations" "$GA_GENS"
    "--sample-size" "$GA_SAMPLE_SIZE"
    "--validation-size" "$GA_VALIDATION_SIZE"
    "--cheap-eval-limit" "$GA_CHEAP_EVAL_LIMIT"
    "--candidate-k" "1"
    "--repair-attempts" "0"
    "--det-profile" "strict"
    "--min-core-blocks" "01,02,03"
    "--selection-mode" "redesign"
    "--fitness-mode" "phase_aware"
    "--mutation-mode" "cloudless_decompiler"
    "--category-balance-mode" "guard"
    "--token-penalty-mode" "hybrid"
    "--stop-controller-mode" "active"
    "--plateau-window" "1"
    "--disruptive-max-attempts" "1"
    "--reasoning-mutation-mode" "auto"
    "--intent-hint-mode" "auto"
    "--progress" "verbose"
    "--timeout-sec" "$GA_TIMEOUT_SEC"
    "--retries" "0"
    "--limit-per-category" "$GA_LIMIT_PER_CATEGORY"
    "--output-root" "$out_dir"
    "--feedback-guided-mutation"
    "--enable-compression-mutation"
    "--enable-prompt-decompiler"
    "--enable-rendered-prompt-dedupe"
    "--enable-pareto-archive"
    "--enable-group-specialist-archives"
    "--full-run"
    "--force"
  )

  append_categories cmd_ref
}

# ------------------------------------------------------------
# 0. Parser and environment checks
# ------------------------------------------------------------
echo
echo "============================================================"
echo "[0/4] Parser / env check"
echo "============================================================"

"$PYTHON_BIN" "$SCRIPT" --help | head -80

"$PYTHON_BIN" - <<PY
from pathlib import Path
import torch
print("[CHECK] torch:", torch.__version__)
print("[CHECK] cuda_available:", torch.cuda.is_available())
print("[CHECK] cuda_device_count:", torch.cuda.device_count())
print("[CHECK] local_model_dir_exists:", Path("$LOCAL_MODEL_DIR").exists(), "$LOCAL_MODEL_DIR")
PY

# ------------------------------------------------------------
# 1. Cloudless small GA
# ------------------------------------------------------------
CLOUDLESS_OUT="$RESULTS_ROOT/ga_cloudless_small"
declare -a CMD_CLOUDLESS
build_base_cmd "$CLOUDLESS_OUT" CMD_CLOUDLESS

run_with_monitor "ga_cloudless_small" "$CLOUDLESS_OUT" "${CMD_CLOUDLESS[@]}"

# ------------------------------------------------------------
# 2. Mock advisor small GA
#    Safe: no OpenAI call. Validates advisor scheduling/artifacts.
# ------------------------------------------------------------
MOCK_ADVISOR_OUT="$RESULTS_ROOT/ga_mock_advisor_small"
declare -a CMD_MOCK
build_base_cmd "$MOCK_ADVISOR_OUT" CMD_MOCK

CMD_MOCK+=(
  "--llm-mutation-advisor"
  "--advisor-model-key" "$ADVISOR_MODEL_KEY"
  "--advisor-llm-mode" "mock"
  "--advisor-trigger-mode" "always"
  "--advisor-min-population-for-child" "4"
  "--advisor-force-child-quota"
  "--advisor-compression-child-quota" "1"
  "--advisor-prefer-compression-after-detpass" "90"
)

run_with_monitor "ga_mock_advisor_small" "$MOCK_ADVISOR_OUT" "${CMD_MOCK[@]}"

# ------------------------------------------------------------
# 3. Optional real cloud advisor small GA
#    Requires OpenAI key. RUN_REAL_CLOUD_ADVISOR=1 to enable.
# ------------------------------------------------------------
if [ "$RUN_REAL_CLOUD_ADVISOR" = "1" ]; then
  CLOUD_KEY="${OPENAI_API_KEY_PROJ_BENCH:-${JOI_EVAL_OPENAI_API_KEY:-${JOI_V15_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}}}"
  if [ -z "$CLOUD_KEY" ]; then
    echo "[ERROR] RUN_REAL_CLOUD_ADVISOR=1 but no OpenAI key found." >&2
    echo "Set one of: OPENAI_API_KEY_PROJ_BENCH, JOI_EVAL_OPENAI_API_KEY, JOI_V15_OPENAI_API_KEY, OPENAI_API_KEY" >&2
    exit 1
  fi

  export OPENAI_API_KEY="$CLOUD_KEY"
  export OPENAI_API_KEY_PROJ_BENCH="$CLOUD_KEY"
  export JOI_EVAL_OPENAI_API_KEY="$CLOUD_KEY"

  REAL_ADVISOR_OUT="$RESULTS_ROOT/ga_real_cloud_advisor_small"
  declare -a CMD_REAL
  build_base_cmd "$REAL_ADVISOR_OUT" CMD_REAL

  CMD_REAL+=(
    "--llm-mutation-advisor"
    "--advisor-model-key" "$ADVISOR_MODEL_KEY"
    "--advisor-llm-mode" "openai"
    "--advisor-trigger-mode" "always"
    "--advisor-min-population-for-child" "4"
    "--advisor-force-child-quota"
    "--advisor-compression-child-quota" "1"
    "--advisor-prefer-compression-after-detpass" "90"
    "--advisor-temperature" "0.0"
  )

  run_with_monitor "ga_real_cloud_advisor_small" "$REAL_ADVISOR_OUT" "${CMD_REAL[@]}"
else
  echo
  echo "============================================================"
  echo "[SKIP] real cloud advisor GA"
  echo "============================================================"
  echo "Set RUN_REAL_CLOUD_ADVISOR=1 to run the OpenAI advisor stage."
fi

# ------------------------------------------------------------
# Final artifact summary
# ------------------------------------------------------------
echo
echo "============================================================"
echo "DONE: GA Search experiment"
echo "============================================================"
echo "RESULTS_ROOT=$RESULTS_ROOT"
echo

find "$RESULTS_ROOT" -maxdepth 3 -type f \
  \( -name 'ga_summary.json' \
     -o -name 'ga_generation_progress.csv' \
     -o -name 'population_transitions.csv' \
     -o -name 'ga_topk_genomes.csv' \
     -o -name 'advisor_feedback_batches.jsonl' \
     -o -name 'advisor_mutation_proposals.jsonl' \
     -o -name 'mutation_proposals.jsonl' \
     -o -name 'pareto_archive.csv' \
     -o -name '*.log' \) \
  -print | sort

echo
echo "Recommended checks:"
echo "  python -m json.tool $CLOUDLESS_OUT/ga_summary.json | head -120"
echo "  head -20 $CLOUDLESS_OUT/ga_generation_progress.csv"
echo "  head -20 $MOCK_ADVISOR_OUT/population_transitions.csv"
echo "  ls -lh $RESULTS_ROOT/_live_logs"
