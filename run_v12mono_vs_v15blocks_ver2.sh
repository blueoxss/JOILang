#!/usr/bin/env bash
set -euo pipefail

cd /home/mgjeong/Desktop/llm/JOILang-Server

PYTHON_BIN="${PYTHON_BIN:-python}"
RUN_BENCH="gpt_mg/version0_15_update20260413/scripts/run_benchmark.py"

export JOI_V15_OPENAI_ENDPOINT="${JOI_V15_OPENAI_ENDPOINT:-https://api.openai.com/v1/chat/completions}"

SERVICE_SCHEMA="$(realpath datasets/service_list_ver2.0.1.json)"
V12_ASSETS="$(realpath gpt_mg/version0_12)"

LIMIT_PER_CATEGORY="${LIMIT_PER_CATEGORY:-5}"
FULL_DATASET="${FULL_DATASET:-0}"

CANDIDATE_K="${CANDIDATE_K:-1}"
REPAIR_ATTEMPTS="${REPAIR_ATTEMPTS:-0}"
DET_PROFILE="${DET_PROFILE:-strict}"
PRINT_MODE="${PRINT_MODE:-summary}"

RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="gpt_mg/version0_15_update20260413/results/v12mono_vs_v15blocks_ver2_${RUN_TS}"
mkdir -p "$RUN_ROOT"

echo "============================================================"
echo "RUN_ROOT=$RUN_ROOT"
echo "SERVICE_SCHEMA=$SERVICE_SCHEMA"
echo "V12_ASSETS=$V12_ASSETS"
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
  echo "Set one of these first:" >&2
  echo "  export JOI_V15_OPENAI_API_KEY='sk-...'" >&2
  echo "  export JOI_V15_HTTP_AUTH_BEARER='sk-...'" >&2
  exit 1
fi

required_v12_assets=(
  grammar_ver1.5.10.md
  service_prompt_10.md
  tempo_prompt_9.md
  caution_prompt_8.md
  response_prompt_baseline_cot.md
)

for f in "${required_v12_assets[@]}"; do
  if [ ! -f "$V12_ASSETS/$f" ]; then
    echo "[ERROR] v12 mono asset missing: $V12_ASSETS/$f" >&2
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

run_one() {
  local label="$1"
  shift

  local log="$RUN_ROOT/${label}.log"
  local out_file="$RUN_ROOT/${label}.outdir.txt"

  echo
  echo "============================================================"
  echo "[RUN] $label"
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
    --print-mode "$PRINT_MODE" \
    --skip-row-report \
    "$@" \
    2>&1 | tee "$log"

  local out_dir
  out_dir="$(grep -oP 'Output directory:\s*\K.*' "$log" | tail -1 || true)"

  if [ -z "$out_dir" ]; then
    echo "[ERROR] Could not parse Output directory from $log" >&2
    exit 1
  fi

  echo "$out_dir" > "$out_file"
  echo "[OK] $label output dir: $out_dir"

  cp "$out_dir/suite_summary.csv" "$RUN_ROOT/${label}_suite_summary.csv"
  cp "$out_dir/row_comparison.csv" "$RUN_ROOT/${label}_row_comparison.csv"
  cp "$out_dir/failure_reason_summary.csv" "$RUN_ROOT/${label}_failure_reason_summary.csv" || true
  cp "$out_dir/category_summary.csv" "$RUN_ROOT/${label}_category_summary.csv" || true
  cp "$out_dir/main_model_comparison.csv" "$RUN_ROOT/${label}_main_model_comparison.csv" || true
  cp "$out_dir/tradeoff_summary.csv" "$RUN_ROOT/${label}_tradeoff_summary.csv" || true
}

run_one "v12_mono_ver2" \
  --prompt-render-mode legacy_v13_monolith \
  --prompt-assets-dir "$V12_ASSETS"

run_one "v15_update_blocks_ver2" \
  --prompt-render-mode blocks

"$PYTHON_BIN" - <<'PY' "$RUN_ROOT"
import csv
import json
import os
from pathlib import Path

run_root = Path(os.sys.argv[1])
labels = ["v12_mono_ver2", "v15_update_blocks_ver2"]

def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def find_col(row, candidates, suffix=None):
    for c in candidates:
        if c in row:
            return c
    if suffix:
        for c in row:
            if c.endswith(suffix):
                return c
    return None

summary_rows = []

for label in labels:
    path = run_root / f"{label}_suite_summary.csv"
    rows = read_csv(path)
    row = rows[0] if rows else {}

    summary_rows.append({
        "label": label,
        "source_out_dir": Path(run_root / f"{label}.outdir.txt").read_text().strip(),
        "rows": row.get("rows", row.get("row_count", row.get("total", ""))),
        "avg_det": row.get("avg_det", row.get("mean_det", "")),
        "pass": row.get("pass", row.get("det_pass_count", "")),
        "det_pass_rate": row.get("det_pass_rate", row.get("pass_rate", "")),
        "gt_exact": row.get("gt_exact", row.get("gt_exact_count", "")),
        "avg_latency": row.get("avg_latency", row.get("avg_latency_sec", "")),
        "avg_prompt_tokens": row.get("avg_prompt_tokens", ""),
        "gen_errors": row.get("gen_errors", row.get("generation_errors", "")),
        "top_generation_error": row.get("top_generation_error", ""),
    })

summary_out = run_root / "twoway_summary.csv"
with summary_out.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
    writer.writeheader()
    writer.writerows(summary_rows)

print("\n============================================================")
print("TWO-WAY SUMMARY")
print("============================================================")
for row in summary_rows:
    print(json.dumps(row, ensure_ascii=False, indent=2))

row_maps = {}
for label in labels:
    rows = read_csv(run_root / f"{label}_row_comparison.csv")
    row_maps[label] = {str(r.get("row_no", "")).strip(): r for r in rows}

all_row_nos = sorted(
    set().union(*(set(m.keys()) for m in row_maps.values())),
    key=lambda x: int(x) if x.isdigit() else 10**9,
)

def get_value(row, exact_candidates, suffix):
    if not row:
        return ""
    col = find_col(row, exact_candidates, suffix=suffix)
    return row.get(col, "") if col else ""

compare_rows = []
for row_no in all_row_nos:
    base = row_maps[labels[0]].get(row_no) or row_maps[labels[1]].get(row_no) or {}
    out = {
        "row_no": row_no,
        "category": base.get("category", ""),
        "command_eng": base.get("command_eng", ""),
        "command_kor": base.get("command_kor", ""),
    }

    for label in labels:
        r = row_maps[label].get(row_no, {})
        out[f"{label}_pass"] = get_value(r, ["gpt41_mini__det_pass", "det_pass"], "__det_pass")
        out[f"{label}_score"] = get_value(r, ["gpt41_mini__det_score", "det_score"], "__det_score")
        out[f"{label}_exact"] = get_value(r, ["gpt41_mini__det_gt_exact", "det_gt_exact"], "__det_gt_exact")
        out[f"{label}_failure"] = get_value(r, ["gpt41_mini__failure_reasons", "failure_reasons"], "__failure_reasons")
        out[f"{label}_output"] = get_value(r, ["gpt41_mini__output", "output"], "__output")

    compare_rows.append(out)

row_out = run_root / "twoway_row_compare.csv"
with row_out.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(compare_rows[0].keys()) if compare_rows else ["row_no"])
    writer.writeheader()
    writer.writerows(compare_rows)

mismatch_out = run_root / "twoway_pass_mismatch.csv"
mismatch_rows = []
for r in compare_rows:
    p1 = str(r.get("v12_mono_ver2_pass", "")).lower()
    p2 = str(r.get("v15_update_blocks_ver2_pass", "")).lower()
    if p1 != p2:
        mismatch_rows.append(r)

with mismatch_out.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(compare_rows[0].keys()) if compare_rows else ["row_no"])
    writer.writeheader()
    writer.writerows(mismatch_rows)

print("\n============================================================")
print("OUTPUT FILES")
print("============================================================")
print(f"SUMMARY_CSV={summary_out}")
print(f"ROW_COMPARE_CSV={row_out}")
print(f"PASS_MISMATCH_CSV={mismatch_out}")
print(f"MISMATCH_COUNT={len(mismatch_rows)}")

if mismatch_rows:
    print("\nPASS MISMATCH ROWS")
    for r in mismatch_rows[:50]:
        print(
            f"row={r.get('row_no')} cat={r.get('category')} "
            f"v12_pass={r.get('v12_mono_ver2_pass')} "
            f"blocks_pass={r.get('v15_update_blocks_ver2_pass')} "
            f"v12_score={r.get('v12_mono_ver2_score')} "
            f"blocks_score={r.get('v15_update_blocks_ver2_score')}"
        )
PY

echo
echo "============================================================"
echo "DONE"
echo "RUN_ROOT=$RUN_ROOT"
echo "v12_mono_ver2_out=$(cat "$RUN_ROOT/v12_mono_ver2.outdir.txt")"
echo "v15_update_blocks_ver2_out=$(cat "$RUN_ROOT/v15_update_blocks_ver2.outdir.txt")"
echo "summary=$RUN_ROOT/twoway_summary.csv"
echo "row_compare=$RUN_ROOT/twoway_row_compare.csv"
echo "pass_mismatch=$RUN_ROOT/twoway_pass_mismatch.csv"
echo "============================================================"
