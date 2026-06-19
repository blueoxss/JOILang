# Hybrid Strict DET + Cloud Semantic Judge Report

## 1. Summary
- total strict rows: 2
- joined cloud rows: 2
- strict-only rows: 0
- cloud-only rows: 0
- join quality: good (row_no_match)
- effective feedback mode: hybrid
- strict DET failed rows: 0
- mean strict_det_score: 100.0
- mean overall_lang: None
- mean overall_gpt: None
- top failure reasons:
- top recommended mutation blocks:
- top root causes:
  - valid_json_nonempty: 2

## 2. Failure reason × cloud judge correlation

| failure_reason | count | mean overall_lang | mean overall_gpt |
|---|---:|---:|---:|

- numeric_grounding ↔ ls_time_period mean: None
- unknown_service/service_match/gt_service_coverage ↔ ls_device_service mean: None
- semantic/gt_mismatch ↔ ls_semantic_intent mean: None
- semantic/gt_mismatch ↔ GPT mean: None
- gt_receiver_coverage ↔ conditions mean: None
- gt_receiver_coverage ↔ device_service mean: None

## 3. High-priority advisor rows

No rows selected after filters.
