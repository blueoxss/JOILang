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

### Row 1 - low (0.0)
- command_eng: Switch the dishwasher to dry mode.
- command_kor: 식기세척기를 건조 모드로 설정해줘.
- strict DET failure reasons: 
- concrete diagnostics:
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: "skipped (generation_empty_output)"
- GPT judge:
  - overall_gpt: None
  - reasoning: skipped (generation_empty_output)
- recommended prompt mutation block/micro-rule:
- GT code:
```
(#Dishwasher).dishwasher_setdishwashermode("dry")
```
- output code:
```
(#Dishwasher).dishwasher_setdishwashermode("dry")
```

### Row 2 - low (0.0)
- command_eng: Add 5 minutes to the oven.
- command_kor: 오븐의 작동 시간을 5분 늘려줘.
- strict DET failure reasons: 
- concrete diagnostics:
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: "skipped (generation_empty_output)"
- GPT judge:
  - overall_gpt: None
  - reasoning: skipped (generation_empty_output)
- recommended prompt mutation block/micro-rule:
- GT code:
```
(#Oven).oven_addmoretime(300)
```
- output code:
```
(#Oven).oven_addmoretime(300)
```
