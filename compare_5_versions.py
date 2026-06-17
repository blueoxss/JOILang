from pathlib import Path
import pandas as pd

files = {
    "version0_7":  "gpt_mg/version0_15_update20260413/results/v07mono_v14mono_ver2_20260616_204539/v07_mono_ver2_suite_summary.csv",
    "version0_12": "gpt_mg/version0_15_update20260413/results/v12mono_vs_v15blocks_ver2_20260616_184014/v12_mono_ver2_suite_summary.csv",
    "version0_13": "gpt_mg/version0_15_update20260413/results/v13mono_ver2_only_20260616_195953/v13_mono_ver2_suite_summary.csv",
    "version0_14": "gpt_mg/version0_15_update20260413/results/v07mono_v14mono_ver2_20260616_204539/v14_mono_ver2_suite_summary.csv",
    "version0_15_blocks": "gpt_mg/version0_15_update20260413/results/v12mono_vs_v15blocks_ver2_20260616_184014/v15_update_blocks_ver2_suite_summary.csv",
}

rows = []
for version, path in files.items():
    df = pd.read_csv(path)
    r = df.iloc[0].to_dict()
    r["version"] = version
    rows.append(r)

out = pd.DataFrame(rows)

cols = [
    "version",
    "model_key",
    "row_count",
    "avg_det_score",
    "pass_count",
    "fail_count",
    "det_pass_rate",
    "gt_exact_count",
    "gt_exact_rate",
    "avg_latency_sec",
    "paper_avg_prompt_tokens",
    "paper_avg_completion_tokens",
    "paper_avg_total_tokens",
    "generation_error_rate",
    "oom_count",
    "failure_reason_topk",
]

out = out[cols]

out["det_pass_rate"] = out["det_pass_rate"] * 100
out["gt_exact_rate"] = out["gt_exact_rate"] * 100

out = out.sort_values(["avg_det_score", "det_pass_rate", "gt_exact_rate"], ascending=False)

out.to_csv("compare_5_versions.csv", index=False)
out.to_markdown("compare_5_versions.md", index=False)

print(out.to_markdown(index=False))
print("\nSaved:")
print(" - compare_5_versions.csv")
print(" - compare_5_versions.md")
