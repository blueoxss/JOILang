#!/usr/bin/env bash
set -euo pipefail

cd /home/mgjeong/Desktop/llm/JOILang-Server

PYTHON_BIN="${PYTHON_BIN:-python}"
RUN_BENCH="gpt_mg/version0_15_update20260413/scripts/run_benchmark.py"

export JOI_V15_OPENAI_ENDPOINT="${JOI_V15_OPENAI_ENDPOINT:-https://api.openai.com/v1/chat/completions}"

SERVICE_SCHEMA="$(realpath datasets/service_list_ver2.0.1.json)"
V07_ASSETS="$(realpath gpt_mg/version0_7)"
V14_ASSETS="$(realpath gpt_mg/version0_14)"

FULL_DATASET="${FULL_DATASET:-1}"
LIMIT_PER_CATEGORY="${LIMIT_PER_CATEGORY:-5}"

CANDIDATE_K="${CANDIDATE_K:-1}"
REPAIR_ATTEMPTS="${REPAIR_ATTEMPTS:-0}"
DET_PROFILE="${DET_PROFILE:-strict}"
PRINT_MODE="${PRINT_MODE:-summary}"

RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="gpt_mg/version0_15_update20260413/results/v07mono_v14mono_ver2_${RUN_TS}"
mkdir -p "$RUN_ROOT"

echo "============================================================"
echo "RUN_ROOT=$RUN_ROOT"
echo "SERVICE_SCHEMA=$SERVICE_SCHEMA"
echo "V07_ASSETS=$V07_ASSETS"
echo "V14_ASSETS=$V14_ASSETS"
echo "FULL_DATASET=$FULL_DATASET"
echo "LIMIT_PER_CATEGORY=$LIMIT_PER_CATEGORY"
echo "============================================================"

if [ ! -f "$RUN_BENCH" ]; then
  echo "[ERROR] run_benchmark.py not found: $RUN_BENCH" >&2
  exit 1
fi

if [ ! -f "$SERVICE_SCHEMA" ]; then
  echo "[ERROR] service schema not found: $SERVICE_SCHEMA" >&2
  exit 1
fi

if [ -z "${JOI_V15_OPENAI_API_KEY:-}" ] && [ -z "${JOI_V15_HTTP_AUTH_BEARER:-}" ]; then
  echo "[ERROR] OpenAI auth is not set." >&2
  echo "export JOI_V15_OPENAI_API_KEY='sk-...'" >&2
  exit 1
fi

required_assets=(
  grammar_ver1.5.10.md
  service_prompt_10.md
  tempo_prompt_9.md
  caution_prompt_8.md
  response_prompt_baseline_cot.md
)

check_assets() {
  local label="$1"
  local assets="$2"

  for f in "${required_assets[@]}"; do
    if [ ! -f "$assets/$f" ]; then
      echo "[ERROR] $label asset missing: $assets/$f" >&2
      exit 1
    fi
  done
}

check_assets "v07" "$V07_ASSETS"
check_assets "v14" "$V14_ASSETS"

if [ "$FULL_DATASET" = "1" ]; then
  SCOPE_ARGS=()
else
  SCOPE_ARGS=(
    --category 1 --category 2 --category 3 --category 4
    --category 5 --category 6 --category 7 --category 8
    --limit-per-category "$LIMIT_PER_CATEGORY"
  )
fi

run_one() {
  local label="$1"
  local assets="$2"

  local log="$RUN_ROOT/${label}.log"
  local out_file="$RUN_ROOT/${label}.outdir.txt"

  echo
  echo "============================================================"
  echo "[RUN] $label"
  echo "ASSETS=$assets"
  echo "============================================================"

  PYTHONFAULTHANDLER=1 \
  TRANSFORMERS_VERBOSITY=error \
  HF_HUB_DISABLE_PROGRESS_BARS=1 \
  TOKENIZERS_PARALLELISM=false \
  "$PYTHON_BIN" "$RUN_BENCH" \
    --suite paper_with_cloud_ref \
    --model-key gpt41_mini \
    --llm-mode openai \
    --llm-endpoint "$JOI_V15_OPENAI_ENDPOINT" \
    "${SCOPE_ARGS[@]}" \
    --candidate-k "$CANDIDATE_K" \
    --repair-attempts "$REPAIR_ATTEMPTS" \
    --det-profile "$DET_PROFILE" \
    --service-schema "$SERVICE_SCHEMA" \
    --prompt-render-mode legacy_v13_monolith \
    --prompt-assets-dir "$assets" \
    --print-mode "$PRINT_MODE" \
    --skip-row-report \
    2>&1 | tee "$log"

  local out_dir
  out_dir="$(grep -oP 'Output directory:\s*\K.*' "$log" | tail -1 || true)"

  if [ -z "$out_dir" ]; then
    echo "[ERROR] Could not parse Output directory from $log" >&2
    exit 1
  fi

  echo "$out_dir" > "$out_file"

  cp "$out_dir/suite_summary.csv" "$RUN_ROOT/${label}_suite_summary.csv"
  cp "$out_dir/row_comparison.csv" "$RUN_ROOT/${label}_row_comparison.csv"
  cp "$out_dir/failure_reason_summary.csv" "$RUN_ROOT/${label}_failure_reason_summary.csv" || true
  cp "$out_dir/category_summary.csv" "$RUN_ROOT/${label}_category_summary.csv" || true
  cp "$out_dir/main_model_comparison.csv" "$RUN_ROOT/${label}_main_model_comparison.csv" || true
  cp "$out_dir/tradeoff_summary.csv" "$RUN_ROOT/${label}_tradeoff_summary.csv" || true

  echo "[OK] $label output dir: $out_dir"
}

run_one "v07_mono_ver2" "$V07_ASSETS"
run_one "v14_mono_ver2" "$V14_ASSETS"

echo
echo "============================================================"
echo "DONE"
echo "RUN_ROOT=$RUN_ROOT"
echo "v07_summary=$RUN_ROOT/v07_mono_ver2_suite_summary.csv"
echo "v14_summary=$RUN_ROOT/v14_mono_ver2_suite_summary.csv"
echo "============================================================"
