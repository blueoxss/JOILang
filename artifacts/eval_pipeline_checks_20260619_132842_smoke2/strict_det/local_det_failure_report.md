# Local DET Failure Report

- results_dir: `/root/llm/JOILang-Server/artifacts/eval_pipeline_checks_20260619_132842_smoke2/strict_det`
- model_key: `qwen25_coder_14b`
- analyzed_failure_rows: `0`

## 1. Failure taxonomy and prompt mutation mapping

| failure_reason | 설명 | target block | suggested mutation | recommended micro-rule |
|---|---|---|---|---|
| invalid_json | 생성 결과가 요구 JSON 형식 또는 필수 key 구조를 만족하지 못한 경우입니다. | 03 / Output_Schema | strengthen_json_only_rule | Return exactly one JSON object with required keys only; do not emit markdown, prose, comments, or code fences. |
| gt_mismatch | JSON은 유효하지만 GT와 최종 동작이 완전히 동일하지 않은 경우입니다. service, receiver, temporal, numeric, enum, dataflow 차이 중 하나 이상이 누적되어 발생합니다. | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| semantic | GT와 생성 코드의 high-level intent 또는 control-flow 의미가 충분히 일치하지 않는 경우입니다. 조건, trigger, 반복, action 순서, state update 방식 차이가 주요 원인입니다. | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |
| extraneous | 사용자 command나 GT에 없는 불필요한 action/read/wrapper가 추가된 경우입니다. | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_receiver_coverage | GT가 요구한 receiver tag, location, group, device target을 생성 코드가 충분히 보존하지 못한 경우입니다. | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | GT가 요구한 sensor/action service family를 생성 코드가 충분히 포함하지 못한 경우입니다. | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| service_match | 생성 코드의 service token이 schema 또는 canonical service와 충분히 일치하지 않는 경우입니다. | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service | 생성 코드가 schema에 존재하지 않는 service/member 이름을 사용한 경우입니다. | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |
| numeric_grounding | 시간, 주기, 단위, threshold, argument literal이 GT 또는 service descriptor 기준과 다르게 변환된 경우입니다. | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |
| precondition | 조건문, 상태 확인, if/wait until guard, trigger condition이 GT의 precondition과 다르게 표현된 경우입니다. | 06 / Skeleton | strengthen_precondition_rule | Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action. |
| arg_type | function argument의 type, number/string/boolean/enum literal, separator 또는 positional argument 구조가 schema와 다르게 생성된 경우입니다. | 02 / Enum_Grounding | strengthen_enum_type_rule | For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema. |
| dataflow | sensor read 결과가 downstream action/report에 올바르게 전달되지 않거나, GT의 variable binding/read-then-act 구조와 다른 경우입니다. | 06 / Dataflow | add_sensor_to_action_flow_rule | When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path. |
| enum_grounding | enum argument 또는 enum-valued condition에서 허용 값과 다른 문자열을 사용한 경우입니다. | 02 / Enum_Grounding | strengthen_enum_type_rule | For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it. |

## 2. Failure reason summary

| failure_reason | count |
|---|---:|

## 3. Row-level detailed analysis

