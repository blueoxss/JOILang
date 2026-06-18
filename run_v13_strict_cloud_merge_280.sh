#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run_v13_strict_cloud_merge_280.sh
#   ./run_v13_strict_cloud_merge_280.sh /home/mgjeong/Desktop/llm/JOILang-Server cuda:1
#   ./run_v13_strict_cloud_merge_280.sh /root/llm/JOILang-Server cuda:0
#
# Optional env overrides:
#   MODEL_KEY=qwen25_coder_14b
#   PROMPT_VERSION=version0_13
#   EVAL_LIMIT=280
#   JOI_V15_LOCAL_DEVICE=cuda:0
#   JOI_V15_LOCAL_DTYPE=bf16
#   JOI_V15_LOCAL_LOAD_IN_4BIT=false

ARG_BASE_DIR="${1:-}"
ARG_DEVICE="${2:-}"

if [ -n "$ARG_BASE_DIR" ]; then
  BASE_DIR="$ARG_BASE_DIR"
else
  CANDIDATES=(
    "/home/mgjeong/Desktop/llm/JOILang-Server"
    "/root/llm/JOILang-Server"
    "$HOME/llm/JOILang-Server"
    "$HOME/Desktop/llm/JOILang-Server"
    "$PWD"
  )

  BASE_DIR=""
  for d in "${CANDIDATES[@]}"; do
    if [ -f "$d/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py" ] && \
       [ -d "$d/utils/evaluation_cloud" ]; then
      BASE_DIR="$d"
      break
    fi
  done

  if [ -z "$BASE_DIR" ]; then
    echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
    echo "Run with explicit path, e.g.:" >&2
    echo "  $0 /home/mgjeong/Desktop/llm/JOILang-Server cuda:1" >&2
    echo "  $0 /root/llm/JOILang-Server cuda:0" >&2
    exit 1
  fi
fi

cd "$BASE_DIR"
source ~/.bashrc || true

MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
PROMPT_VERSION="${PROMPT_VERSION:-version0_13}"
EVAL_LIMIT="${EVAL_LIMIT:-280}"

STRICT_OUT_NAME="${STRICT_OUT_NAME:-model_suite_v13_strict_${EVAL_LIMIT}}"
STRICT_DIR="$BASE_DIR/gpt_mg/version0_15_update20260413/results/${STRICT_OUT_NAME}"
V13_ASSETS="$BASE_DIR/gpt_mg/version0_13"

LOCAL_MODELS_BASE="$(realpath "$BASE_DIR/../local_models")"
LOCAL_MODEL_DIR="$LOCAL_MODELS_BASE/$MODEL_KEY"

DATASET_CSV="${DATASET_CSV:-datasets/JOICommands-280.csv}"
DATASET_ABS="$BASE_DIR/$DATASET_CSV"

CLOUD_OUT_REL="${CLOUD_OUT_REL:-results/${PROMPT_VERSION}_${EVAL_LIMIT}}"
CLOUD_OUT_DIR="$BASE_DIR/utils/evaluation_cloud/$CLOUD_OUT_REL"
CLOUD_CSV="$CLOUD_OUT_DIR/result_gpt_mg_${PROMPT_VERSION}.csv"

MERGE_OUT_DIR="$BASE_DIR/artifacts/hybrid_strict_cloud_v13_${EVAL_LIMIT}"

export JOI_V15_PYTHON="${JOI_V15_PYTHON:-$(which python)}"
export JOI_V15_WORKER_PYTHON="${JOI_V15_WORKER_PYTHON:-$(which python)}"

export JOI_V15_LOCAL_MODEL_BASE_DIR="$LOCAL_MODELS_BASE"
export JOI_V15_LOCAL_MODEL_NAME="$LOCAL_MODEL_DIR"
export JOI_V15_LOCAL_FILES_ONLY="${JOI_V15_LOCAL_FILES_ONLY:-true}"
export JOI_V15_LOCAL_DEVICE="${ARG_DEVICE:-${JOI_V15_LOCAL_DEVICE:-cuda:0}}"
export JOI_V15_LOCAL_DTYPE="${JOI_V15_LOCAL_DTYPE:-bf16}"
export JOI_V15_LOCAL_LOAD_IN_4BIT="${JOI_V15_LOCAL_LOAD_IN_4BIT:-false}"
export JOI_V15_LOCAL_TRUST_REMOTE_CODE="${JOI_V15_LOCAL_TRUST_REMOTE_CODE:-true}"

LLM_EXTRA_JSON="$(mktemp)"
trap 'rm -f "$LLM_EXTRA_JSON"' EXIT

cat > "$LLM_EXTRA_JSON" <<JSON
{
  "local_model_name": "$LOCAL_MODEL_DIR",
  "local_files_only": true,
  "local_device": "$JOI_V15_LOCAL_DEVICE",
  "local_dtype": "$JOI_V15_LOCAL_DTYPE",
  "local_load_in_4bit": false,
  "local_trust_remote_code": true
}
JSON

echo "============================================================"
echo "JOILang strict DET + cloud semantic judge + adapter"
echo "============================================================"
echo "BASE_DIR=$BASE_DIR"
echo "MODEL_KEY=$MODEL_KEY"
echo "PROMPT_VERSION=$PROMPT_VERSION"
echo "STRICT_DIR=$STRICT_DIR"
echo "V13_ASSETS=$V13_ASSETS"
echo "LOCAL_MODELS_BASE=$LOCAL_MODELS_BASE"
echo "LOCAL_MODEL_DIR=$LOCAL_MODEL_DIR"
echo "JOI_V15_PYTHON=$JOI_V15_PYTHON"
echo "JOI_V15_WORKER_PYTHON=$JOI_V15_WORKER_PYTHON"
echo "JOI_V15_LOCAL_MODEL_NAME=$JOI_V15_LOCAL_MODEL_NAME"
echo "JOI_V15_LOCAL_DEVICE=$JOI_V15_LOCAL_DEVICE"
echo "JOI_V15_LOCAL_DTYPE=$JOI_V15_LOCAL_DTYPE"
echo "JOI_V15_LOCAL_FILES_ONLY=$JOI_V15_LOCAL_FILES_ONLY"
echo "DATASET_ABS=$DATASET_ABS"
echo "CLOUD_OUT_DIR=$CLOUD_OUT_DIR"
echo "CLOUD_CSV=$CLOUD_CSV"
echo "MERGE_OUT_DIR=$MERGE_OUT_DIR"
echo "EVAL_LIMIT=$EVAL_LIMIT"
echo "LLM_EXTRA_JSON=$LLM_EXTRA_JSON"
echo "============================================================"

if [ ! -d "$LOCAL_MODEL_DIR" ]; then
  echo "[ERROR] Local model directory not found: $LOCAL_MODEL_DIR" >&2
  echo "Available local models:" >&2
  ls -lh "$LOCAL_MODELS_BASE" >&2 || true
  exit 1
fi

if [ ! -f "$DATASET_ABS" ]; then
  echo "[ERROR] Dataset CSV not found: $DATASET_ABS" >&2
  exit 1
fi

python - <<PY
import pandas as pd
from pathlib import Path

p = Path("$DATASET_ABS")
df = pd.read_csv(p, encoding="utf-8-sig")
print(f"[CHECK] dataset={p}")
print(f"[CHECK] dataset rows={len(df)}")
if len(df) < int("$EVAL_LIMIT"):
    print(f"[WARN] dataset rows ({len(df)}) < EVAL_LIMIT ({int('$EVAL_LIMIT')})")
PY

mkdir -p "$STRICT_DIR" "$CLOUD_OUT_DIR" "$MERGE_OUT_DIR"

echo
echo "============================================================"
echo "[0/4] Preflight local model availability"
echo "============================================================"

python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
  --suite paper_local5 \
  --model-key "$MODEL_KEY" \
  --prompt-render-mode legacy_v13_monolith \
  --prompt-assets-dir "$V13_ASSETS" \
  --llm-extra-json "$LLM_EXTRA_JSON" \
  --preflight-only \
  --print-worker-info \
  --strict-availability

echo
echo "============================================================"
echo "[1/4] Strict DET benchmark"
echo "============================================================"

python gpt_mg/version0_15_update20260413/scripts/run_benchmark.py \
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

echo
echo "============================================================"
echo "[2/4] Export local strict DET failure report"
echo "============================================================"

python utils/export_local_det_failure_report.py \
  --results-dir "$STRICT_DIR" \
  --model-key "$MODEL_KEY"

#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./run_v13_strict_cloud_merge_280.sh
#   ./run_v13_strict_cloud_merge_280.sh /home/mgjeong/Desktop/llm/JOILang-Server cuda:1
#   ./run_v13_strict_cloud_merge_280.sh /root/llm/JOILang-Server cuda:0
#
# Optional env overrides:
#   MODEL_KEY=qwen25_coder_14b
#   PROMPT_VERSION=version0_13
#   EVAL_LIMIT=280
#   JOI_V15_LOCAL_DEVICE=cuda:0
#   JOI_V15_LOCAL_DTYPE=bf16
#   JOI_V15_LOCAL_LOAD_IN_4BIT=false

ARG_BASE_DIR="${1:-}"
ARG_DEVICE="${2:-}"

if [ -n "$ARG_BASE_DIR" ]; then
  BASE_DIR="$ARG_BASE_DIR"
else
  CANDIDATES=(
    "/home/mgjeong/Desktop/llm/JOILang-Server"
    "/root/llm/JOILang-Server"
    "$HOME/llm/JOILang-Server"
    "$HOME/Desktop/llm/JOILang-Server"
    "$PWD"
  )

  BASE_DIR=""
  for d in "${CANDIDATES[@]}"; do
    if [ -f "$d/gpt_mg/version0_15_update20260413/scripts/run_benchmark.py" ] && \
       [ -d "$d/utils/evaluation_cloud" ]; then
      BASE_DIR="$d"
      break
    fi
  done

  if [ -z "$BASE_DIR" ]; then
    echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
    echo "Run with explicit path, e.g.:" >&2
    echo "  $0 /home/mgjeong/Desktop/llm/JOILang-Server cuda:1" >&2
    echo "  $0 /root/llm/JOILang-Server cuda:0" >&2
    exit 1
  fi
fi

cd "$BASE_DIR"
source ~/.bashrc || true

MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
PROMPT_VERSION="${PROMPT_VERSION:-version0_13}"
EVAL_LIMIT="${EVAL_LIMIT:-280}"

STRICT_OUT_NAME="${STRICT_OUT_NAME:-model_suite_v13_strict_${EVAL_LIMIT}}"
STRICT_DIR="$BASE_DIR/gpt_mg/version0_15_update20260413/results/${STRICT_OUT_NAME}"
V13_ASSETS="$BASE_DIR/gpt_mg/version0_13"

LOCAL_MODELS_BASE="$(realpath "$BASE_DIR/../local_models")"
LOCAL_MODEL_DIR="$LOCAL_MODELS_BASE/$MODEL_KEY"

DATASET_CSV="${DATASET_CSV:-datasets/JOICommands-280.csv}"
DATASET_ABS="$BASE_DIR/$DATASET_CSV"

CLOUD_OUT_REL="${CLOUD_OUT_REL:-results/${PROMPT_VERSION}_${EVAL_LIMIT}}"
CLOUD_OUT_DIR="$BASE_DIR/utils/evaluation_cloud/$CLOUD_OUT_REL"
CLOUD_CSV="$CLOUD_OUT_DIR/result_gpt_mg_${PROMPT_VERSION}.csv"

MERGE_OUT_DIR="$BASE_DIR/artifacts/hybrid_strict_cloud_v13_${EVAL_LIMIT}"

export JOI_V15_PYTHON="${JOI_V15_PYTHON:-$(which python)}"
export JOI_V15_WORKER_PYTHON="${JOI_V15_WORKER_PYTHON:-$(which python)}"

export JOI_V15_LOCAL_MODEL_BASE_DIR="$LOCAL_MODELS_BASE"
export JOI_V15_LOCAL_MODEL_NAME="$LOCAL_MODEL_DIR"
export JOI_V15_LOCAL_FILES_ONLY="${JOI_V15_LOCAL_FILES_ONLY:-true}"
export JOI_V15_LOCAL_DEVICE="${ARG_DEVICE:-${JOI_V15_LOCAL_DEVICE:-cuda:0}}"
export JOI_V15_LOCAL_DTYPE="${JOI_V15_LOCAL_DTYPE:-bf16}"
export JOI_V15_LOCAL_LOAD_IN_4BIT="${JOI_V15_LOCAL_LOAD_IN_4BIT:-false}"
export JOI_V15_LOCAL_TRUST_REMOTE_CODE="${JOI_V15_LOCAL_TRUST_REMOTE_CODE:-true}"

LLM_EXTRA_JSON="$(mktemp)"
trap 'rm -f "$LLM_EXTRA_JSON"' EXIT

cat > "$LLM_EXTRA_JSON" <<JSON
{
  "local_model_name": "$LOCAL_MODEL_DIR",
  "local_files_only": true,
  "local_device": "$JOI_V15_LOCAL_DEVICE",
  "local_dtype": "$JOI_V15_LOCAL_DTYPE",
  "local_load_in_4bit": false,
  "local_trust_remote_code": true
}
JSON

echo "============================================================"
echo "JOILang strict DET + cloud semantic judge + adapter"
echo "============================================================"
echo "BASE_DIR=$BASE_DIR"
echo "MODEL_KEY=$MODEL_KEY"
echo "PROMPT_VERSION=$PROMPT_VERSION"
echo "STRICT_DIR=$STRICT_DIR"
echo "V13_ASSETS=$V13_ASSETS"
echo "LOCAL_MODELS_BASE=$LOCAL_MODELS_BASE"
echo "LOCAL_MODEL_DIR=$LOCAL_MODEL_DIR"
echo "JOI_V15_PYTHON=$JOI_V15_PYTHON"
echo "JOI_V15_WORKER_PYTHON=$JOI_V15_WORKER_PYTHON"
echo "JOI_V15_LOCAL_MODEL_NAME=$JOI_V15_LOCAL_MODEL_NAME"
echo "JOI_V15_LOCAL_DEVICE=$JOI_V15_LOCAL_DEVICE"
echo "JOI_V15_LOCAL_DTYPE=$JOI_V15_LOCAL_DTYPE"
echo "JOI_V15_LOCAL_FILES_ONLY=$JOI_V15_LOCAL_FILES_ONLY"
echo "DATASET_ABS=$DATASET_ABS"
echo "CLOUD_OUT_DIR=$CLOUD_OUT_DIR"
echo "CLOUD_CSV=$CLOUD_CSV"
echo "MERGE_OUT_DIR=$MERGE_OUT_DIR"
echo "EVAL_LIMIT=$EVAL_LIMIT"
echo "LLM_EXTRA_JSON=$LLM_EXTRA_JSON"
echo "============================================================"

if [ ! -d "$LOCAL_MODEL_DIR" ]; then
  echo "[ERROR] Local model directory not found: $LOCAL_MODEL_DIR" >&2
  echo "Available local models:" >&2
  ls -lh "$LOCAL_MODELS_BASE" >&2 || true
  exit 1
fi

if [ ! -f "$DATASET_ABS" ]; then
  echo "[ERROR] Dataset CSV not found: $DATASET_ABS" >&2
  exit 1
fi

python - <<PY
import pandas as pd
from pathlib import Path

p = Path("$DATASET_ABS")
df = pd.read_csv(p, encoding="utf-8-sig")
print(f"[CHECK] dataset={p}")
print(f"[CHECK] dataset rows={len(df)}")
if len(df) < int("$EVAL_LIMIT"):
    print(f"[WARN] dataset rows ({len(df)}) < EVAL_LIMIT ({int('$EVAL_LIMIT')})")
PY


CLOUD_API_KEY="${OPENAI_API_KEY_PROJ_BENCH:-}"

if [ -z "$CLOUD_API_KEY" ]; then
  CLOUD_API_KEY="${JOI_EVAL_OPENAI_API_KEY:-}"
fi

if [ -z "$CLOUD_API_KEY" ]; then
  CLOUD_API_KEY="${JOI_V15_OPENAI_API_KEY:-}"
fi

if [ -z "$CLOUD_API_KEY" ]; then
  CLOUD_API_KEY="${OPENAI_API_KEY:-}"
fi

if [ -z "$CLOUD_API_KEY" ]; then
  echo "[ERROR] Cloud OpenAI API key is missing." >&2
  exit 1
fi

export OPENAI_API_KEY="$CLOUD_API_KEY"
export OPENAI_API_KEY_PROJ_BENCH="$CLOUD_API_KEY"
export JOI_EVAL_OPENAI_API_KEY="$CLOUD_API_KEY"

echo "[CHECK] Cloud API key configured"


echo
echo "============================================================"
echo "[3/4] Cloud semantic judges: lang + gpt"
echo "============================================================"


EVAL_LIMIT="$EVAL_LIMIT" \
PYTHONPATH="$BASE_DIR${PYTHONPATH:+:$PYTHONPATH}" \
"$JOI_V15_PYTHON" "$BASE_DIR/utils/evaluation_cloud/main_evaluator.py" \
  lang gpt joi "$PROMPT_VERSION" \
  --out-dir "$CLOUD_OUT_DIR"


if [ ! -f "$CLOUD_CSV" ]; then
  echo "[ERROR] Cloud judge CSV not found: $CLOUD_CSV" >&2
  echo "Actual CSV files under cloud output dir:" >&2
  find "$CLOUD_OUT_DIR" -maxdepth 2 -type f -name '*.csv' -print 2>/dev/null || true
  exit 1
fi

echo
echo "============================================================"
echo "[4/4] Merge strict DET + cloud judge results"
echo "============================================================"

python utils/merge_strict_det_with_cloud_judges.py \
  --strict-results-dir "$STRICT_DIR" \
  --cloud-judge-csv "$CLOUD_CSV" \
  --model-key "$MODEL_KEY" \
  --out-dir "$MERGE_OUT_DIR"

echo
echo "============================================================"
echo "DONE"
echo "============================================================"

echo
echo "[Strict DET]"
ls -lh "$STRICT_DIR"

echo
echo "[Cloud judge]"
ls -lh "$CLOUD_OUT_DIR"

echo
echo "[Merged rich feedback]"
ls -lh "$MERGE_OUT_DIR"

echo
echo "Key outputs:"
echo "- $STRICT_DIR/row_comparison.csv"
echo "- $STRICT_DIR/failure_reason_summary.csv"
echo "- $STRICT_DIR/local_det_failure_report.json"
echo "- $CLOUD_CSV"
echo "- $MERGE_OUT_DIR/advisor_rich_feedback.json"
echo "- $MERGE_OUT_DIR/hybrid_strict_cloud_report.csv"
echo "- $MERGE_OUT_DIR/hybrid_strict_cloud_report.md"