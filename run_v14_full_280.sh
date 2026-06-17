#!/usr/bin/env bash
set -euo pipefail

cd /home/mgjeong/Desktop/llm/JOILang-Server

PYTHON_BIN="${PYTHON_BIN:-python}"
RUN_BENCH="gpt_mg/version0_15_update20260413/scripts/run_benchmark.py"

export JOI_V15_OPENAI_ENDPOINT="${JOI_V15_OPENAI_ENDPOINT:-https://api.openai.com/v1/chat/completions}"

SERVICE_SCHEMA="$(realpath datasets/service_list_ver2.0.1.json)"
V13_ASSETS="$(realpath gpt_mg/version0_13)"

FULL_DATASET="${FULL_DATASET:-1}"
LIMIT_PER_CATEGORY="${LIMIT_PER_CATEGORY:-5}"

CANDIDATE_K="${CANDIDATE_K:-1}"
REPAIR_ATTEMPTS="${REPAIR_ATTEMPTS:-0}"
DET_PROFILE="${DET_PROFILE:-strict}"
PRINT_MODE="${PRINT_MODE:-summary}"

RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="gpt_mg/version0_15_update20260413/results/v13mono_ver2_only_${RUN_TS}"
mkdir -p "$RUN_ROOT"

echo "============================================================"
echo "RUN_ROOT=$RUN_ROOT"
echo "SERVICE_SCHEMA=$SERVICE_SCHEMA"
echo "V13_ASSETS=$V13_ASSETS"
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

for f in "${required_assets[@]}"; do
  if [ ! -f "$V13_ASSETS/$f" ]; then
    echo "[ERROR] v13 mono asset missing: $V13_ASSETS/$f" >&2
    exit 1
  fi
done

if [ "$FULL_DATASET" = "1" ]; then
  SCOPE_ARGS=()
else
  SCOPE_ARGS=(
    --category 1 --category 2 --category 3 --category 4
    --category 5 --category 6 --category 7 --category 8
    --limit-per-category "$LIMIT_PER_CATEGORY"
  )
fi

LOG="$RUN_ROOT/v13_mono_ver2.log"
OUT_FILE="$RUN_ROOT/v13_mono_ver2.outdir.txt"

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
  --prompt-assets-dir "$V13_ASSETS" \
  --print-mode "$PRINT_MODE" \
  --skip-row-report \
  2>&1 | tee "$LOG"

OUT_DIR="$(grep -oP 'Output directory:\s*\K.*' "$LOG" | tail -1 || true)"

if [ -z "$OUT_DIR" ]; then
  echo "[ERROR] Could not parse Output directory from $LOG" >&2
  exit 1
fi

echo "$OUT_DIR" > "$OUT_FILE"

cp "$OUT_DIR/suite_summary.csv" "$RUN_ROOT/v13_mono_ver2_suite_summary.csv"
cp "$OUT_DIR/row_comparison.csv" "$RUN_ROOT/v13_mono_ver2_row_comparison.csv"
cp "$OUT_DIR/failure_reason_summary.csv" "$RUN_ROOT/v13_mono_ver2_failure_reason_summary.csv" || true
cp "$OUT_DIR/category_summary.csv" "$RUN_ROOT/v13_mono_ver2_category_summary.csv" || true

echo
echo "============================================================"
echo "DONE"
echo "RUN_ROOT=$RUN_ROOT"
echo "v13_mono_ver2_out=$OUT_DIR"
echo "summary=$RUN_ROOT/v13_mono_ver2_suite_summary.csv"
echo "row_compare=$RUN_ROOT/v13_mono_ver2_row_comparison.csv"
echo "failure_summary=$RUN_ROOT/v13_mono_ver2_failure_reason_summary.csv"
echo "category_summary=$RUN_ROOT/v13_mono_ver2_category_summary.csv"
echo "============================================================"
