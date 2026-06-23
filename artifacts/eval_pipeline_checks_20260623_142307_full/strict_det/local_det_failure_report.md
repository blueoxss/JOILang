# Local DET Failure Report

- results_dir: `/root/llm/JOILang-Server/artifacts/eval_pipeline_checks_20260623_142307_full/strict_det`
- model_key: `qwen25_coder_14b`
- analyzed_failure_rows: `49`

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
| `invalid_json.malformed_json` | 25 |
| `gt_mismatch` | 24 |
| `gt_receiver_coverage` | 21 |
| `gt_service_coverage` | 21 |
| `semantic` | 13 |
| `extraneous` | 11 |
| `numeric_grounding` | 7 |
| `service_match` | 5 |
| `enum_grounding` | 4 |
| `precondition` | 4 |
| `dataflow` | 3 |
| `arg_type` | 2 |
| `unknown_service:doorlock_lockstate` | 2 |
| `unknown_service:cloudserviceprovider_savefile` | 1 |
| `unknown_service:laundrydryer_setlaundrydryermodemode` | 1 |
| `unknown_service:robotvacuumcleaner_robotvacuumcleanermodemode` | 1 |

## 3. Row-level detailed analysis

### Row 13 | category=1 | det_score=69.9

- command_eng: Announce the fine dust level through the speaker.
- command_kor: 미세먼지 농도를 스피커로 알려줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `airqualitysensor_dustlevel`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.616584` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.616584, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
dust = (#AirQualitySensor).airqualitysensor_dustlevel

(#Speaker).speaker_speak("미세먼지 농도는 " + dust + "입니다")
```

#### Output code
```
fine_dust_level = (#WeatherProvider).weatherprovider_pm10weather
(#Speaker).speaker_speak(fine_dust_level)
```

#### Resolved services
```json
[
  {
    "device": "WeatherProvider",
    "service": "Pm10Weather",
    "canonical_name": "WeatherProvider_Pm10Weather",
    "args": [],
    "receiver": "(#WeatherProvider)"
  },
  {
    "device": "Speaker",
    "service": "Speak",
    "canonical_name": "Speaker_Speak",
    "args": [
      "fine_dust_level"
    ],
    "receiver": "(#Speaker)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.616584. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "WeatherProvider", "service": "Pm10Weather", "canonical_name": "WeatherProvider_Pm10Weather", "args": [], "receiver": "(#WeatherProvider)"}, {"device": "Speaker", "service": "Speak", "canonical_name": "Speaker_Speak", "args": ["fine_dust_level"], "receiver": "(#Speaker)"}]

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |

### Row 15 | category=1 | det_score=69.9

- command_eng: Generate a cat image using cloud service and save it as "cat.png".
- command_kor: 클라우드로 고양이 사진을 생성하고 "cat.png"로 저장해줘.
- failure_reasons: `arg_type`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `service_match`, `unknown_service:cloudserviceprovider_savefile`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `cloudserviceprovider_savetofile`.
- Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `cloudserviceprovider_savefile`.
- Unknown service detail: `cloudserviceprovider_savefile`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `cloudserviceprovider_savetofile`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.832368` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.832368, 'gt_service_coverage': 0.5, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
img = (#CloudServiceProvider).cloudserviceprovider_generateimage("Generate a cat image")

(#CloudServiceProvider).cloudserviceprovider_savetofile(img, "cat.png")
```

#### Output code
```
(#CloudServiceProvider).cloudserviceprovider_generateimage("cat")
(#CloudServiceProvider).cloudserviceprovider_savefile("cat.png")
```

#### Resolved services
```json
[
  {
    "device": "CloudServiceProvider",
    "service": "GenerateImage",
    "canonical_name": "CloudServiceProvider_GenerateImage",
    "args": [
      "\"cat\""
    ],
    "receiver": "(#CloudServiceProvider)"
  }
]
```

#### Failure-label explanation
- `arg_type`: function argument의 type, quoting, separator, positional order가 schema와 다를 수 있습니다. argument_type, argument_bounds, argument_format을 기준으로 literal을 재검증해야 합니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.832368. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "CloudServiceProvider", "service": "GenerateImage", "canonical_name": "CloudServiceProvider_GenerateImage", "args": ["\"cat\""], "receiver": "(#CloudServiceProvider)"}]
- `service_match`: service match score=. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다.
- `unknown_service:cloudserviceprovider_savefile`: 생성 코드가 현재 service schema에 없는 service/member `cloudserviceprovider_savefile`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| arg_type | 02 / Enum_Grounding | strengthen_enum_type_rule | For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| service_match | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service:cloudserviceprovider_savefile | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |

### Row 65 | category=3 | det_score=69.9

- command_eng: If the rice cooker is on keep-warm mode, switch it to cooking mode.
- command_kor: 밥솥이 보온 모드이면, 조리 모드로 변경해줘.
- failure_reasons: `enum_grounding`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.833` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `0.0` |
| `component_score_policy` | `{'gt_similarity': 0.833, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 0.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#RiceCooker).ricecooker_ricecookermode == "keepWarm") {

    (#RiceCooker).ricecooker_setricecookermode("cooking")

}
```

#### Output code
```
if ((#RiceCooker).ricecooker_ricecookermode == "keepWarm") {
  (#RiceCooker).ricecooker_setcookingparameters("cooking", 0)
}
```

#### Resolved services
```json
[
  {
    "device": "RiceCooker",
    "service": "RiceCookerMode",
    "canonical_name": "RiceCooker_RiceCookerMode",
    "args": [],
    "receiver": "(#RiceCooker)"
  },
  {
    "device": "RiceCooker",
    "service": "SetCookingParameters",
    "canonical_name": "RiceCooker_SetCookingParameters",
    "args": [
      "\"cooking\"",
      "0"
    ],
    "receiver": "(#RiceCooker)"
  }
]
```

#### Failure-label explanation
- `enum_grounding`: enum grounding score=0.0. 허용 enum 값을 paraphrase하지 말고 descriptor의 allowed value를 그대로 복사해야 합니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.833. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "RiceCooker", "service": "RiceCookerMode", "canonical_name": "RiceCooker_RiceCookerMode", "args": [], "receiver": "(#RiceCooker)"}, {"device": "RiceCooker", "service": "SetCookingParameters", "canonical_name": "RiceCooker_SetCookingParameters", "args": ["\"cooking\"", "0"], "receiver": "(#RiceCooker)"}]

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| enum_grounding | 02 / Enum_Grounding | strengthen_enum_type_rule | For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |

### Row 71 | category=3 | det_score=56.3381

- command_eng: If the laundry dryer is in low noise mode, switch it to quick mode.
- command_kor: 건조기가 저소음 모드이면, 퀵 모드로 바꿔줘.
- failure_reasons: `arg_type`, `dataflow`, `enum_grounding`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `service_match`, `unknown_service:laundrydryer_setlaundrydryermodemode`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `laundrydryer_setlaundrydryermode`.
- Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `laundrydryer_setlaundrydryermodemode`.
- Unknown service detail: `laundrydryer_setlaundrydryermodemode`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `laundrydryer_setlaundrydryermode`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `56.3381` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.867623` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `0.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `0.0` |
| `component_score_policy` | `{'gt_similarity': 0.867623, 'gt_service_coverage': 0.5, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.5, 'dataflow_score': 0.0, 'numeric_grounding': 1.0, 'enum_grounding': 0.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#LaundryDryer).laundrydryer_laundrydryermode == "lownoise") {

    (#LaundryDryer).laundrydryer_setlaundrydryermode("quick")

}
```

#### Output code
```
if ((#LaundryDryer).laundrydryer_laundrydryermode == "lownoise") {
  (#LaundryDryer).laundrydryer_setlaundrydryermodemode("quick")
}
```

#### Resolved services
```json
[
  {
    "device": "LaundryDryer",
    "service": "LaundryDryerMode",
    "canonical_name": "LaundryDryer_LaundryDryerMode",
    "args": [],
    "receiver": "(#LaundryDryer)"
  }
]
```

#### Failure-label explanation
- `arg_type`: function argument의 type, quoting, separator, positional order가 schema와 다를 수 있습니다. argument_type, argument_bounds, argument_format을 기준으로 literal을 재검증해야 합니다.
- `dataflow`: dataflow score=0.0. sensor read 값이 downstream condition/action/report에 GT와 같은 방식으로 전달되지 않았을 가능성이 있습니다.
- `enum_grounding`: enum grounding score=0.0. 허용 enum 값을 paraphrase하지 말고 descriptor의 allowed value를 그대로 복사해야 합니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.867623. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "LaundryDryer", "service": "LaundryDryerMode", "canonical_name": "LaundryDryer_LaundryDryerMode", "args": [], "receiver": "(#LaundryDryer)"}]
- `service_match`: service match score=. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다.
- `unknown_service:laundrydryer_setlaundrydryermodemode`: 생성 코드가 현재 service schema에 없는 service/member `laundrydryer_setlaundrydryermodemode`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| arg_type | 02 / Enum_Grounding | strengthen_enum_type_rule | For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema. |
| dataflow | 06 / Dataflow | add_sensor_to_action_flow_rule | When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path. |
| enum_grounding | 02 / Enum_Grounding | strengthen_enum_type_rule | For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| service_match | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service:laundrydryer_setlaundrydryermodemode | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |

### Row 74 | category=3 | det_score=69.9

- command_eng: If the button is in the pushed state, raise the blind.
- command_kor: 버튼이 눌려진 상태면, 블라인드를 올려줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `button_button`.
- Missing condition: GT condition `((#Button).button_button == "pushed"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `((#DimmerSwitch).dimmerswitch_button1 == "pushed"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.781604` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.781604, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#Button).button_button == "pushed") {

    (#Blind).windowcovering_uporopen()

}
```

#### Output code
```
if ((#DimmerSwitch).dimmerswitch_button1 == "pushed") {
  (#Blind).windowcovering_uporopen()
}
```

#### Resolved services
```json
[
  {
    "device": "DimmerSwitch",
    "service": "Button1",
    "canonical_name": "DimmerSwitch_Button1",
    "args": [],
    "receiver": "(#DimmerSwitch)"
  },
  {
    "device": "WindowCovering",
    "service": "UpOrOpen",
    "canonical_name": "WindowCovering_UpOrOpen",
    "args": [],
    "receiver": "(#Blind)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.781604. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "DimmerSwitch", "service": "Button1", "canonical_name": "DimmerSwitch_Button1", "args": [], "receiver": "(#DimmerSwitch)"}, {"device": "WindowCovering", "service": "UpOrOpen", "canonical_name": "WindowCovering_UpOrOpen", "args": [], "receiver": "(#Blind)"}]
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.781604. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 76 | category=3 | det_score=68.0895

- command_eng: If face recognition at the entrance is off, start it.
- command_kor: 입구의 얼굴 인식이 꺼져있으면, 얼굴 인식을 시작해줘
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `precondition`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `facerecognizer_start`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `68.0895` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.817893` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.817893, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#Entrance #FaceRecognizer).switch_switch == false) {

    (#Entrance #FaceRecognizer).facerecognizer_start()

}
```

#### Output code
```
if ((#Entrance #FaceRecognizer).switch_switch == false) { (#Entrance #FaceRecognizer).switch_on() }
```

#### Resolved services
```json
[
  {
    "device": "Switch",
    "service": "Switch",
    "canonical_name": "Switch_Switch",
    "args": [],
    "receiver": "(#Entrance #FaceRecognizer)"
  },
  {
    "device": "Switch",
    "service": "On",
    "canonical_name": "Switch_On",
    "args": [],
    "receiver": "(#Entrance #FaceRecognizer)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.817893. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Switch", "service": "Switch", "canonical_name": "Switch_Switch", "args": [], "receiver": "(#Entrance #FaceRecognizer)"}, {"device": "Switch", "service": "On", "canonical_name": "Switch_On", "args": [], "receiver": "(#Entrance #FaceRecognizer)"}]
- `precondition`: if/wait until guard 또는 state precondition이 GT와 다릅니다. 명령의 조건절을 action으로 바꾸거나, mode value를 state check로 오해했는지 확인해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.817893. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| precondition | 06 / Skeleton | strengthen_precondition_rule | Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 98 | category=4 | det_score=66.7591

- command_eng: When the button is pushed 3 times, open the valve.
- command_kor: 버튼이 세번 눌리면 벨브를 열어줘.
- failure_reasons: `dataflow`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `numeric_grounding`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `button_button`.
- Missing condition: GT condition `((#Button).button_button == "pushed_3x"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `DimmerSwitch_Button1 == "pushed_3x"`가 추가되었습니다.
- Missing wait-until trigger: GT는 `wait until ((#Button)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `66.7591` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.581818` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `0.0` |
| `det_numeric_grounding` | `0.75` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.581818, 'gt_service_coverage': 0.5, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.5, 'dataflow_score': 0.0, 'numeric_grounding': 0.75, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
wait until ((#Button).button_button == "pushed_3x")

(#Valve).valve_open()
```

#### Output code
```
if ((#DimmerSwitch_Button1 == "pushed_3x")) {
  (#Valve).valve_open()
}
```

#### Resolved services
```json
[
  {
    "device": "Valve",
    "service": "Open",
    "canonical_name": "Valve_Open",
    "args": [],
    "receiver": "(#Valve)"
  }
]
```

#### Failure-label explanation
- `dataflow`: dataflow score=0.0. sensor read 값이 downstream condition/action/report에 GT와 같은 방식으로 전달되지 않았을 가능성이 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.581818. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Valve", "service": "Open", "canonical_name": "Valve_Open", "args": [], "receiver": "(#Valve)"}]
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| dataflow | 06 / Dataflow | add_sensor_to_action_flow_rule | When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |

### Row 107 | category=4 | det_score=69.9

- command_eng: When motion is detected in the bedroom, turn on the bedroom air conditioner.
- command_kor: 침실에 움직임이 감지되면 침실 에어컨을 켜줘.
- failure_reasons: `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.791953` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.791953, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
wait until ((#Bedroom #MotionSensor).motionsensor_motion == true)

(#Bedroom #AirConditioner).switch_on()
```

#### Output code
```
wait until ((#Bedroom #MotionSensor).motionsensor_motion == true)
(#Bedroom #AirConditioner).airconditioner_setairconditionermode("auto")
```

#### Resolved services
```json
[
  {
    "device": "MotionSensor",
    "service": "Motion",
    "canonical_name": "MotionSensor_Motion",
    "args": [],
    "receiver": "(#Bedroom #MotionSensor)"
  },
  {
    "device": "AirConditioner",
    "service": "SetAirConditionerMode",
    "canonical_name": "AirConditioner_SetAirConditionerMode",
    "args": [
      "\"auto\""
    ],
    "receiver": "(#Bedroom #AirConditioner)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.791953. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "MotionSensor", "service": "Motion", "canonical_name": "MotionSensor_Motion", "args": [], "receiver": "(#Bedroom #MotionSensor)"}, {"device": "AirConditioner", "service": "SetAirConditionerMode", "canonical_name": "AirConditioner_SetAirConditionerMode", "args": ["\"auto\""], "receiver": "(#Bedroom #AirConditioner)"}]

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |

### Row 129 | category=5 | det_score=69.9

- command_eng: When it rains, close the door and check again after 1 hour; if it's not raining then, open the door again.
- command_kor: 비가 오면 문을 닫고 1시간 뒤에 체크해서 비가 안오면 문을 다시 열어줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `weatherprovider_weather`.
- Missing condition: GT condition `((#WeatherProvider).weatherprovider_weather != "rain"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `((#RainSensor).rainsensor_rain == false`가 추가되었습니다.
- Missing wait-until trigger: GT는 `wait until ((#RainSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.747672` |
| `det_gt_service_coverage` | `0.75` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.75` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.747672, 'gt_service_coverage': 0.75, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.75, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
wait until ((#RainSensor).rainsensor_rain == true)

(#Door).door_close()
delay(1 HOUR)

if ((#WeatherProvider).weatherprovider_weather != "rain") {

    (#Door).door_open()

}
```

#### Output code
```
if ((#RainSensor).rainsensor_rain == true) {
  (#Door).door_close()
  delay(1 HOUR)
  if ((#RainSensor).rainsensor_rain == false) {
    (#Door).door_open()
  }
}
```

#### Resolved services
```json
[
  {
    "device": "RainSensor",
    "service": "Rain",
    "canonical_name": "RainSensor_Rain",
    "args": [],
    "receiver": "(#RainSensor)"
  },
  {
    "device": "Door",
    "service": "Close",
    "canonical_name": "Door_Close",
    "args": [],
    "receiver": "(#Door)"
  },
  {
    "device": "RainSensor",
    "service": "Rain",
    "canonical_name": "RainSensor_Rain",
    "args": [],
    "receiver": "(#RainSensor)"
  },
  {
    "device": "Door",
    "service": "Open",
    "canonical_name": "Door_Open",
    "args": [],
    "receiver": "(#Door)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.747672. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.75. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.75. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "RainSensor", "service": "Rain", "canonical_name": "RainSensor_Rain", "args": [], "receiver": "(#RainSensor)"}, {"device": "Door", "service": "Close", "canonical_name": "Door_Close", "args": [], "receiver": "(#Door)"}, {"device": "RainSensor", "service": "Rain", "canonical_name": "RainSensor_Rain", "args": [], "receiver": "(#RainSensor)"}, {"device": "Door", "service": "Open", "canonical_name": "Door_Open", "args": [], "receiver": "(#Door)"}]

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |

### Row 156 | category=6 | det_score=69.9

- command_eng: If the fine dust level is 150 or higher and the door is open, close the door and set the air purifier to high.
- command_kor: 미세먼지 농도가 150 이상이고 문이 열려 있으면, 문을 닫고 공기청정기를 강풍으로 작동시켜줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `numeric_grounding`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `airqualitysensor_finedustlevel`.
- Missing condition: GT condition `((#AirQualitySensor).airqualitysensor_finedustlevel >= 150`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `((#WeatherProvider).weatherprovider_pm10weather >= 150`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.845331` |
| `det_gt_service_coverage` | `0.75` |
| `det_gt_service_precision` | `0.75` |
| `det_gt_receiver_coverage` | `0.75` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.75` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.845331, 'gt_service_coverage': 0.75, 'gt_service_precision': 0.75, 'gt_receiver_coverage': 0.75, 'dataflow_score': 1.0, 'numeric_grounding': 0.75, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#AirQualitySensor).airqualitysensor_finedustlevel >= 150 and (#Door).door_doorstate == "open") {

    (#Door).door_close()

    (#AirPurifier).airpurifier_setairpurifiermode("high")

}
```

#### Output code
```
if ((#WeatherProvider).weatherprovider_pm10weather >= 150 and (#Door).door_doorstate == "open") {
  (#Door).door_close()
  (#AirPurifier).airpurifier_setairpurifiermode("high")
}
```

#### Resolved services
```json
[
  {
    "device": "WeatherProvider",
    "service": "Pm10Weather",
    "canonical_name": "WeatherProvider_Pm10Weather",
    "args": [],
    "receiver": "(#WeatherProvider)"
  },
  {
    "device": "Door",
    "service": "DoorState",
    "canonical_name": "Door_DoorState",
    "args": [],
    "receiver": "(#Door)"
  },
  {
    "device": "Door",
    "service": "Close",
    "canonical_name": "Door_Close",
    "args": [],
    "receiver": "(#Door)"
  },
  {
    "device": "AirPurifier",
    "service": "SetAirPurifierMode",
    "canonical_name": "AirPurifier_SetAirPurifierMode",
    "args": [
      "\"high\""
    ],
    "receiver": "(#AirPurifier)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.845331. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.75. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.75. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "WeatherProvider", "service": "Pm10Weather", "canonical_name": "WeatherProvider_Pm10Weather", "args": [], "receiver": "(#WeatherProvider)"}, {"device": "Door", "service": "DoorState", "canonical_name": "Door_DoorState", "args": [], "receiver": "(#Door)"}, {"device": "Door", "service": "Close", "canonical_name": "Door_Close", "args": [], "receiver": "(#Door)"}, {"device": "AirPurifier", "service": "SetAirPurifierMode", "canonical_name": "AirPurifier_SetAirPurifierMode", "args": ["\"hi
... <truncated>
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |

### Row 167 | category=6 | det_score=69.9

- command_eng: If the bedroom temperature is 26 degrees or higher and the bedroom window is open, close the window and turn on the air conditioner.
- command_kor: 안방의 온도가 26도 이상이고 창문이 열려 있으면, 창문을 닫고 에어컨을 켜줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `numeric_grounding`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.83146` |
| `det_gt_service_coverage` | `0.75` |
| `det_gt_service_precision` | `0.6` |
| `det_gt_receiver_coverage` | `0.75` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.833333` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.83146, 'gt_service_coverage': 0.75, 'gt_service_precision': 0.6, 'gt_receiver_coverage': 0.75, 'dataflow_score': 1.0, 'numeric_grounding': 0.833333, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#Bedroom #TemperatureSensor).temperaturesensor_temperature >= 26 and (#Bedroom #Window).armrobot_currentposition > 0) {

    (#Bedroom #Window).windowcovering_downorclose()

    (#Bedroom #AirConditioner).switch_on()

}
```

#### Output code
```
if ((#Bedroom #TemperatureSensor).temperaturesensor_temperature >= 26 and (#Bedroom #Window).armrobot_currentposition > 0) {
  (#Bedroom #Window).windowcovering_downorclose()
  (#Bedroom #AirConditioner).airconditioner_setairconditionermode("cool")
  (#Bedroom #AirConditioner).airconditioner_settargettemperature(26)
}
```

#### Resolved services
```json
[
  {
    "device": "TemperatureSensor",
    "service": "Temperature",
    "canonical_name": "TemperatureSensor_Temperature",
    "args": [],
    "receiver": "(#Bedroom #TemperatureSensor)"
  },
  {
    "device": "ArmRobot",
    "service": "CurrentPosition",
    "canonical_name": "ArmRobot_CurrentPosition",
    "args": [],
    "receiver": "(#Bedroom #Window)"
  },
  {
    "device": "WindowCovering",
    "service": "DownOrClose",
    "canonical_name": "WindowCovering_DownOrClose",
    "args": [],
    "receiver": "(#Bedroom #Window)"
  },
  {
    "device": "AirConditioner",
    "service": "SetAirConditionerMode",
    "canonical_name": "AirConditioner_SetAirConditionerMode",
    "args": [
      "\"cool\""
    ],
    "receiver": "(#Bedroom #AirConditioner)"
  },
  {
    "device": "AirConditioner",
    "service": "SetTargetTemperature",
    "canonical_name": "AirConditioner_SetTargetTemperature",
    "args": [
      "26"
    ],
    "receiver": "(#Bedroom #AirConditioner)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.83146. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.75. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.75. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "TemperatureSensor", "service": "Temperature", "canonical_name": "TemperatureSensor_Temperature", "args": [], "receiver": "(#Bedroom #TemperatureSensor)"}, {"device": "ArmRobot", "service": "CurrentPosition", "canonical_name": "ArmRobot_CurrentPosition", "args": [], "receiver": "(#Bedroom #Window)"}, {"device": "WindowCovering", "service": "DownOrClose", "canonical_name": "WindowCovering_DownOrClose", "args": [], "receiver": "(#Bedroom #Window)"}, {"device": "AirConditioner", "servic
... <truncated>
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |

### Row 176 | category=6 | det_score=69.9

- command_eng: If the wine cellar temperature is 15 degrees or higher and humidity is 60% or higher, turn on the air conditioner and turn off the humidifier.
- command_kor: 와인 셀러 온도가 15도 이상이고 습도가 60% 이상이면, 에어컨을 켜고 가습기를 꺼줘.
- failure_reasons: `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.86787` |
| `det_gt_service_coverage` | `0.75` |
| `det_gt_service_precision` | `0.75` |
| `det_gt_receiver_coverage` | `0.75` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.86787, 'gt_service_coverage': 0.75, 'gt_service_precision': 0.75, 'gt_receiver_coverage': 0.75, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`0`
- Output: cron=``, period=`0`

#### GT code
```
if ((#WineCellar #TemperatureSensor).temperaturesensor_temperature >= 15 and (#WineCellar #HumiditySensor).humiditysensor_humidity >= 60) {

    (#AirConditioner).switch_on()

    (#Humidifier).switch_off()

}
```

#### Output code
```
if ((#WineCellar #TemperatureSensor).temperaturesensor_temperature >= 15 and (#WineCellar #HumiditySensor).humiditysensor_humidity >= 60) {
  (#WineCellar #AirConditioner).airconditioner_setairconditionermode("cool")
  (#WineCellar #Humidifier).switch_off()
}
```

#### Resolved services
```json
[
  {
    "device": "TemperatureSensor",
    "service": "Temperature",
    "canonical_name": "TemperatureSensor_Temperature",
    "args": [],
    "receiver": "(#WineCellar #TemperatureSensor)"
  },
  {
    "device": "HumiditySensor",
    "service": "Humidity",
    "canonical_name": "HumiditySensor_Humidity",
    "args": [],
    "receiver": "(#WineCellar #HumiditySensor)"
  },
  {
    "device": "AirConditioner",
    "service": "SetAirConditionerMode",
    "canonical_name": "AirConditioner_SetAirConditionerMode",
    "args": [
      "\"cool\""
    ],
    "receiver": "(#WineCellar #AirConditioner)"
  },
  {
    "device": "Switch",
    "service": "Off",
    "canonical_name": "Switch_Off",
    "args": [],
    "receiver": "(#WineCellar #Humidifier)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.86787. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.75. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.75. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "TemperatureSensor", "service": "Temperature", "canonical_name": "TemperatureSensor_Temperature", "args": [], "receiver": "(#WineCellar #TemperatureSensor)"}, {"device": "HumiditySensor", "service": "Humidity", "canonical_name": "HumiditySensor_Humidity", "args": [], "receiver": "(#WineCellar #HumiditySensor)"}, {"device": "AirConditioner", "service": "SetAirConditionerMode", "canonical_name": "AirConditioner_SetAirConditionerMode", "args": ["\"cool\""], "receiver": "(#WineCellar #Ai
... <truncated>

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |

### Row 182 | category=7 | det_score=0.0

- command_eng: Every 30 minutes, if the temperature is 20 degrees or higher and below 30 degrees, set the air conditioner to auto mode; if it is 30 degrees or higher, set it to cool mode.
- command_kor: 30분마다 체크해서 온도가 20도 이상, 30도 미만이면 에어컨을 자동모드로 설정하고, 30도 이상이면 쿨모드로 설정해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`1800000`
- Output: cron=``, period=``

#### GT code
```
temp = (#TemperatureSensor).temperaturesensor_temperature

if (temp >= 20 and temp < 30) {

    (#AirConditioner).airconditioner_setairconditionermode("auto")

} else if (temp >= 30) {

    (#AirConditioner).airconditioner_setairconditionermode("cool")

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 185 | category=7 | det_score=52.9106

- command_eng: Set the rice cooker to reheating mode every morning at 7 AM.
- command_kor: 매일 아침 7시에 밥솥을 재가열 모드로 설정해줘.
- failure_reasons: `enum_grounding`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `52.9106` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.667826` |
| `det_gt_service_coverage` | `0.0` |
| `det_gt_service_precision` | `0.0` |
| `det_gt_receiver_coverage` | `0.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `0.0` |
| `component_score_policy` | `{'gt_similarity': 0.667826, 'gt_service_coverage': 0.0, 'gt_service_precision': 0.0, 'gt_receiver_coverage': 0.0, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 0.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 7 * * *`, period=`0`
- Output: cron=`0 7 * * *`, period=`0`

#### GT code
```
(#RiceCooker).ricecooker_setricecookermode("reheating")
```

#### Output code
```
(#RiceCooker).ricecooker_setcookingparameters("reheating", 0)
```

#### Resolved services
```json
[
  {
    "device": "RiceCooker",
    "service": "SetCookingParameters",
    "canonical_name": "RiceCooker_SetCookingParameters",
    "args": [
      "\"reheating\"",
      "0"
    ],
    "receiver": "(#RiceCooker)"
  }
]
```

#### Failure-label explanation
- `enum_grounding`: enum grounding score=0.0. 허용 enum 값을 paraphrase하지 말고 descriptor의 allowed value를 그대로 복사해야 합니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.667826. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.0. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.0. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "RiceCooker", "service": "SetCookingParameters", "canonical_name": "RiceCooker_SetCookingParameters", "args": ["\"reheating\"", "0"], "receiver": "(#RiceCooker)"}]
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.667826. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| enum_grounding | 02 / Enum_Grounding | strengthen_enum_type_rule | For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 190 | category=7 | det_score=51.8391

- command_eng: On weekdays at 7 AM, start the rice cooker in auto-cleaning mode.
- command_kor: 평일 오전 7시에 밥솥을 자동청소 모드로 작동해줘.
- failure_reasons: `enum_grounding`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `51.8391` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.667826` |
| `det_gt_service_coverage` | `0.0` |
| `det_gt_service_precision` | `0.0` |
| `det_gt_receiver_coverage` | `0.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `0.0` |
| `component_score_policy` | `{'gt_similarity': 0.667826, 'gt_service_coverage': 0.0, 'gt_service_precision': 0.0, 'gt_receiver_coverage': 0.0, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 0.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 7 * * 1-5`, period=`0`
- Output: cron=`0 7 * * 1-5`, period=`0`

#### GT code
```
(#RiceCooker).ricecooker_setricecookermode("autoClean")
```

#### Output code
```
(#RiceCooker).ricecooker_setcookingparameters("autoClean", 0)
```

#### Resolved services
```json
[
  {
    "device": "RiceCooker",
    "service": "SetCookingParameters",
    "canonical_name": "RiceCooker_SetCookingParameters",
    "args": [
      "\"autoClean\"",
      "0"
    ],
    "receiver": "(#RiceCooker)"
  }
]
```

#### Failure-label explanation
- `enum_grounding`: enum grounding score=0.0. 허용 enum 값을 paraphrase하지 말고 descriptor의 allowed value를 그대로 복사해야 합니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.667826. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.0. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.0. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "RiceCooker", "service": "SetCookingParameters", "canonical_name": "RiceCooker_SetCookingParameters", "args": ["\"autoClean\"", "0"], "receiver": "(#RiceCooker)"}]
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.667826. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| enum_grounding | 02 / Enum_Grounding | strengthen_enum_type_rule | For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 193 | category=7 | det_score=69.9

- command_eng: Every Monday at 8 AM, if both the safe and the door lock are locked, say 'It is safe' through the speaker
- command_kor: 월요일 아침 8시마다 금고와 도어락이 모두 잠겨있으면 스피커로 "안전합니다"라고 말해줘.
- failure_reasons: `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `semantic`, `service_match`, `unknown_service:doorlock_lockstate`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `doorlock_doorlockstate`.
- Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `doorlock_lockstate`.
- Unknown service detail: `doorlock_lockstate`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `doorlock_doorlockstate`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
- Condition mismatch: `((#Safe).safe_safestate` 비교식이 다릅니다 (value GT `"locked"` vs output `"closed"`). GT condition `((#Safe).safe_safestate == "locked"` vs output condition `((#Safe).safe_safestate == "closed"`.
- Missing condition: GT condition `(#DoorLock).doorlock_doorlockstate == "locked"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `(#DoorLock).doorlock_lockstate == "locked"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.901282` |
| `det_gt_service_coverage` | `0.666667` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.666667` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.901282, 'gt_service_coverage': 0.666667, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.666667, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 8 * * 1`, period=`0`
- Output: cron=`0 8 * * 1`, period=`0`

#### GT code
```
if ((#Safe).safe_safestate == "locked" and (#DoorLock).doorlock_doorlockstate == "locked") {

    (#Speaker).speaker_speak("안전합니다")

}
```

#### Output code
```
if ((#Safe).safe_safestate == "closed" and (#DoorLock).doorlock_lockstate == "locked") {
  (#Speaker).speaker_speak("안전합니다")
}
```

#### Resolved services
```json
[
  {
    "device": "Safe",
    "service": "SafeState",
    "canonical_name": "Safe_SafeState",
    "args": [],
    "receiver": "(#Safe)"
  },
  {
    "device": "Speaker",
    "service": "Speak",
    "canonical_name": "Speaker_Speak",
    "args": [
      "\"안전합니다\""
    ],
    "receiver": "(#Speaker)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.901282. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.666667. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.666667. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Safe", "service": "SafeState", "canonical_name": "Safe_SafeState", "args": [], "receiver": "(#Safe)"}, {"device": "Speaker", "service": "Speak", "canonical_name": "Speaker_Speak", "args": ["\"안전합니다\""], "receiver": "(#Speaker)"}]
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.901282. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.
- `service_match`: service match score=. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다.
- `unknown_service:doorlock_lockstate`: 생성 코드가 현재 service schema에 없는 service/member `doorlock_lockstate`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |
| service_match | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service:doorlock_lockstate | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |

### Row 194 | category=7 | det_score=69.0201

- command_eng: Every 30 minutes from 7 PM to 10 PM, check the robot vacuum cleaner and start it in auto mode if it is stopped.
- command_kor: 저녁 7시부터 10시까지 30분마다 로봇청소기를 체크해서 멈춰있으면 자동 모드로 실행시켜줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `semantic`, `service_match`, `unknown_service:robotvacuumcleaner_robotvacuumcleanermodemode`

#### Concrete mismatch diagnostics
- Schedule mismatch: cron이 다릅니다. GT=`0,30 19-21 * * *` vs output=`0 19-22 * * *`.
- Schedule mismatch: period가 다릅니다. GT=`0` vs output=`1800000`.
- Extraneous temporal guard: GT는 cron 필드로 시간 범위를 이미 표현하므로 output code 안의 `#Clock` 조건은 중복/불필요한 guard일 가능성이 큽니다.
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `robotvacuumcleaner_robotvacuumcleanermode`.
- Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `robotvacuumcleaner_robotvacuumcleanermodemode`.
- Unknown service detail: `robotvacuumcleaner_robotvacuumcleanermodemode`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `robotvacuumcleaner_setrobotvacuumcleanermodemode`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
- Missing condition: GT condition `((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermode == "stop"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermodemode == "stop"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.0201` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.642105` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.642105, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0,30 19-21 * * *`, period=`0`
- Output: cron=`0 19-22 * * *`, period=`1800000`

#### GT code
```
if ((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermode == "stop") {

    (#RobotVacuumCleaner).robotvacuumcleaner_setrobotvacuumcleanermodemode("auto")

}
```

#### Output code
```
if ((#Clock).clock_hour >= 19 and (#Clock).clock_hour < 22) {
  if ((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermodemode == "stop") {
    (#RobotVacuumCleaner).robotvacuumcleaner_setrobotvacuumcleanermodemode("auto")
  }
} else {
  break
}
```

#### Resolved services
```json
[
  {
    "device": "Clock",
    "service": "Hour",
    "canonical_name": "Clock_Hour",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "Clock",
    "service": "Hour",
    "canonical_name": "Clock_Hour",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "RobotVacuumCleaner",
    "service": "SetRobotVacuumCleanerModeMode",
    "canonical_name": "RobotVacuumCleaner_SetRobotVacuumCleanerModeMode",
    "args": [
      "\"auto\""
    ],
    "receiver": "(#RobotVacuumCleaner)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.642105. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Clock", "service": "Hour", "canonical_name": "Clock_Hour", "args": [], "receiver": "(#Clock)"}, {"device": "Clock", "service": "Hour", "canonical_name": "Clock_Hour", "args": [], "receiver": "(#Clock)"}, {"device": "RobotVacuumCleaner", "service": "SetRobotVacuumCleanerModeMode", "canonical_name": "RobotVacuumCleaner_SetRobotVacuumCleanerModeMode", "args": ["\"auto\""], "receiver": "(#RobotVacuumCleaner)"}]
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.642105. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.
- `service_match`: service match score=. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다.
- `unknown_service:robotvacuumcleaner_robotvacuumcleanermodemode`: 생성 코드가 현재 service schema에 없는 service/member `robotvacuumcleaner_robotvacuumcleanermodemode`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |
| service_match | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service:robotvacuumcleaner_robotvacuumcleanermodemode | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |

### Row 197 | category=7 | det_score=69.9

- command_eng: At 11 PM, if safe is unlocked or the door lock is unlocked , speak 'Check the safe and door lock' through the speaker.
- command_kor: 오후 11시에 금고가 열려있거나 도어락이 열려있으면, 스피커로 "금고와 도어락을 확인하세요"라고 말해줘.
- failure_reasons: `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `service_match`, `unknown_service:doorlock_lockstate`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `doorlock_doorlockstate`.
- Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `doorlock_lockstate`.
- Unknown service detail: `doorlock_lockstate`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `doorlock_doorlockstate`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
- Condition mismatch: `((#Safe).safe_safestate` 비교식이 다릅니다 (value GT `"unlocked"` vs output `"open"`). GT condition `((#Safe).safe_safestate == "unlocked"` vs output condition `((#Safe).safe_safestate == "open"`.
- Missing condition: GT condition `(#DoorLock).doorlock_doorlockstate == "unlocked"`에 대응되는 output condition을 찾지 못했습니다.
- Extra condition: output에 GT에서 요구하지 않은 조건 `(#DoorLock).doorlock_lockstate == "open"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.814842` |
| `det_gt_service_coverage` | `0.666667` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.666667` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.814842, 'gt_service_coverage': 0.666667, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.666667, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 23 * * *`, period=`0`
- Output: cron=`0 23 * * *`, period=`0`

#### GT code
```
if ((#Safe).safe_safestate == "unlocked" or (#DoorLock).doorlock_doorlockstate == "unlocked") {

    (#Speaker).speaker_speak("금고와 도어락의 잠금 상태를 확인해 주세요.")

}
```

#### Output code
```
if ((#Safe).safe_safestate == "open" or (#DoorLock).doorlock_lockstate == "open") {
  (#Speaker).speaker_speak("Check the safe and door lock")
}
```

#### Resolved services
```json
[
  {
    "device": "Safe",
    "service": "SafeState",
    "canonical_name": "Safe_SafeState",
    "args": [],
    "receiver": "(#Safe)"
  },
  {
    "device": "Speaker",
    "service": "Speak",
    "canonical_name": "Speaker_Speak",
    "args": [
      "\"Check the safe and door lock\""
    ],
    "receiver": "(#Speaker)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.814842. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.666667. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.666667. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Safe", "service": "SafeState", "canonical_name": "Safe_SafeState", "args": [], "receiver": "(#Safe)"}, {"device": "Speaker", "service": "Speak", "canonical_name": "Speaker_Speak", "args": ["\"Check the safe and door lock\""], "receiver": "(#Speaker)"}]
- `service_match`: service match score=. schema에 있는 canonical service/value name과 output token의 일치 여부를 확인해야 합니다.
- `unknown_service:doorlock_lockstate`: 생성 코드가 현재 service schema에 없는 service/member `doorlock_lockstate`를 사용했습니다. output code에서 해당 token을 찾아 canonical service/value로 치환해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| service_match | 02 / Service_Mapping | add_canonical_service_name_rule | Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier. |
| unknown_service:doorlock_lockstate | 02 / Service_Mapping | add_canonical_service_name_rule | Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list. |

### Row 198 | category=7 | det_score=0.0

- command_eng: Check every 30 minutes; if the temperature is 30 degrees or higher, set the target temperature to 25 degrees; if it's below 23 degrees, set it to 26 degrees.
- command_kor: 30분마다 체크해서 온도가 30도 이상이면 목표 온도를 25도로 설정하고, 23도 미만이면 26도로 설정해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`1800000`
- Output: cron=``, period=``

#### GT code
```
temp = (#TemperatureSensor).temperaturesensor_temperature

if (temp >= 30) {

    (#AirConditioner).airconditioner_settargettemperature(25)

} else if (temp < 23) {

    (#AirConditioner).airconditioner_settargettemperature(26)

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 199 | category=7 | det_score=0.0

- command_eng: Check humidity every 10 minutes; if it's 50 or higher, turn off the humidifier; if it's 20 or lower, turn on the humidifier and set it to auto mode.
- command_kor: 10분마다 습도를 체크해서 50 이상이면 가습기를 끄고 20 이하면 가습기를 켜고 자동모드로 설정해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`600000`
- Output: cron=``, period=``

#### GT code
```
hum = (#HumiditySensor).humiditysensor_humidity

if (hum >= 50) {

    (#Humidifier).switch_off()

} else if (hum <= 20) {

    (#Humidifier).switch_on()

    (#Humidifier).humidifier_sethumidifiermode("auto")

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 200 | category=7 | det_score=0.0

- command_eng: Check the fine dust level every hour; if it's 200 or higher, set the air purifier to high speed; if it's 100 or lower, set it to low speed.
- command_kor: 1시간마다 미세먼지 농도를 체크해서 200 이상이면 공기청정기를 강풍모드로 설정하고 100 이하이면 미풍모드로 설정해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
dust = (#AirQualitySensor).airqualitysensor_finedustlevel

if (dust >= 200) {

    (#AirPurifier).airpurifier_setairpurifiermode("high")

} else if (dust <= 100) {

    (#AirPurifier).airpurifier_setairpurifiermode("low")

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 212 | category=7 | det_score=0.0

- command_eng: Check all door locks in Sector 1 every hour; if any one is open, change all lights in that sector to red.
- command_kor: 섹터1의 모든 도어락을 1시간마다 확인해서, 하나라도 열려 있으면 해당 섹터의 모든 조명을 빨간색으로 바꿔줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
if (all(#Sector1 #DoorLock).doorlock_doorlockstate ==| "open") {

    all(#Sector1 #Light).light_movetorgb(255, 0, 0)

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 214 | category=7 | det_score=69.9

- command_eng: Every 8 AM, open all blinds with odd tags, and at 9 AM, open all blinds with even tags.
- command_kor: 아침 8시에 홀수 태그가 붙은 블라인드를 모두 열어주고, 9시에는 짝수 태그가 붙은 모든 블라인드를 열어줘.
- failure_reasons: `gt_mismatch`, `numeric_grounding`, `semantic`

#### Concrete mismatch diagnostics
- Delay mismatch: GT delay=['1 HOUR'] vs output delay=[].

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.77089` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.77089, 'gt_service_coverage': 1.0, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 1.0, 'dataflow_score': 1.0, 'numeric_grounding': 0.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 8 * * *`, period=`0`
- Output: cron=`0 8 * * *`, period=`0`

#### GT code
```
all(#Odd #Blind).windowcovering_uporopen()

delay(1 HOUR)

all(#Even #Blind).windowcovering_uporopen()
```

#### Output code
```
all(#Odd #Even #Blind).windowcovering_uporopen()
```

#### Resolved services
```json
[
  {
    "device": "WindowCovering",
    "service": "UpOrOpen",
    "canonical_name": "WindowCovering_UpOrOpen",
    "args": [],
    "receiver": "all(#Odd #Even #Blind)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.77089. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.77089. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 215 | category=7 | det_score=68.1437

- command_eng: Every 30 minutes during weekends, check all pumps in the factory; if any one is turned on, turn off all pumps and send an email to "test@example.com" with the subject 'Risk' and message 'A pump is turned on'.
- command_kor: 주말 동안 공장의 모든 펌프를 30분마다 확인해서, 켜진 펌프가 하나라도 있으면 모두 꺼주고 "test@example.com"에게 "위험" 제목으로 "펌프가 켜졌습니다"라는 내용의 메일 보내줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `precondition`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_off`, `switch_switch`.
- Condition mismatch: `(#Clock).clock_weekday` 비교식이 다릅니다 (value GT `"sunday"` vs output `"saturday"`). GT condition `(#Clock).clock_weekday != "sunday"` vs output condition `((#Clock).clock_weekday != "saturday"`.
- Extra condition: output에 GT에서 요구하지 않은 조건 `(all(#Factory #Pump).pump_pumpmode != "normal"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `68.1437` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.6716` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.5` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.6716, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.5, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 0 * * 6-7`, period=`1800000`
- Output: cron=`0 0 * * 6-7`, period=`1800000`

#### GT code
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {

    break

}

if (all(#Factory #Pump).switch_switch ==| true) {

    all(#Factory #Pump).switch_off()

    (#EmailProvider).emailprovider_sendmail("test@example.com", "위험", "펌프가 켜졌습니다")

}
```

#### Output code
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {
    break
}

if (all(#Factory #Pump).pump_pumpmode != "normal") {
  all(#Factory #Pump).pump_setpumpmode("normal")
  (#EmailProvider).emailprovider_sendmail("test@example.com", "Risk", "A pump is turned on")
}
```

#### Resolved services
```json
[
  {
    "device": "Clock",
    "service": "Weekday",
    "canonical_name": "Clock_Weekday",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "Clock",
    "service": "Weekday",
    "canonical_name": "Clock_Weekday",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "Pump",
    "service": "PumpMode",
    "canonical_name": "Pump_PumpMode",
    "args": [],
    "receiver": "all(#Factory #Pump)"
  },
  {
    "device": "Pump",
    "service": "SetPumpMode",
    "canonical_name": "Pump_SetPumpMode",
    "args": [
      "\"normal\""
    ],
    "receiver": "all(#Factory #Pump)"
  },
  {
    "device": "EmailProvider",
    "service": "SendMail",
    "canonical_name": "EmailProvider_SendMail",
    "args": [
      "\"test@example.com\"",
      "\"Risk\"",
      "\"A pump is turned on\""
    ],
    "receiver": "(#EmailProvider)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.6716. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Clock", "service": "Weekday", "canonical_name": "Clock_Weekday", "args": [], "receiver": "(#Clock)"}, {"device": "Clock", "service": "Weekday", "canonical_name": "Clock_Weekday", "args": [], "receiver": "(#Clock)"}, {"device": "Pump", "service": "PumpMode", "canonical_name": "Pump_PumpMode", "args": [], "receiver": "all(#Factory #Pump)"}, {"device": "Pump", "service": "SetPumpMode", "canonical_name": "Pump_SetPumpMode", "args": ["\"normal\""], "receiver": "all(#Factory #Pump)"}, {"d
... <truncated>
- `precondition`: if/wait until guard 또는 state precondition이 GT와 다릅니다. 명령의 조건절을 action으로 바꾸거나, mode value를 state check로 오해했는지 확인해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.6716. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| precondition | 06 / Skeleton | strengthen_precondition_rule | Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 218 | category=7 | det_score=0.0

- command_eng: Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.
- command_kor: 자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=`0 0-5 * * *`, period=`0`
- Output: cron=``, period=``

#### GT code
```
if (all(#Door).door_doorstate ==| "open") {

    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 219 | category=7 | det_score=0.0

- command_eng: If no motion is detected between 10 PM and 11 PM, lock all door locks.
- command_kor: 밤 10시부터 11시까지 움직임이 한번도 감지되지 않았으면, 모든 도어락을 잠궈줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=`0 22 * * *`, period=`100`
- Output: cron=``, period=``

#### GT code
```
if ((#MotionSensor).motionsensor_motion == true) {

    break

}

if ((#Clock).clock_hour == 23) {

    all(#DoorLock).doorlock_lock()

    break

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 223 | category=7 | det_score=0.0

- command_eng: Every 30 seconds from 10 PM to 11 PM, check for rain every 30 seconds; if it rains, close the window.
- command_kor: 오후 10시부터 11시까지 30초마다 비를 감지해서 비가 오면 창문을 닫아줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=`0 22 * * *`, period=`30000`
- Output: cron=``, period=``

#### GT code
```
if ((#Clock).clock_hour == 23) {

    break

}

if ((#RainSensor).rainsensor_rain == true) {

    (#Window).windowcovering_downorclose()

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 224 | category=7 | det_score=66.9016

- command_eng: Every 5 seconds on weekends, if the pump is off, turn it on; if it is on, turn it off.
- command_kor: 주말에 5초마다 체크해서 펌프가 꺼져 있으면 켜고, 켜져 있으면 꺼줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `precondition`, `semantic`

#### Concrete mismatch diagnostics
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_toggle`.
- Condition mismatch: `(#Clock).clock_weekday` 비교식이 다릅니다 (value GT `"sunday"` vs output `"saturday"`). GT condition `(#Clock).clock_weekday != "sunday"` vs output condition `((#Clock).clock_weekday != "saturday"`.
- Extra condition: output에 GT에서 요구하지 않은 조건 `((#Pump).pump_pumpmode == "minimum"`가 추가되었습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `66.9016` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.708893` |
| `det_gt_service_coverage` | `0.5` |
| `det_gt_service_precision` | `0.333333` |
| `det_gt_receiver_coverage` | `0.5` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.708893, 'gt_service_coverage': 0.5, 'gt_service_precision': 0.333333, 'gt_receiver_coverage': 0.5, 'dataflow_score': 1.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 0 * * 6-7`, period=`5000`
- Output: cron=`0 0 * * 6-7`, period=`5000`

#### GT code
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {

    break

}

(#Pump).switch_toggle()
```

#### Output code
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {
    break
}

if ((#Pump).pump_pumpmode == "minimum") {
  (#Pump).pump_setpumpmode("normal")
} else {
  (#Pump).pump_setpumpmode("minimum")
}
```

#### Resolved services
```json
[
  {
    "device": "Clock",
    "service": "Weekday",
    "canonical_name": "Clock_Weekday",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "Clock",
    "service": "Weekday",
    "canonical_name": "Clock_Weekday",
    "args": [],
    "receiver": "(#Clock)"
  },
  {
    "device": "Pump",
    "service": "PumpMode",
    "canonical_name": "Pump_PumpMode",
    "args": [],
    "receiver": "(#Pump)"
  },
  {
    "device": "Pump",
    "service": "SetPumpMode",
    "canonical_name": "Pump_SetPumpMode",
    "args": [
      "\"normal\""
    ],
    "receiver": "(#Pump)"
  },
  {
    "device": "Pump",
    "service": "SetPumpMode",
    "canonical_name": "Pump_SetPumpMode",
    "args": [
      "\"minimum\""
    ],
    "receiver": "(#Pump)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.708893. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.5. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.5. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Clock", "service": "Weekday", "canonical_name": "Clock_Weekday", "args": [], "receiver": "(#Clock)"}, {"device": "Clock", "service": "Weekday", "canonical_name": "Clock_Weekday", "args": [], "receiver": "(#Clock)"}, {"device": "Pump", "service": "PumpMode", "canonical_name": "Pump_PumpMode", "args": [], "receiver": "(#Pump)"}, {"device": "Pump", "service": "SetPumpMode", "canonical_name": "Pump_SetPumpMode", "args": ["\"normal\""], "receiver": "(#Pump)"}, {"device": "Pump", "service
... <truncated>
- `precondition`: if/wait until guard 또는 state precondition이 GT와 다릅니다. 명령의 조건절을 action으로 바꾸거나, mode value를 state check로 오해했는지 확인해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.708893. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| precondition | 06 / Skeleton | strengthen_precondition_rule | Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 225 | category=7 | det_score=0.0

- command_eng: Measure the temperature every 15 minutes; turn on the air conditioner in cool mode if it's 25 degrees or higher, and turn it off if it's below 25 degrees.
- command_kor: 15분마다 온도를 측정해서 25도 이상이면 에어컨을 냉방 모드로 켜고, 25도 미만이면 꺼줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`900000`
- Output: cron=``, period=``

#### GT code
```
if ((#TemperatureSensor).temperaturesensor_temperature >= 25) {

    (#AirConditioner).airconditioner_setairconditionermode("cool")

} else {

    (#AirConditioner).switch_off()
}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 226 | category=7 | det_score=33.5203

- command_eng: Check every 5 minutes from 10 PM to 11 PM and turn it off when charging is complete.
- command_kor: 오후 10시부터 11시까지 5분마다 체크해서 충전이 완료되면 꺼줘.
- failure_reasons: `dataflow`, `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `precondition`, `semantic`

#### Concrete mismatch diagnostics
- Schedule mismatch: cron이 다릅니다. GT=`*/5 22 * * *` vs output=`0 22 * * *`.
- Schedule mismatch: period가 다릅니다. GT=`0` vs output=`300000`.
- Extraneous temporal guard: GT는 cron 필드로 시간 범위를 이미 표현하므로 output code 안의 `#Clock` 조건은 중복/불필요한 guard일 가능성이 큽니다.
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `charger_chargingstate`, `switch_off`.
- Missing condition: GT condition `((#Charger).charger_chargingstate == "fullyCharged"`에 대응되는 output condition을 찾지 못했습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `33.5203` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.304054` |
| `det_gt_service_coverage` | `0.0` |
| `det_gt_service_precision` | `0.0` |
| `det_gt_receiver_coverage` | `0.0` |
| `det_dataflow_score` | `0.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.304054, 'gt_service_coverage': 0.0, 'gt_service_precision': 0.0, 'gt_receiver_coverage': 0.0, 'dataflow_score': 0.0, 'numeric_grounding': 1.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`*/5 22 * * *`, period=`0`
- Output: cron=`0 22 * * *`, period=`300000`

#### GT code
```
if ((#Charger).charger_chargingstate == "fullyCharged") {

    (#Charger).switch_off()

}
```

#### Output code
```
if ((#Clock).clock_hour == 23) { break }
```

#### Resolved services
```json
[
  {
    "device": "Clock",
    "service": "Hour",
    "canonical_name": "Clock_Hour",
    "args": [],
    "receiver": "(#Clock)"
  }
]
```

#### Failure-label explanation
- `dataflow`: dataflow score=0.0. sensor read 값이 downstream condition/action/report에 GT와 같은 방식으로 전달되지 않았을 가능성이 있습니다.
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.304054. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.0. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.0. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "Clock", "service": "Hour", "canonical_name": "Clock_Hour", "args": [], "receiver": "(#Clock)"}]
- `precondition`: if/wait until guard 또는 state precondition이 GT와 다릅니다. 명령의 조건절을 action으로 바꾸거나, mode value를 state check로 오해했는지 확인해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.304054. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| dataflow | 06 / Dataflow | add_sensor_to_action_flow_rule | When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path. |
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| precondition | 06 / Skeleton | strengthen_precondition_rule | Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 230 | category=7 | det_score=69.9

- command_eng: Every hour from 6 PM to 8 PM, if someone is detected on the 1st floor, turn on all 1st floor lights.
- command_kor: 오후 6시부터 8시까지 1층에 사람이 감지되면 1층 불을 다 켜줘.
- failure_reasons: `extraneous`, `gt_mismatch`, `gt_receiver_coverage`, `gt_service_coverage`, `numeric_grounding`, `semantic`

#### Concrete mismatch diagnostics
- Schedule mismatch: cron이 다릅니다. GT=`0 18 * * *` vs output=`0 18-20 * * *`.
- Schedule mismatch: period가 다릅니다. GT=`100` vs output=`3600000`.
- Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `clock_hour`.
- Missing condition: GT condition `((#Clock).clock_hour >= 20`에 대응되는 output condition을 찾지 못했습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.696483` |
| `det_gt_service_coverage` | `0.666667` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `0.666667` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.833333` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.696483, 'gt_service_coverage': 0.666667, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 0.666667, 'dataflow_score': 1.0, 'numeric_grounding': 0.833333, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=`0 18 * * *`, period=`100`
- Output: cron=`0 18-20 * * *`, period=`3600000`

#### GT code
```
if ((#Clock).clock_hour >= 20) {

    break

}

if ((#Floor1 #PresenceSensor).presencesensor_presence == true) {

    all(#Floor1 #Light).switch_on()

}
```

#### Output code
```
if ((#Floor1 #PresenceSensor).presencesensor_presence == true) {
  all(#Floor1 #Light).switch_on()
}
```

#### Resolved services
```json
[
  {
    "device": "PresenceSensor",
    "service": "Presence",
    "canonical_name": "PresenceSensor_Presence",
    "args": [],
    "receiver": "(#Floor1 #PresenceSensor)"
  },
  {
    "device": "Switch",
    "service": "On",
    "canonical_name": "Switch_On",
    "args": [],
    "receiver": "all(#Floor1 #Light)"
  }
]
```

#### Failure-label explanation
- `extraneous`: output에 GT나 command가 요구하지 않은 read/action/wrapper가 포함되었을 수 있습니다.
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.696483. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `gt_receiver_coverage`: receiver coverage score=0.666667. GT가 요구한 location/group/device tag 일부가 output receiver에 충분히 반영되지 않았을 가능성이 큽니다.
- `gt_service_coverage`: service coverage score=0.666667. GT의 sensor/action service family 일부가 output에 빠졌거나 다른 service로 대체되었습니다. resolved_services=[{"device": "PresenceSensor", "service": "Presence", "canonical_name": "PresenceSensor_Presence", "args": [], "receiver": "(#Floor1 #PresenceSensor)"}, {"device": "Switch", "service": "On", "canonical_name": "Switch_On", "args": [], "receiver": "all(#Floor1 #Light)"}]
- `numeric_grounding`: cron 불일치: GT=`0 18 * * *` vs output=`0 18-20 * * *`; period 불일치: GT=`100` vs output=`3600000` cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.696483. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| extraneous | 03 / Minimality | strengthen_no_unrelated_action_rule | Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes. |
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| gt_receiver_coverage | 02 / Owner_Device_Rule | strengthen_owner_device_rule | Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target. |
| gt_service_coverage | 02 / Service_Mapping | add_schema_grounding_rule | Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 247 | category=8 | det_score=0.0

- command_eng: When the contact sensor is closed, sound the police siren every 10 seconds.
- command_kor: 접촉센서가 닫히면 10초마다 경찰 사이렌을 울려줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`10000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#ContactSensor).contactsensor_contact == true)

    active = 1

}

(#Siren).siren_setsirenmode("police")
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 248 | category=8 | det_score=0.0

- command_eng: Once the entrance door is opened, check the safe every 5 minutes and announce "The safe is open" through the speaker if it's not locked.
- command_kor: 현관문이 열리면 그 후부터 5분마다 금고를 체크해서 잠겨있지 않으면 스피커로 금고가 열려있다고 출력해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`300000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#Entrance #Door).door_doorstate == "open")

    active = 1

}

if ((#Safe).safe_safestate != "locked") {

    (#Speaker).speaker_speak("금고가 열려있습니다")

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 249 | category=8 | det_score=0.0

- command_eng: When a leak is detected, close the valve immediately and give a warning broadcast through the speaker every minute.
- command_kor: 누수가 감지되면 즉시 밸브를 잠그고 1분마다 스피커로 "누수가 감지되었습니다. 대피하세요"라고 출력해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`60000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#LeakSensor).leaksensor_leakage == true)

    (#Valve).valve_close()

    active = 1

}

(#Speaker).speaker_speak("누수가 감지되었습니다. 대피하세요")
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 251 | category=8 | det_score=0.0

- command_eng: At midnight, close the door and check the light every hour until 6 AM; if the brightness is greater than 30, lower it to 10.
- command_kor: 자정이 되면 문을 닫고, 오전 6시까지 한 시간마다 조명을 체크해서 밝기가 30보다 크면 10으로 낮춰줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=`0 0 * * *`, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    (#Door).door_close()

    active = 1

}

if ((#Clock).clock_hour == 6) {

    break

}

if ((#Light).lightsensor_brightness > 30) {

    (#Light).light_movetobrightness(10)

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 255 | category=8 | det_score=69.9

- command_eng: If motion is detected, capture an image every 10 seconds thereafter.
- command_kor: 움직임이 감지되면 그 뒤로 10초마다 사진을 찍어줘.
- failure_reasons: `gt_mismatch`, `numeric_grounding`, `semantic`

#### Concrete mismatch diagnostics
- Missing condition: GT condition `active == 0`에 대응되는 output condition을 찾지 못했습니다.
- Missing wait-until trigger: GT는 `wait until ((#MotionSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.750769` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.750769, 'gt_service_coverage': 1.0, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 1.0, 'dataflow_score': 1.0, 'numeric_grounding': 0.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`10000`
- Output: cron=``, period=`10000`

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#MotionSensor).motionsensor_motion == true)

    active = 1

}

(#Camera).camera_captureimage()
```

#### Output code
```
if ((#MotionSensor).motionsensor_motion == true) { (#Camera).camera_captureimage() }
```

#### Resolved services
```json
[
  {
    "device": "MotionSensor",
    "service": "Motion",
    "canonical_name": "MotionSensor_Motion",
    "args": [],
    "receiver": "(#MotionSensor)"
  },
  {
    "device": "Camera",
    "service": "CaptureImage",
    "canonical_name": "Camera_CaptureImage",
    "args": [],
    "receiver": "(#Camera)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.750769. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.750769. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 258 | category=8 | det_score=0.0

- command_eng: Whenever a light in the upper part is turned on, turn on a light in the lower part as well.
- command_kor: 상단부에 있는 조명이 켜질 때마다, 하단부에 있는 조명도 켜줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`100`
- Output: cron=``, period=``

#### GT code
```
prev := (#Top #Light).switch_switch

curr = (#Top #Light).switch_switch

if (prev == false and curr == true) {

    (#Bottom #Light).switch_on()

}

prev = curr
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 265 | category=8 | det_score=0.0

- command_eng: Whenever motion is detected at the entrance, turn on the entrance light at maximum brightness and then turn it off after 3 seconds.
- command_kor: 입구에 움직임이 감지될 때마다 입구 조명을 최대밝기로 켰다가 3초 뒤에 꺼줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`100`
- Output: cron=``, period=``

#### GT code
```
prev := (#Entrance #PresenceSensor).presencesensor_presence

curr = (#Entrance #PresenceSensor).presencesensor_presence

if (prev == false and curr == true) {

    (#Entrance #Light).levelcontrol_movetolevel(100, 0)

    delay(3 SEC)

    (#Entrance #Light).switch_off()

}

prev = curr
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 267 | category=8 | det_score=0.0

- command_eng: When the server rack humidity becomes higher than 70%, set the lab dehumidifier to dehumidifying mode and check the humidity every hour; turn it off if it's below 50%.
- command_kor: 서버 랙 습도가 70%보다 높아지면 연구실 제습기를 제습모드로 설정하고 1시간마다 습도를 다시 체크해서 50% 밑이면 제습기를 꺼줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#ServerRack #HumiditySensor).humiditysensor_humidity > 70)

    (#Lab #Dehumidifier).dehumidifier_setdehumidifiermode("dehumidifying")

    active = 1

}

if ((#ServerRack #HumiditySensor).humiditysensor_humidity < 50) {

    (#Lab #Dehumidifier).switch_off()

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 268 | category=8 | det_score=0.0

- command_eng: When the carbon dioxide level in the parking lot exceeds 880 ppm, speak "CO2 level danger" through the parking lot speaker every 10 seconds.
- command_kor: 주차장 이산화탄소 농도가 880ppm보다 높아지면, 10초마다 "CO2 농도 위험"이라고 주차장 스피커로 출력해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`10000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#ParkingLot #AirQualitySensor).airqualitysensor_carbondioxide > 880)

    active = 1

}

(#ParkingLot #Speaker).speaker_speak("CO2 농도 위험")
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 269 | category=8 | det_score=0.0

- command_eng: When smoke is detected in the living room, sound all fire alarms. Then, speak "Please evacuate" through the speaker every 10 seconds.
- command_kor: 거실에서 연기가 감지되면 모든 화재 경보를 울리고, 10초마다 스피커로 "대피하세요"라고 출력해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`10000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#LivingRoom #SmokeDetector).smokedetector_smoke == true)

    all(#Siren).siren_setsirenmode("fire")

    active = 1

}

(#Speaker).speaker_speak("대피하세요")
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 270 | category=8 | det_score=0.0

- command_eng: When any presence sensor on the 1st floor detects presence, sound all emergency sirens for 3 seconds every minute and then turn them off.
- command_kor: 1층에서 재실센서가 하나라도 감지되면, 1분마다 모든 긴급 사이렌을 3초간 울렸다 꺼줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`60000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until (all(#Floor1 #PresenceSensor).presencesensor_presence ==| true)

    active = 1

}

all(#Siren).siren_setsirenmode("emergency")

delay(3 SEC)

all(#Siren).switch_off()
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 271 | category=8 | det_score=69.9

- command_eng: When motion is detected in the lobby, capture an image of the lobby every 30 seconds.
- command_kor: 로비에서 움직임이 감지되면 30초마다 로비 사진을 찍어줘.
- failure_reasons: `gt_mismatch`, `numeric_grounding`, `semantic`

#### Concrete mismatch diagnostics
- Missing condition: GT condition `active == 0`에 대응되는 output condition을 찾지 못했습니다.
- Missing wait-until trigger: GT는 `wait until ((#Lobby #MotionSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `69.9` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.763229` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `0.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.763229, 'gt_service_coverage': 1.0, 'gt_service_precision': 1.0, 'gt_receiver_coverage': 1.0, 'dataflow_score': 1.0, 'numeric_grounding': 0.0, 'enum_grounding': 1.0, 'not_evaluated_reason': ''}` |

#### Schedule comparison

- GT: cron=``, period=`30000`
- Output: cron=``, period=`30000`

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#Lobby #MotionSensor).motionsensor_motion == true)

    active = 1

}

(#Lobby #Camera).camera_captureimage()
```

#### Output code
```
if ((#Lobby #MotionSensor).motionsensor_motion == true) {
  (#Lobby #Camera).camera_captureimage()
}
```

#### Resolved services
```json
[
  {
    "device": "MotionSensor",
    "service": "Motion",
    "canonical_name": "MotionSensor_Motion",
    "args": [],
    "receiver": "(#Lobby #MotionSensor)"
  },
  {
    "device": "Camera",
    "service": "CaptureImage",
    "canonical_name": "Camera_CaptureImage",
    "args": [],
    "receiver": "(#Lobby #Camera)"
  }
]
```

#### Failure-label explanation
- `gt_mismatch`: schema-valid하더라도 GT와 exact match가 아닙니다. gt_similarity=0.763229. receiver/service/temporal/numeric/enum/dataflow 중 하나 이상을 row-level로 비교해야 합니다.
- `numeric_grounding`: 시간/숫자/단위 literal이 GT 또는 descriptor 기준과 일부 다릅니다. cron/period와 service argument 단위를 먼저 내부적으로 결정한 뒤 final code를 생성하도록 Temporal_Rule을 강화해야 합니다.
- `semantic`: GT와 output의 high-level 동작 의미가 완전히 일치하지 않습니다. gt_similarity=0.763229. trigger, guard, repeat, delay, action order, state update 구조를 GT와 비교해야 합니다.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| gt_mismatch | 06 / DET_Helper | add_targeted_repair_hint | When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output. |
| numeric_grounding | 06 / Temporal_Rule | add_micro_rule | Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output. |
| semantic | 06 / Skeleton | strengthen_skeleton_rule | Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat. |

### Row 272 | category=8 | det_score=0.0

- command_eng: When smoke is detected by the kitchen smoke detector, speak "Fire outbreak" every 10 seconds through the living room speaker.
- command_kor: 주방의 연기 감지기로 연기가 감지가 되면 거실 스피커로 10초마다 "화재 발생"이라고 말해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`10000`
- Output: cron=``, period=``

#### GT code
```
active := 0

if (active == 0) {

    wait until ((#Kitchen #SmokeDetector).smokedetector_smoke == true)

    active = 1

}

(#LivingRoom #Speaker).speaker_speak("화재 발생")
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 273 | category=8 | det_score=0.0

- command_eng: Whenever the kitchen leak sensor detects a leak, start streaming with the kitchen camera.
- command_kor: 주방의 누수 센서가 감지될 때마다 주방 카메라로 스트리밍을 시작해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`100`
- Output: cron=``, period=``

#### GT code
```
prev := (#Kitchen #LeakSensor).leaksensor_leakage

curr = (#Kitchen #LeakSensor).leaksensor_leakage

if (prev == false and curr == true) {

    (#Kitchen #Camera).camera_startstream()
}

prev = curr
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 276 | category=8 | det_score=0.0

- command_eng: Repeat opening and closing the living room blind every hour.
- command_kor: 거실 블라인드를 1시간 간격으로 올렸다 내렸다 반복해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
open := false

if (open == false) {

    (#LivingRoom #Blind).windowcovering_uporopen()

    open = true

} else {

    (#LivingRoom #Blind).windowcovering_downorclose()

    open = false

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 277 | category=8 | det_score=0.0

- command_eng: Repeat opening and closing the bedroom window every 2 hours.
- command_kor: 안방 창문을 2시간마다 열었다 닫았다 반복해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`7200000`
- Output: cron=``, period=``

#### GT code
```
open := false

if (open == false) {

    (#Bedroom #Window).windowcovering_uporopen()

    open = true

} else {

    (#Bedroom #Window).windowcovering_downorclose()

    open = false

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 278 | category=8 | det_score=0.0

- command_eng: Every hour, alternate the air conditioner's target temperature between 25 and 20 degrees.
- command_kor: 회의실 에어컨의 목표 온도를 1시간마다 25와 20으로 번갈아 설정해줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`3600000`
- Output: cron=``, period=``

#### GT code
```
state := 0

if (state == 0) {

    (#MeetingRoom #AirConditioner).airconditioner_settargettemperature(25)

    state = 1

} else {

    (#MeetingRoom #AirConditioner).airconditioner_settargettemperature(20)

    state = 0

}
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

### Row 280 | category=8 | det_score=0.0

- command_eng: Whenever the meeting room door is opened, turn on the light at maximum brightness and then turn it off after 10 seconds.
- command_kor: 회의실 문이 열릴 때마다, 조명의 밝기를 최대밝기로 켰다가 10초뒤에 꺼줘.
- failure_reasons: `invalid_json.malformed_json`

#### Concrete mismatch diagnostics
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### DET component scores

| metric | value |
|---|---:|
| `det_score` | `0.0` |
| `det_pass` | `False` |
| `det_gt_exact` | `False` |
| `det_gt_similarity` | `0.0` |
| `det_gt_service_coverage` | `1.0` |
| `det_gt_service_precision` | `1.0` |
| `det_gt_receiver_coverage` | `1.0` |
| `det_dataflow_score` | `1.0` |
| `det_numeric_grounding` | `1.0` |
| `det_enum_grounding` | `1.0` |
| `component_score_policy` | `{'gt_similarity': 0.0, 'gt_service_coverage': None, 'gt_service_precision': None, 'gt_receiver_coverage': None, 'dataflow_score': None, 'numeric_grounding': None, 'enum_grounding': None, 'not_evaluated_reason': 'invalid_json.malformed_json'}` |

#### Schedule comparison

- GT: cron=``, period=`100`
- Output: cron=``, period=``

#### GT code
```
prev := (#MeetingRoom #Door).door_doorstate
 
curr = (#MeetingRoom #Door).door_doorstate

if (prev != "open" and curr == "open") {

    (#Light).levelcontrol_movetolevel(100, 0)

    delay(10 SEC)

    (#Light).switch_off()

}

prev = curr
```

#### Output code
```

```

#### Resolved services
```json
[]
```

#### Failure-label explanation
- Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.

#### Recommended prompt mutation
| failure | target block | mutation | micro-rule |
|---|---|---|---|
| invalid_json.malformed_json | 03 / Output_Schema | strict_parseable_json_rule | Return one parseable JSON object with required keys and no prose/markdown. |

