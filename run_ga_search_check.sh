#!/usr/bin/env bash
# ==============================================================================
# run_ga_search_check.sh
# ------------------------------------------------------------------------------
# Purpose:
#   GA search를 full로 돌리기 전에 smoke부터 단계적으로 검증한다.
#
# Flow:
#   1) cloudless small
#      - advisor 없이 GA/worker/candidate generation 자체가 되는지 확인
#   2) mock advisor small
#      - API 비용 없이 advisor mutation 구조가 genome에 반영되는지 확인
#   3) real cloud advisor small
#      - OpenAI advisor가 실제 proposal을 만들고 accepted/rejected 기록이 남는지 확인
#   4) medium
#      - category 1/2/7/8 중심으로 조금 더 큰 탐색 확인
#   5) full
#      - 전체 category에 대해 장시간 GA search 실행
#
# Usage:
#   chmod +x run_ga_search_check.sh
#
#   # smoke: cloudless + mock advisor + real advisor if API key exists
#   ./run_ga_search_check.sh smoke /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
#   # medium까지 실행
#   ./run_ga_search_check.sh medium /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
#   # full까지 실행. 오래 걸릴 수 있으므로 자기 전 실행용.
#   ./run_ga_search_check.sh full /home/mgjeong/Desktop/llm/JOILang-Server cuda:0
#
# Optional env overrides:
#   MODEL_KEY=qwen25_coder_14b
#   TARGET_DETPASS=90
#   RUN_REAL_ADVISOR=1
#   RUN_ROOT=/path/to/output/root
#   JOI_V15_PYTHON=/path/to/python
#   JOI_V15_LOCAL_DEVICE=cuda:0
#   JOI_V15_LOCAL_DTYPE=bf16
#   JOI_V15_LOCAL_LOAD_IN_4BIT=false
#
# PASS/FAIL 기준:
#   - command rc=0
#   - ga_summary.json, best_genome.json, candidate CSV 생성
#   - 모든 candidate가 빈 문자열 또는 CUDA OOM이면 FAIL
#   - advisor mode에서는 advisor proposal/response/diff 파일 생성
#   - DET 점수 자체는 smoke 단계에서 0일 수 있으므로 hard fail 기준이 아니다.
#     단, 전부 OOM/empty candidate이면 runtime/prompt-budget 문제로 FAIL.
#
# Note:
#   run_ga_search.py는 --llm-extra-json을 받지 않는 버전이 있으므로 이 스크립트는
#   local model 설정을 환경변수로만 전달한다.
# ==============================================================================

set -u
set -o pipefail

MODE="${1:-smoke}"
ARG_BASE_DIR="${2:-}"
ARG_DEVICE="${3:-}"

case "$MODE" in
  smoke|medium|full)
    ;;
  *)
    echo "[ERROR] Unknown mode: $MODE" >&2
    echo "Usage: $0 {smoke|medium|full} [BASE_DIR] [DEVICE]" >&2
    exit 2
    ;;
esac

SCRIPT_TS="$(date +%Y%m%d_%H%M%S)"
MODEL_KEY="${MODEL_KEY:-qwen25_coder_14b}"
TARGET_DETPASS="${TARGET_DETPASS:-90}"

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
    if [ -f "$d/gpt_mg/version0_15_update20260413/scripts/run_ga_search.py" ]; then
      echo "$d"
      return 0
    fi
  done

  return 1
}

BASE_DIR="$(detect_base_dir || true)"
if [ -z "$BASE_DIR" ]; then
  echo "[ERROR] Could not auto-detect JOILang-Server path." >&2
  echo "Example: $0 smoke /home/mgjeong/Desktop/llm/JOILang-Server cuda:0" >&2
  exit 1
fi

cd "$BASE_DIR" || {
  echo "[ERROR] Cannot cd to BASE_DIR=$BASE_DIR" >&2
  exit 1
}

source ~/.bashrc >/dev/null 2>&1 || true

PY="${JOI_V15_PYTHON:-$(command -v python)}"
WORKER_PY="${JOI_V15_WORKER_PYTHON:-$PY}"
GA_SCRIPT="$BASE_DIR/gpt_mg/version0_15_update20260413/scripts/run_ga_search.py"

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

RUN_ROOT="${RUN_ROOT:-$BASE_DIR/artifacts/ga_search_checks_${SCRIPT_TS}_${MODE}}"
LOG_DIR="$RUN_ROOT/_logs"
SUMMARY_TSV="$RUN_ROOT/check_summary.tsv"
mkdir -p "$LOG_DIR"
: > "$SUMMARY_TSV"

record() {
  local name="$1"
  local status="$2"
  local detail="${3:-}"
  printf "%-50s : %-5s %s\n" "$name" "$status" "$detail"
  printf "%s\t%s\t%s\n" "$name" "$status" "$detail" >> "$SUMMARY_TSV"
}

has_failures() {
  awk -F'\t' '$2=="FAIL"{found=1} END{exit found ? 0 : 1}' "$SUMMARY_TSV"
}

print_context() {
  echo "=============================================================================="
  echo "GA Search Check"
  echo "=============================================================================="
  echo "MODE=$MODE"
  echo "BASE_DIR=$BASE_DIR"
  echo "GA_SCRIPT=$GA_SCRIPT"
  echo "PY=$PY"
  echo "WORKER_PY=$WORKER_PY"
  echo "MODEL_KEY=$MODEL_KEY"
  echo "TARGET_DETPASS=$TARGET_DETPASS"
  echo "LOCAL_MODELS_BASE=$LOCAL_MODELS_BASE"
  echo "LOCAL_MODEL_DIR=$LOCAL_MODEL_DIR"
  echo "JOI_V15_LOCAL_DEVICE=$JOI_V15_LOCAL_DEVICE"
  echo "JOI_V15_LOCAL_DTYPE=$JOI_V15_LOCAL_DTYPE"
  echo "JOI_V15_LOCAL_LOAD_IN_4BIT=$JOI_V15_LOCAL_LOAD_IN_4BIT"
  echo "RUN_ROOT=$RUN_ROOT"
  echo "LOG_DIR=$LOG_DIR"
  echo "=============================================================================="
}

run_ga() {
  local label="$1"
  local out_dir="$2"
  local logfile="$3"
  shift 3

  echo
  echo "=============================================================================="
  echo "[RUN] $label"
  echo "=============================================================================="
  echo "OUT_DIR=$out_dir"
  echo "LOG=$logfile"
  echo "[COMMAND]"
  printf "%q " "$PY" -u "$GA_SCRIPT" "$@"
  echo
  echo

  mkdir -p "$out_dir"

  "$PY" -u "$GA_SCRIPT" "$@" > "$logfile" 2>&1
  local rc=$?

  if [ "$rc" -eq 0 ]; then
    record "$label command" "PASS" "rc=0"
  else
    record "$label command" "FAIL" "rc=$rc log=$logfile"
  fi

  check_ga_artifacts "$label" "$out_dir"
  return "$rc"
}

check_ga_artifacts() {
  local label="$1"
  local out_dir="$2"

  [ -f "$out_dir/ga_summary.json" ] \
    && record "$label ga_summary.json" "PASS" "$out_dir/ga_summary.json" \
    || record "$label ga_summary.json" "FAIL" "missing"

  [ -f "$out_dir/best_genome.json" ] \
    && record "$label best_genome.json" "PASS" "$out_dir/best_genome.json" \
    || record "$label best_genome.json" "FAIL" "missing"

  "$PY" - "$out_dir" <<'PY' > "$out_dir/_artifact_health_check.txt" 2>&1
import json
import sys
from pathlib import Path

import pandas as pd

out = Path(sys.argv[1])
cand_dir = out / "candidates"
csvs = sorted(cand_dir.glob("*.csv"))

summary = {}
if (out / "ga_summary.json").exists():
    try:
        summary = json.loads((out / "ga_summary.json").read_text(encoding="utf-8"))
    except Exception as e:
        print("summary_parse_error", repr(e))

print("candidate_csv_count", len(csvs))

rows = 0
oom = 0
empty = 0
non_empty = 0
error_types = {}

for p in csvs:
    try:
        df = pd.read_csv(p)
    except Exception as e:
        print("candidate_csv_read_error", p, repr(e))
        continue
    rows += len(df)
    for _, r in df.iterrows():
        gen_err = str(r.get("generation_error_type", "") or "")
        if gen_err:
            error_types[gen_err] = error_types.get(gen_err, 0) + 1
        oom_flag = str(r.get("generation_oom_flag", "")).strip().lower()
        if oom_flag == "true" or gen_err == "cuda_oom":
            oom += 1
        cands = str(r.get("candidates", "") or "").strip()
        if cands in {"", '[""]', "[]", "nan", "None"}:
            empty += 1
        else:
            non_empty += 1

best = None
hist = summary.get("best_history") if isinstance(summary, dict) else None
if isinstance(hist, list) and hist:
    best = hist[-1]
print("candidate_rows", rows)
print("non_empty_candidates", non_empty)
print("empty_candidates", empty)
print("oom_rows", oom)
print("error_types", error_types)
if best:
    print("last_best_det", best.get("avg_det_score"), "last_best_pass", best.get("train_det_pass_rate"))

if len(csvs) == 0:
    print("STATUS|FAIL|no candidate CSV generated")
    raise SystemExit(1)
if rows == 0:
    print("STATUS|FAIL|candidate CSVs have zero rows")
    raise SystemExit(1)
if non_empty == 0 and (empty > 0 or oom > 0):
    print(f"STATUS|FAIL|all candidate rows are empty/OOM: rows={rows} empty={empty} oom={oom}")
    raise SystemExit(1)
if oom > 0:
    print(f"STATUS|WARN|candidate generation has OOM rows: rows={rows} empty={empty} oom={oom} non_empty={non_empty}")
    raise SystemExit(3)

print(f"STATUS|PASS|candidate_rows={rows} non_empty={non_empty} empty={empty} oom={oom}")
raise SystemExit(0)
PY

  local rc=$?
  local status_line
  status_line="$(grep 'STATUS|' "$out_dir/_artifact_health_check.txt" | tail -1 || true)"
  local status="FAIL"
  local detail="see $out_dir/_artifact_health_check.txt"

  if [ -n "$status_line" ]; then
    status="$(echo "$status_line" | cut -d'|' -f2)"
    detail="$(echo "$status_line" | cut -d'|' -f3-)"
  fi

  record "$label candidate health" "$status" "$detail"
}

check_advisor_artifacts() {
  local label="$1"
  local out_dir="$2"
  local required_mode="${3:-any}"

  local count
  count="$(find "$out_dir" -type f \( -name '*advisor*' -o -name '*proposal*' -o -name '*feedback*' \) 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$count" -gt 0 ]; then
    record "$label advisor files" "PASS" "count=$count"
  else
    record "$label advisor files" "FAIL" "no advisor/proposal/feedback files"
  fi

  if [ -s "$out_dir/ga_block_diffs.jsonl" ]; then
    record "$label block diffs" "PASS" "$out_dir/ga_block_diffs.jsonl"
  else
    record "$label block diffs" "WARN" "ga_block_diffs.jsonl missing or empty"
  fi

  "$PY" - "$out_dir" "$required_mode" <<'PY' > "$out_dir/_advisor_health_check.txt" 2>&1
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
mode = sys.argv[2]

proposal_files = list(out.glob("advisor_response_generation_*.json")) + list(out.glob("logs/advisor_generation_*.json"))
proposal_jsonl = out / "advisor_mutation_proposals.jsonl"
raw_files = list((out / "advisor_raw_responses").glob("*.txt")) if (out / "advisor_raw_responses").exists() else []

print("advisor_response_json_count", len(proposal_files))
print("advisor_mutation_proposals_jsonl", proposal_jsonl.exists(), proposal_jsonl.stat().st_size if proposal_jsonl.exists() else 0)
print("advisor_raw_response_count", len(raw_files))

accepted_like = False
for p in proposal_files:
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    text = json.dumps(data, ensure_ascii=False)
    if "accepted" in text or "proposal" in text or "advisor_status" in text:
        accepted_like = True
        break

if proposal_jsonl.exists() and proposal_jsonl.stat().st_size > 0:
    accepted_like = True

if accepted_like:
    print("STATUS|PASS|advisor proposal/response evidence exists")
    raise SystemExit(0)

print("STATUS|FAIL|advisor proposal/response evidence missing")
raise SystemExit(1)
PY

  local status_line
  status_line="$(grep 'STATUS|' "$out_dir/_advisor_health_check.txt" | tail -1 || true)"
  local status="FAIL"
  local detail="see $out_dir/_advisor_health_check.txt"

  if [ -n "$status_line" ]; then
    status="$(echo "$status_line" | cut -d'|' -f2)"
    detail="$(echo "$status_line" | cut -d'|' -f3-)"
  fi

  record "$label advisor health" "$status" "$detail"
}

print_context

# ------------------------------------------------------------------------------
# Pre-checks
# ------------------------------------------------------------------------------
[ -f "$GA_SCRIPT" ] && record "GA script exists" "PASS" "$GA_SCRIPT" || record "GA script exists" "FAIL" "$GA_SCRIPT missing"
[ -d "$LOCAL_MODEL_DIR" ] && record "local model dir exists" "PASS" "$LOCAL_MODEL_DIR" || record "local model dir exists" "FAIL" "$LOCAL_MODEL_DIR missing"

"$PY" -m compileall "$BASE_DIR/utils" "$BASE_DIR/gpt_mg/version0_15_update20260413/scripts" > "$LOG_DIR/compileall.log" 2>&1
[ "$?" -eq 0 ] && record "compileall" "PASS" "utils + legacy scripts" || record "compileall" "FAIL" "$LOG_DIR/compileall.log"

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi > "$LOG_DIR/nvidia_smi.txt" 2>&1 || true
  record "nvidia-smi" "PASS" "$LOG_DIR/nvidia_smi.txt"
else
  record "nvidia-smi" "WARN" "not found"
fi

COMMON_ARGS=(
  --profile version0_15
  --model-key "$MODEL_KEY"
  --target-detpass "$TARGET_DETPASS"
  --llm-mode worker
  --candidate-k 1
  --repair-attempts 0
  --det-profile strict
  --selection-mode redesign
  --fitness-mode phase_aware
  --mutation-mode cloudless_decompiler
  --category-balance-mode guard
  --token-penalty-mode hybrid
  --stop-controller-mode active
  --reasoning-mutation-mode auto
  --intent-hint-mode auto
  --progress verbose
  --retries 0
  --feedback-guided-mutation
  --enable-compression-mutation
  --enable-prompt-decompiler
  --enable-rendered-prompt-dedupe
  --enable-pareto-archive
  --enable-group-specialist-archives
  --full-run
  --force
)

SMALL_ARGS=(
  --population 4
  --gens 2
  --min-generations 2
  --max-generations 2
  --sample-size 2
  --validation-size 2
  --cheap-eval-limit 1
  --plateau-window 1
  --disruptive-max-attempts 1
  --timeout-sec 2400
  --limit-per-category 1
  --category 1
  --category 2
)

# ------------------------------------------------------------------------------
# 1) Cloudless small
# ------------------------------------------------------------------------------
run_ga "ga_cloudless_small" "$RUN_ROOT/ga_cloudless_small" "$LOG_DIR/ga_cloudless_small.log" \
  "${COMMON_ARGS[@]}" \
  "${SMALL_ARGS[@]}" \
  --output-root "$RUN_ROOT/ga_cloudless_small"

# ------------------------------------------------------------------------------
# 2) Mock advisor small
# ------------------------------------------------------------------------------
run_ga "ga_mock_advisor_small" "$RUN_ROOT/ga_mock_advisor_small" "$LOG_DIR/ga_mock_advisor_small.log" \
  "${COMMON_ARGS[@]}" \
  "${SMALL_ARGS[@]}" \
  --output-root "$RUN_ROOT/ga_mock_advisor_small" \
  --llm-mutation-advisor \
  --advisor-model-key gpt41_mini \
  --advisor-llm-mode mock \
  --advisor-trigger-mode always \
  --advisor-min-population-for-child 4 \
  --advisor-force-child-quota \
  --advisor-compression-child-quota 1 \
  --advisor-prefer-compression-after-detpass "$TARGET_DETPASS"

check_advisor_artifacts "ga_mock_advisor_small" "$RUN_ROOT/ga_mock_advisor_small" "mock"

# ------------------------------------------------------------------------------
# 3) Real cloud advisor small
# ------------------------------------------------------------------------------
CLOUD_API_KEY="${OPENAI_API_KEY_PROJ_BENCH:-${JOI_EVAL_OPENAI_API_KEY:-${JOI_V15_OPENAI_API_KEY:-${OPENAI_API_KEY:-}}}}"
RUN_REAL_ADVISOR="${RUN_REAL_ADVISOR:-auto}"

if [ "$RUN_REAL_ADVISOR" = "0" ]; then
  record "ga_real_cloud_advisor_small" "SKIP" "RUN_REAL_ADVISOR=0"
elif [ "$RUN_REAL_ADVISOR" = "auto" ] && [ -z "$CLOUD_API_KEY" ]; then
  record "ga_real_cloud_advisor_small" "SKIP" "no OpenAI key found"
else
  if [ -z "$CLOUD_API_KEY" ]; then
    record "ga_real_cloud_advisor_small" "FAIL" "OpenAI key missing"
  else
    export OPENAI_API_KEY="$CLOUD_API_KEY"
    export OPENAI_API_KEY_PROJ_BENCH="$CLOUD_API_KEY"
    export JOI_EVAL_OPENAI_API_KEY="$CLOUD_API_KEY"
    export LANGSMITH_TRACING="${LANGSMITH_TRACING:-false}"
    export LANGCHAIN_TRACING_V2="${LANGCHAIN_TRACING_V2:-false}"

    run_ga "ga_real_cloud_advisor_small" "$RUN_ROOT/ga_real_cloud_advisor_small" "$LOG_DIR/ga_real_cloud_advisor_small.log" \
      "${COMMON_ARGS[@]}" \
      "${SMALL_ARGS[@]}" \
      --output-root "$RUN_ROOT/ga_real_cloud_advisor_small" \
      --llm-mutation-advisor \
      --advisor-model-key gpt41_mini \
      --advisor-llm-mode openai \
      --advisor-trigger-mode always \
      --advisor-min-population-for-child 4 \
      --advisor-force-child-quota \
      --advisor-compression-child-quota 1 \
      --advisor-prefer-compression-after-detpass "$TARGET_DETPASS" \
      --advisor-temperature 0.0

    check_advisor_artifacts "ga_real_cloud_advisor_small" "$RUN_ROOT/ga_real_cloud_advisor_small" "openai"
  fi
fi

# ------------------------------------------------------------------------------
# 4) Medium search
# ------------------------------------------------------------------------------
if [ "$MODE" = "medium" ] || [ "$MODE" = "full" ]; then
  MEDIUM_ARGS=(
    --population 8
    --gens 4
    --min-generations 3
    --max-generations 4
    --sample-size 8
    --validation-size 8
    --cheap-eval-limit 4
    --plateau-window 2
    --disruptive-max-attempts 2
    --timeout-sec 3600
    --limit-per-category 2
    --category 1
    --category 2
    --category 7
    --category 8
  )

  run_ga "ga_real_cloud_advisor_medium" "$RUN_ROOT/ga_real_cloud_advisor_medium" "$LOG_DIR/ga_real_cloud_advisor_medium.log" \
    "${COMMON_ARGS[@]}" \
    "${MEDIUM_ARGS[@]}" \
    --output-root "$RUN_ROOT/ga_real_cloud_advisor_medium" \
    --llm-mutation-advisor \
    --advisor-model-key gpt41_mini \
    --advisor-llm-mode openai \
    --advisor-trigger-mode always \
    --advisor-min-population-for-child 4 \
    --advisor-force-child-quota \
    --advisor-compression-child-quota 1 \
    --advisor-prefer-compression-after-detpass "$TARGET_DETPASS" \
    --advisor-temperature 0.0

  check_advisor_artifacts "ga_real_cloud_advisor_medium" "$RUN_ROOT/ga_real_cloud_advisor_medium" "openai"
fi

# ------------------------------------------------------------------------------
# 5) Full search
# ------------------------------------------------------------------------------
if [ "$MODE" = "full" ]; then
  FULL_ARGS=(
    --population 16
    --gens 10
    --min-generations 5
    --max-generations 10
    --sample-size 40
    --validation-size 40
    --cheap-eval-limit 20
    --plateau-window 3
    --disruptive-max-attempts 3
    --timeout-sec 7200
    --category 1
    --category 2
    --category 3
    --category 4
    --category 5
    --category 6
    --category 7
    --category 8
  )

  run_ga "ga_real_cloud_advisor_full" "$RUN_ROOT/ga_real_cloud_advisor_full" "$LOG_DIR/ga_real_cloud_advisor_full.log" \
    "${COMMON_ARGS[@]}" \
    "${FULL_ARGS[@]}" \
    --output-root "$RUN_ROOT/ga_real_cloud_advisor_full" \
    --llm-mutation-advisor \
    --advisor-model-key gpt41_mini \
    --advisor-llm-mode openai \
    --advisor-trigger-mode on_failure_plateau \
    --advisor-min-population-for-child 4 \
    --advisor-force-child-quota \
    --advisor-compression-child-quota 2 \
    --advisor-prefer-compression-after-detpass "$TARGET_DETPASS" \
    --advisor-temperature 0.0

  check_advisor_artifacts "ga_real_cloud_advisor_full" "$RUN_ROOT/ga_real_cloud_advisor_full" "openai"
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
echo "- RUN_ROOT=$RUN_ROOT"
echo "- SUMMARY_TSV=$SUMMARY_TSV"
echo "- logs=$LOG_DIR"
echo

echo "Useful inspection commands:"
echo "  tail -n 120 \"$LOG_DIR/ga_cloudless_small.log\""
echo "  python -m json.tool \"$RUN_ROOT/ga_cloudless_small/ga_summary.json\" | head -120"
echo "  find \"$RUN_ROOT\" -type f \\( -name '*advisor*' -o -name '*proposal*' -o -name '*feedback*' \\) -print | sort"
echo "  grep -R \"cuda_oom\\|invalid_json\\|generation_oom_flag\" -n \"$RUN_ROOT\" | head -80"

if has_failures; then
  echo
  echo "[FINAL] FAIL"
  exit 1
else
  echo
  echo "[FINAL] PASS"
  exit 0
fi
