# Hybrid Strict DET + Cloud Semantic Judge Report

## 1. Summary
- total strict rows: 280
- joined cloud rows: 50
- strict-only rows: 230
- cloud-only rows: 0
- join quality: bad (duplicate_join_key)
- effective feedback mode: strict_only_fallback
- strict DET failed rows: 49
- mean strict_det_score: 85.705245
- mean overall_lang: None
- mean overall_gpt: None
- top failure reasons:
  - gt_mismatch: 135
  - semantic: 58
  - extraneous: 48
  - invalid_json: 25
  - numeric_grounding: 25
  - arg_type: 24
  - gt_receiver_coverage: 21
  - gt_service_coverage: 21
  - precondition: 12
  - enum_grounding: 7
- top recommended mutation blocks:
  - Service_Mapping: 31
  - Output_Schema: 25
  - DET_Helper: 24
  - Owner_Device_Rule: 21
  - Skeleton: 17
  - Minimality: 11
  - Temporal_Rule: 7
  - Enum_Grounding: 6
  - Dataflow: 3
- top root causes:
  - valid_json_nonempty: 255
  - invalid_json.malformed_json: 25

## 2. Failure reason × cloud judge correlation

| failure_reason | count | mean overall_lang | mean overall_gpt |
|---|---:|---:|---:|
| gt_mismatch | 135 | None | None |
| semantic | 58 | None | None |
| extraneous | 48 | None | None |
| numeric_grounding | 25 | None | None |
| invalid_json | 25 | None | None |
| arg_type | 24 | None | None |
| gt_receiver_coverage | 21 | None | None |
| gt_service_coverage | 21 | None | None |
| precondition | 12 | None | None |
| enum_grounding | 7 | None | None |
| service_match | 5 | None | None |
| unknown_service | 5 | None | None |
| dataflow | 3 | None | None |

- numeric_grounding ↔ ls_time_period mean: None
- unknown_service/service_match/gt_service_coverage ↔ ls_device_service mean: None
- semantic/gt_mismatch ↔ ls_semantic_intent mean: None
- semantic/gt_mismatch ↔ GPT mean: None
- gt_receiver_coverage ↔ conditions mean: None
- gt_receiver_coverage ↔ device_service mean: None

## 3. High-priority advisor rows

### Row 182 - high (1.0)
- command_eng: Every 30 minutes, if the temperature is 20 degrees or higher and below 30 degrees, set the air conditioner to auto mode; if it is 30 degrees or higher, set it to cool mode.
- command_kor: 30분마다 체크해서 온도가 20도 이상, 30도 미만이면 에어컨을 자동모드로 설정하고, 30도 이상이면 쿨모드로 설정해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
temp = (#TemperatureSensor).temperaturesensor_temperature

if (temp >= 20 and temp < 30) {

    (#AirConditioner).airconditioner_setairconditionermode("auto")

} else if (temp >= 30) {

    (#AirConditioner).airconditioner_setairconditionermode("cool")

}
```
- output code:
```

```

### Row 198 - high (1.0)
- command_eng: Check every 30 minutes; if the temperature is 30 degrees or higher, set the target temperature to 25 degrees; if it's below 23 degrees, set it to 26 degrees.
- command_kor: 30분마다 체크해서 온도가 30도 이상이면 목표 온도를 25도로 설정하고, 23도 미만이면 26도로 설정해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
temp = (#TemperatureSensor).temperaturesensor_temperature

if (temp >= 30) {

    (#AirConditioner).airconditioner_settargettemperature(25)

} else if (temp < 23) {

    (#AirConditioner).airconditioner_settargettemperature(26)

}
```
- output code:
```

```

### Row 199 - high (1.0)
- command_eng: Check humidity every 10 minutes; if it's 50 or higher, turn off the humidifier; if it's 20 or lower, turn on the humidifier and set it to auto mode.
- command_kor: 10분마다 습도를 체크해서 50 이상이면 가습기를 끄고 20 이하면 가습기를 켜고 자동모드로 설정해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
hum = (#HumiditySensor).humiditysensor_humidity

if (hum >= 50) {

    (#Humidifier).switch_off()

} else if (hum <= 20) {

    (#Humidifier).switch_on()

    (#Humidifier).humidifier_sethumidifiermode("auto")

}
```
- output code:
```

```

### Row 200 - high (1.0)
- command_eng: Check the fine dust level every hour; if it's 200 or higher, set the air purifier to high speed; if it's 100 or lower, set it to low speed.
- command_kor: 1시간마다 미세먼지 농도를 체크해서 200 이상이면 공기청정기를 강풍모드로 설정하고 100 이하이면 미풍모드로 설정해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
dust = (#AirQualitySensor).airqualitysensor_finedustlevel

if (dust >= 200) {

    (#AirPurifier).airpurifier_setairpurifiermode("high")

} else if (dust <= 100) {

    (#AirPurifier).airpurifier_setairpurifiermode("low")

}
```
- output code:
```

```

### Row 212 - high (1.0)
- command_eng: Check all door locks in Sector 1 every hour; if any one is open, change all lights in that sector to red.
- command_kor: 섹터1의 모든 도어락을 1시간마다 확인해서, 하나라도 열려 있으면 해당 섹터의 모든 조명을 빨간색으로 바꿔줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
if (all(#Sector1 #DoorLock).doorlock_doorlockstate ==| "open") {

    all(#Sector1 #Light).light_movetorgb(255, 0, 0)

}
```
- output code:
```

```

### Row 218 - high (1.0)
- command_eng: Every hour from midnight to 5 AM, if at least one door is open, turn all hallway lights to 50%.
- command_kor: 자정부터 오전 5시까지 1시간마다 체크해서 문이 하나라도 열려있으면, 복도의 조명을 모두 50%로 켜줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
if (all(#Door).door_doorstate ==| "open") {

    all(#Hallway #Light).levelcontrol_movetolevel(50, 0)

}
```
- output code:
```

```

### Row 219 - high (1.0)
- command_eng: If no motion is detected between 10 PM and 11 PM, lock all door locks.
- command_kor: 밤 10시부터 11시까지 움직임이 한번도 감지되지 않았으면, 모든 도어락을 잠궈줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
if ((#MotionSensor).motionsensor_motion == true) {

    break

}

if ((#Clock).clock_hour == 23) {

    all(#DoorLock).doorlock_lock()

    break

}
```
- output code:
```

```

### Row 223 - high (1.0)
- command_eng: Every 30 seconds from 10 PM to 11 PM, check for rain every 30 seconds; if it rains, close the window.
- command_kor: 오후 10시부터 11시까지 30초마다 비를 감지해서 비가 오면 창문을 닫아줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
if ((#Clock).clock_hour == 23) {

    break

}

if ((#RainSensor).rainsensor_rain == true) {

    (#Window).windowcovering_downorclose()

}
```
- output code:
```

```

### Row 225 - high (1.0)
- command_eng: Measure the temperature every 15 minutes; turn on the air conditioner in cool mode if it's 25 degrees or higher, and turn it off if it's below 25 degrees.
- command_kor: 15분마다 온도를 측정해서 25도 이상이면 에어컨을 냉방 모드로 켜고, 25도 미만이면 꺼줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
if ((#TemperatureSensor).temperaturesensor_temperature >= 25) {

    (#AirConditioner).airconditioner_setairconditionermode("cool")

} else {

    (#AirConditioner).switch_off()
}
```
- output code:
```

```

### Row 247 - high (1.0)
- command_eng: When the contact sensor is closed, sound the police siren every 10 seconds.
- command_kor: 접촉센서가 닫히면 10초마다 경찰 사이렌을 울려줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#ContactSensor).contactsensor_contact == true)

    active = 1

}

(#Siren).siren_setsirenmode("police")
```
- output code:
```

```

### Row 248 - high (1.0)
- command_eng: Once the entrance door is opened, check the safe every 5 minutes and announce "The safe is open" through the speaker if it's not locked.
- command_kor: 현관문이 열리면 그 후부터 5분마다 금고를 체크해서 잠겨있지 않으면 스피커로 금고가 열려있다고 출력해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 249 - high (1.0)
- command_eng: When a leak is detected, close the valve immediately and give a warning broadcast through the speaker every minute.
- command_kor: 누수가 감지되면 즉시 밸브를 잠그고 1분마다 스피커로 "누수가 감지되었습니다. 대피하세요"라고 출력해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#LeakSensor).leaksensor_leakage == true)

    (#Valve).valve_close()

    active = 1

}

(#Speaker).speaker_speak("누수가 감지되었습니다. 대피하세요")
```
- output code:
```

```

### Row 251 - high (1.0)
- command_eng: At midnight, close the door and check the light every hour until 6 AM; if the brightness is greater than 30, lower it to 10.
- command_kor: 자정이 되면 문을 닫고, 오전 6시까지 한 시간마다 조명을 체크해서 밝기가 30보다 크면 10으로 낮춰줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 258 - high (1.0)
- command_eng: Whenever a light in the upper part is turned on, turn on a light in the lower part as well.
- command_kor: 상단부에 있는 조명이 켜질 때마다, 하단부에 있는 조명도 켜줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
prev := (#Top #Light).switch_switch

curr = (#Top #Light).switch_switch

if (prev == false and curr == true) {

    (#Bottom #Light).switch_on()

}

prev = curr
```
- output code:
```

```

### Row 265 - high (1.0)
- command_eng: Whenever motion is detected at the entrance, turn on the entrance light at maximum brightness and then turn it off after 3 seconds.
- command_kor: 입구에 움직임이 감지될 때마다 입구 조명을 최대밝기로 켰다가 3초 뒤에 꺼줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 267 - high (1.0)
- command_eng: When the server rack humidity becomes higher than 70%, set the lab dehumidifier to dehumidifying mode and check the humidity every hour; turn it off if it's below 50%.
- command_kor: 서버 랙 습도가 70%보다 높아지면 연구실 제습기를 제습모드로 설정하고 1시간마다 습도를 다시 체크해서 50% 밑이면 제습기를 꺼줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 268 - high (1.0)
- command_eng: When the carbon dioxide level in the parking lot exceeds 880 ppm, speak "CO2 level danger" through the parking lot speaker every 10 seconds.
- command_kor: 주차장 이산화탄소 농도가 880ppm보다 높아지면, 10초마다 "CO2 농도 위험"이라고 주차장 스피커로 출력해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#ParkingLot #AirQualitySensor).airqualitysensor_carbondioxide > 880)

    active = 1

}

(#ParkingLot #Speaker).speaker_speak("CO2 농도 위험")
```
- output code:
```

```

### Row 269 - high (1.0)
- command_eng: When smoke is detected in the living room, sound all fire alarms. Then, speak "Please evacuate" through the speaker every 10 seconds.
- command_kor: 거실에서 연기가 감지되면 모든 화재 경보를 울리고, 10초마다 스피커로 "대피하세요"라고 출력해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#LivingRoom #SmokeDetector).smokedetector_smoke == true)

    all(#Siren).siren_setsirenmode("fire")

    active = 1

}

(#Speaker).speaker_speak("대피하세요")
```
- output code:
```

```

### Row 270 - high (1.0)
- command_eng: When any presence sensor on the 1st floor detects presence, sound all emergency sirens for 3 seconds every minute and then turn them off.
- command_kor: 1층에서 재실센서가 하나라도 감지되면, 1분마다 모든 긴급 사이렌을 3초간 울렸다 꺼줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 272 - high (1.0)
- command_eng: When smoke is detected by the kitchen smoke detector, speak "Fire outbreak" every 10 seconds through the living room speaker.
- command_kor: 주방의 연기 감지기로 연기가 감지가 되면 거실 스피커로 10초마다 "화재 발생"이라고 말해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#Kitchen #SmokeDetector).smokedetector_smoke == true)

    active = 1

}

(#LivingRoom #Speaker).speaker_speak("화재 발생")
```
- output code:
```

```

### Row 273 - high (1.0)
- command_eng: Whenever the kitchen leak sensor detects a leak, start streaming with the kitchen camera.
- command_kor: 주방의 누수 센서가 감지될 때마다 주방 카메라로 스트리밍을 시작해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
```
prev := (#Kitchen #LeakSensor).leaksensor_leakage

curr = (#Kitchen #LeakSensor).leaksensor_leakage

if (prev == false and curr == true) {

    (#Kitchen #Camera).camera_startstream()
}

prev = curr
```
- output code:
```

```

### Row 276 - high (1.0)
- command_eng: Repeat opening and closing the living room blind every hour.
- command_kor: 거실 블라인드를 1시간 간격으로 올렸다 내렸다 반복해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 277 - high (1.0)
- command_eng: Repeat opening and closing the bedroom window every 2 hours.
- command_kor: 안방 창문을 2시간마다 열었다 닫았다 반복해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 278 - high (1.0)
- command_eng: Every hour, alternate the air conditioner's target temperature between 25 and 20 degrees.
- command_kor: 회의실 에어컨의 목표 온도를 1시간마다 25와 20으로 번갈아 설정해줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 280 - high (1.0)
- command_eng: Whenever the meeting room door is opened, turn on the light at maximum brightness and then turn it off after 10 seconds.
- command_kor: 회의실 문이 열릴 때마다, 조명의 밝기를 최대밝기로 켰다가 10초뒤에 꺼줘.
- strict DET failure reasons: invalid_json
- concrete diagnostics:
  - Parse/schema failure: `invalid_json.malformed_json`. Inspect raw candidate and JSON contract before semantic GT-vs-output diagnostics.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Output_Schema: Return one parseable JSON object with required keys and no prose/markdown.
- GT code:
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
- output code:
```

```

### Row 226 - high (0.815077)
- command_eng: Check every 5 minutes from 10 PM to 11 PM and turn it off when charging is complete.
- command_kor: 오후 10시부터 11시까지 5분마다 체크해서 충전이 완료되면 꺼줘.
- strict DET failure reasons: dataflow, extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, precondition, semantic
- concrete diagnostics:
  - Schedule mismatch: cron이 다릅니다. GT=`*/5 22 * * *` vs output=`0 22 * * *`.
  - Schedule mismatch: period가 다릅니다. GT=`0` vs output=`300000`.
  - Extraneous temporal guard: GT는 cron 필드로 시간 범위를 이미 표현하므로 output code 안의 `#Clock` 조건은 중복/불필요한 guard일 가능성이 큽니다.
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `charger_chargingstate`, `switch_off`.
  - Missing condition: GT condition `((#Charger).charger_chargingstate == "fullyCharged"`에 대응되는 output condition을 찾지 못했습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Dataflow: When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path.
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Charger).charger_chargingstate == "fullyCharged") {

    (#Charger).switch_off()

}
```
- output code:
```
if ((#Clock).clock_hour == 23) { break }
```

### Row 190 - medium (0.659368)
- command_eng: On weekdays at 7 AM, start the rice cooker in auto-cleaning mode.
- command_kor: 평일 오전 7시에 밥솥을 자동청소 모드로 작동해줘.
- strict DET failure reasons: enum_grounding, gt_mismatch, gt_receiver_coverage, gt_service_coverage, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Enum_Grounding: For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
(#RiceCooker).ricecooker_setricecookermode("autoClean")
```
- output code:
```
(#RiceCooker).ricecooker_setcookingparameters("autoClean", 0)
```

### Row 185 - medium (0.65026)
- command_eng: Set the rice cooker to reheating mode every morning at 7 AM.
- command_kor: 매일 아침 7시에 밥솥을 재가열 모드로 설정해줘.
- strict DET failure reasons: enum_grounding, gt_mismatch, gt_receiver_coverage, gt_service_coverage, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Enum_Grounding: For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
(#RiceCooker).ricecooker_setricecookermode("reheating")
```
- output code:
```
(#RiceCooker).ricecooker_setcookingparameters("reheating", 0)
```

### Row 71 - medium (0.621126)
- command_eng: If the laundry dryer is in low noise mode, switch it to quick mode.
- command_kor: 건조기가 저소음 모드이면, 퀵 모드로 바꿔줘.
- strict DET failure reasons: arg_type, dataflow, enum_grounding, gt_mismatch, gt_receiver_coverage, gt_service_coverage, service_match, unknown_service:laundrydryer_setlaundrydryermodemode
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `laundrydryer_setlaundrydryermode`.
  - Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `laundrydryer_setlaundrydryermodemode`.
  - Unknown service detail: `laundrydryer_setlaundrydryermodemode`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `laundrydryer_setlaundrydryermode`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Enum_Grounding: For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema.
  - Dataflow: When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path.
  - Enum_Grounding: For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Service_Mapping: Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.
  - Service_Mapping: Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.
- GT code:
```
if ((#LaundryDryer).laundrydryer_laundrydryermode == "lownoise") {

    (#LaundryDryer).laundrydryer_setlaundrydryermode("quick")

}
```
- output code:
```
if ((#LaundryDryer).laundrydryer_laundrydryermode == "lownoise") {
  (#LaundryDryer).laundrydryer_setlaundrydryermodemode("quick")
}
```

### Row 98 - medium (0.532548)
- command_eng: When the button is pushed 3 times, open the valve.
- command_kor: 버튼이 세번 눌리면 벨브를 열어줘.
- strict DET failure reasons: dataflow, gt_mismatch, gt_receiver_coverage, gt_service_coverage, numeric_grounding
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `button_button`.
  - Missing condition: GT condition `((#Button).button_button == "pushed_3x"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `DimmerSwitch_Button1 == "pushed_3x"`가 추가되었습니다.
  - Missing wait-until trigger: GT는 `wait until ((#Button)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Dataflow: When reading a value for reporting or control, bind it to a variable and use that variable in the downstream condition or action instead of re-inventing a separate value path.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
- GT code:
```
wait until ((#Button).button_button == "pushed_3x")

(#Valve).valve_open()
```
- output code:
```
if ((#DimmerSwitch_Button1 == "pushed_3x")) {
  (#Valve).valve_open()
}
```

### Row 224 - medium (0.531336)
- command_eng: Every 5 seconds on weekends, if the pump is off, turn it on; if it is on, turn it off.
- command_kor: 주말에 5초마다 체크해서 펌프가 꺼져 있으면 켜고, 켜져 있으면 꺼줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, precondition, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_toggle`.
  - Condition mismatch: `(#Clock).clock_weekday` 비교식이 다릅니다 (value GT `"sunday"` vs output `"saturday"`). GT condition `(#Clock).clock_weekday != "sunday"` vs output condition `((#Clock).clock_weekday != "saturday"`.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `((#Pump).pump_pumpmode == "minimum"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {

    break

}

(#Pump).switch_toggle()
```
- output code:
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

### Row 76 - medium (0.521239)
- command_eng: If face recognition at the entrance is off, start it.
- command_kor: 입구의 얼굴 인식이 꺼져있으면, 얼굴 인식을 시작해줘
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, precondition, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `facerecognizer_start`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Entrance #FaceRecognizer).switch_switch == false) {

    (#Entrance #FaceRecognizer).facerecognizer_start()

}
```
- output code:
```
if ((#Entrance #FaceRecognizer).switch_switch == false) { (#Entrance #FaceRecognizer).switch_on() }
```

### Row 215 - medium (0.520779)
- command_eng: Every 30 minutes during weekends, check all pumps in the factory; if any one is turned on, turn off all pumps and send an email to "test@example.com" with the subject 'Risk' and message 'A pump is turned on'.
- command_kor: 주말 동안 공장의 모든 펌프를 30분마다 확인해서, 켜진 펌프가 하나라도 있으면 모두 꺼주고 "test@example.com"에게 "위험" 제목으로 "펌프가 켜졌습니다"라는 내용의 메일 보내줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, precondition, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_off`, `switch_switch`.
  - Condition mismatch: `(#Clock).clock_weekday` 비교식이 다릅니다 (value GT `"sunday"` vs output `"saturday"`). GT condition `(#Clock).clock_weekday != "sunday"` vs output condition `((#Clock).clock_weekday != "saturday"`.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `(all(#Factory #Pump).pump_pumpmode != "normal"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Represent explicit state preconditions as guard conditions before the action; do not infer state from unrelated mode values or replace a state check with an action.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {

    break

}

if (all(#Factory #Pump).switch_switch ==| true) {

    all(#Factory #Pump).switch_off()

    (#EmailProvider).emailprovider_sendmail("test@example.com", "위험", "펌프가 켜졌습니다")

}
```
- output code:
```
if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {
    break
}

if (all(#Factory #Pump).pump_pumpmode != "normal") {
  all(#Factory #Pump).pump_setpumpmode("normal")
  (#EmailProvider).emailprovider_sendmail("test@example.com", "Risk", "A pump is turned on")
}
```

### Row 194 - medium (0.513329)
- command_eng: Every 30 minutes from 7 PM to 10 PM, check the robot vacuum cleaner and start it in auto mode if it is stopped.
- command_kor: 저녁 7시부터 10시까지 30분마다 로봇청소기를 체크해서 멈춰있으면 자동 모드로 실행시켜줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, semantic, service_match, unknown_service:robotvacuumcleaner_robotvacuumcleanermodemode
- concrete diagnostics:
  - Schedule mismatch: cron이 다릅니다. GT=`0,30 19-21 * * *` vs output=`0 19-22 * * *`.
  - Schedule mismatch: period가 다릅니다. GT=`0` vs output=`1800000`.
  - Extraneous temporal guard: GT는 cron 필드로 시간 범위를 이미 표현하므로 output code 안의 `#Clock` 조건은 중복/불필요한 guard일 가능성이 큽니다.
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `robotvacuumcleaner_robotvacuumcleanermode`.
  - Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `robotvacuumcleaner_robotvacuumcleanermodemode`.
  - Unknown service detail: `robotvacuumcleaner_robotvacuumcleanermodemode`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `robotvacuumcleaner_setrobotvacuumcleanermodemode`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
  - Missing condition: GT condition `((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermode == "stop"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermodemode == "stop"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
  - Service_Mapping: Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.
  - Service_Mapping: Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.
- GT code:
```
if ((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermode == "stop") {

    (#RobotVacuumCleaner).robotvacuumcleaner_setrobotvacuumcleanermodemode("auto")

}
```
- output code:
```
if ((#Clock).clock_hour >= 19 and (#Clock).clock_hour < 22) {
  if ((#RobotVacuumCleaner).robotvacuumcleaner_robotvacuumcleanermodemode == "stop") {
    (#RobotVacuumCleaner).robotvacuumcleaner_setrobotvacuumcleanermodemode("auto")
  }
} else {
  break
}
```

### Row 13 - medium (0.50585)
- command_eng: Announce the fine dust level through the speaker.
- command_kor: 미세먼지 농도를 스피커로 알려줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `airqualitysensor_dustlevel`.
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
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
- GT code:
```
dust = (#AirQualitySensor).airqualitysensor_dustlevel

(#Speaker).speaker_speak("미세먼지 농도는 " + dust + "입니다")
```
- output code:
```
fine_dust_level = (#WeatherProvider).weatherprovider_pm10weather
(#Speaker).speaker_speak(fine_dust_level)
```

### Row 15 - medium (0.50585)
- command_eng: Generate a cat image using cloud service and save it as "cat.png".
- command_kor: 클라우드로 고양이 사진을 생성하고 "cat.png"로 저장해줘.
- strict DET failure reasons: arg_type, gt_mismatch, gt_receiver_coverage, gt_service_coverage, service_match, unknown_service:cloudserviceprovider_savefile
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `cloudserviceprovider_savetofile`.
  - Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `cloudserviceprovider_savefile`.
  - Unknown service detail: `cloudserviceprovider_savefile`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `cloudserviceprovider_savetofile`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
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
  - Enum_Grounding: For ENUM arguments, copy one allowed enum value exactly; for numeric arguments, use unquoted numeric literals; preserve positional argument order and separator required by the schema.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Service_Mapping: Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.
  - Service_Mapping: Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.
- GT code:
```
img = (#CloudServiceProvider).cloudserviceprovider_generateimage("Generate a cat image")

(#CloudServiceProvider).cloudserviceprovider_savetofile(img, "cat.png")
```
- output code:
```
(#CloudServiceProvider).cloudserviceprovider_generateimage("cat")
(#CloudServiceProvider).cloudserviceprovider_savefile("cat.png")
```

### Row 65 - medium (0.50585)
- command_eng: If the rice cooker is on keep-warm mode, switch it to cooking mode.
- command_kor: 밥솥이 보온 모드이면, 조리 모드로 변경해줘.
- strict DET failure reasons: enum_grounding, gt_mismatch, gt_receiver_coverage, gt_service_coverage
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `ricecooker_setricecookermode`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Enum_Grounding: For enum-valued services, copy the allowed enum value exactly from the selected service descriptor and do not paraphrase it.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
- GT code:
```
if ((#RiceCooker).ricecooker_ricecookermode == "keepWarm") {

    (#RiceCooker).ricecooker_setricecookermode("cooking")

}
```
- output code:
```
if ((#RiceCooker).ricecooker_ricecookermode == "keepWarm") {
  (#RiceCooker).ricecooker_setcookingparameters("cooking", 0)
}
```

### Row 74 - medium (0.50585)
- command_eng: If the button is in the pushed state, raise the blind.
- command_kor: 버튼이 눌려진 상태면, 블라인드를 올려줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, semantic
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `button_button`.
  - Missing condition: GT condition `((#Button).button_button == "pushed"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `((#DimmerSwitch).dimmerswitch_button1 == "pushed"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Button).button_button == "pushed") {

    (#Blind).windowcovering_uporopen()

}
```
- output code:
```
if ((#DimmerSwitch).dimmerswitch_button1 == "pushed") {
  (#Blind).windowcovering_uporopen()
}
```

### Row 107 - medium (0.50585)
- command_eng: When motion is detected in the bedroom, turn on the bedroom air conditioner.
- command_kor: 침실에 움직임이 감지되면 침실 에어컨을 켜줘.
- strict DET failure reasons: gt_mismatch, gt_receiver_coverage, gt_service_coverage
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
- GT code:
```
wait until ((#Bedroom #MotionSensor).motionsensor_motion == true)

(#Bedroom #AirConditioner).switch_on()
```
- output code:
```
wait until ((#Bedroom #MotionSensor).motionsensor_motion == true)
(#Bedroom #AirConditioner).airconditioner_setairconditionermode("auto")
```

### Row 129 - medium (0.50585)
- command_eng: When it rains, close the door and check again after 1 hour; if it's not raining then, open the door again.
- command_kor: 비가 오면 문을 닫고 1시간 뒤에 체크해서 비가 안오면 문을 다시 열어줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `weatherprovider_weather`.
  - Missing condition: GT condition `((#WeatherProvider).weatherprovider_weather != "rain"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `((#RainSensor).rainsensor_rain == false`가 추가되었습니다.
  - Missing wait-until trigger: GT는 `wait until ((#RainSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
- GT code:
```
wait until ((#RainSensor).rainsensor_rain == true)

(#Door).door_close()
delay(1 HOUR)

if ((#WeatherProvider).weatherprovider_weather != "rain") {

    (#Door).door_open()

}
```
- output code:
```
if ((#RainSensor).rainsensor_rain == true) {
  (#Door).door_close()
  delay(1 HOUR)
  if ((#RainSensor).rainsensor_rain == false) {
    (#Door).door_open()
  }
}
```

### Row 156 - medium (0.50585)
- command_eng: If the fine dust level is 150 or higher and the door is open, close the door and set the air purifier to high.
- command_kor: 미세먼지 농도가 150 이상이고 문이 열려 있으면, 문을 닫고 공기청정기를 강풍으로 작동시켜줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, numeric_grounding
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `airqualitysensor_finedustlevel`.
  - Missing condition: GT condition `((#AirQualitySensor).airqualitysensor_finedustlevel >= 150`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `((#WeatherProvider).weatherprovider_pm10weather >= 150`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
- GT code:
```
if ((#AirQualitySensor).airqualitysensor_finedustlevel >= 150 and (#Door).door_doorstate == "open") {

    (#Door).door_close()

    (#AirPurifier).airpurifier_setairpurifiermode("high")

}
```
- output code:
```
if ((#WeatherProvider).weatherprovider_pm10weather >= 150 and (#Door).door_doorstate == "open") {
  (#Door).door_close()
  (#AirPurifier).airpurifier_setairpurifiermode("high")
}
```

### Row 167 - medium (0.50585)
- command_eng: If the bedroom temperature is 26 degrees or higher and the bedroom window is open, close the window and turn on the air conditioner.
- command_kor: 안방의 온도가 26도 이상이고 창문이 열려 있으면, 창문을 닫고 에어컨을 켜줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, numeric_grounding
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
- GT code:
```
if ((#Bedroom #TemperatureSensor).temperaturesensor_temperature >= 26 and (#Bedroom #Window).armrobot_currentposition > 0) {

    (#Bedroom #Window).windowcovering_downorclose()

    (#Bedroom #AirConditioner).switch_on()

}
```
- output code:
```
if ((#Bedroom #TemperatureSensor).temperaturesensor_temperature >= 26 and (#Bedroom #Window).armrobot_currentposition > 0) {
  (#Bedroom #Window).windowcovering_downorclose()
  (#Bedroom #AirConditioner).airconditioner_setairconditionermode("cool")
  (#Bedroom #AirConditioner).airconditioner_settargettemperature(26)
}
```

### Row 176 - medium (0.50585)
- command_eng: If the wine cellar temperature is 15 degrees or higher and humidity is 60% or higher, turn on the air conditioner and turn off the humidifier.
- command_kor: 와인 셀러 온도가 15도 이상이고 습도가 60% 이상이면, 에어컨을 켜고 가습기를 꺼줘.
- strict DET failure reasons: gt_mismatch, gt_receiver_coverage, gt_service_coverage
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `switch_on`.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
- GT code:
```
if ((#WineCellar #TemperatureSensor).temperaturesensor_temperature >= 15 and (#WineCellar #HumiditySensor).humiditysensor_humidity >= 60) {

    (#AirConditioner).switch_on()

    (#Humidifier).switch_off()

}
```
- output code:
```
if ((#WineCellar #TemperatureSensor).temperaturesensor_temperature >= 15 and (#WineCellar #HumiditySensor).humiditysensor_humidity >= 60) {
  (#WineCellar #AirConditioner).airconditioner_setairconditionermode("cool")
  (#WineCellar #Humidifier).switch_off()
}
```

### Row 193 - medium (0.50585)
- command_eng: Every Monday at 8 AM, if both the safe and the door lock are locked, say 'It is safe' through the speaker
- command_kor: 월요일 아침 8시마다 금고와 도어락이 모두 잠겨있으면 스피커로 "안전합니다"라고 말해줘.
- strict DET failure reasons: gt_mismatch, gt_receiver_coverage, gt_service_coverage, semantic, service_match, unknown_service:doorlock_lockstate
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `doorlock_doorlockstate`.
  - Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `doorlock_lockstate`.
  - Unknown service detail: `doorlock_lockstate`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `doorlock_doorlockstate`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
  - Condition mismatch: `((#Safe).safe_safestate` 비교식이 다릅니다 (value GT `"locked"` vs output `"closed"`). GT condition `((#Safe).safe_safestate == "locked"` vs output condition `((#Safe).safe_safestate == "closed"`.
  - Missing condition: GT condition `(#DoorLock).doorlock_doorlockstate == "locked"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `(#DoorLock).doorlock_lockstate == "locked"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
  - Service_Mapping: Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.
  - Service_Mapping: Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.
- GT code:
```
if ((#Safe).safe_safestate == "locked" and (#DoorLock).doorlock_doorlockstate == "locked") {

    (#Speaker).speaker_speak("안전합니다")

}
```
- output code:
```
if ((#Safe).safe_safestate == "closed" and (#DoorLock).doorlock_lockstate == "locked") {
  (#Speaker).speaker_speak("안전합니다")
}
```

### Row 197 - medium (0.50585)
- command_eng: At 11 PM, if safe is unlocked or the door lock is unlocked , speak 'Check the safe and door lock' through the speaker.
- command_kor: 오후 11시에 금고가 열려있거나 도어락이 열려있으면, 스피커로 "금고와 도어락을 확인하세요"라고 말해줘.
- strict DET failure reasons: gt_mismatch, gt_receiver_coverage, gt_service_coverage, service_match, unknown_service:doorlock_lockstate
- concrete diagnostics:
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `doorlock_doorlockstate`.
  - Extra or substituted service/member: output에는 있으나 GT/resolved services와 직접 대응되지 않는 member가 있습니다: `doorlock_lockstate`.
  - Unknown service detail: `doorlock_lockstate`는 schema에 없는 member입니다. 가장 가까운 GT/resolved 후보는 `doorlock_doorlockstate`입니다. 이름을 합성하지 말고 schema의 canonical member를 그대로 사용해야 합니다.
  - Condition mismatch: `((#Safe).safe_safestate` 비교식이 다릅니다 (value GT `"unlocked"` vs output `"open"`). GT condition `((#Safe).safe_safestate == "unlocked"` vs output condition `((#Safe).safe_safestate == "open"`.
  - Missing condition: GT condition `(#DoorLock).doorlock_doorlockstate == "unlocked"`에 대응되는 output condition을 찾지 못했습니다.
  - Extra condition: output에 GT에서 요구하지 않은 조건 `(#DoorLock).doorlock_lockstate == "open"`가 추가되었습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Service_Mapping: Do not invent service/value names; choose only functions and values present in the injected service list and use the canonical device-prefixed service identifier.
  - Service_Mapping: Before emitting a service member, verify that it appears in the current service schema; if not, select the nearest valid canonical service from the injected service list.
- GT code:
```
if ((#Safe).safe_safestate == "unlocked" or (#DoorLock).doorlock_doorlockstate == "unlocked") {

    (#Speaker).speaker_speak("금고와 도어락의 잠금 상태를 확인해 주세요.")

}
```
- output code:
```
if ((#Safe).safe_safestate == "open" or (#DoorLock).doorlock_lockstate == "open") {
  (#Speaker).speaker_speak("Check the safe and door lock")
}
```

### Row 214 - medium (0.50585)
- command_eng: Every 8 AM, open all blinds with odd tags, and at 9 AM, open all blinds with even tags.
- command_kor: 아침 8시에 홀수 태그가 붙은 블라인드를 모두 열어주고, 9시에는 짝수 태그가 붙은 모든 블라인드를 열어줘.
- strict DET failure reasons: gt_mismatch, numeric_grounding, semantic
- concrete diagnostics:
  - Delay mismatch: GT delay=['1 HOUR'] vs output delay=[].
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
all(#Odd #Blind).windowcovering_uporopen()

delay(1 HOUR)

all(#Even #Blind).windowcovering_uporopen()
```
- output code:
```
all(#Odd #Even #Blind).windowcovering_uporopen()
```

### Row 230 - medium (0.50585)
- command_eng: Every hour from 6 PM to 8 PM, if someone is detected on the 1st floor, turn on all 1st floor lights.
- command_kor: 오후 6시부터 8시까지 1층에 사람이 감지되면 1층 불을 다 켜줘.
- strict DET failure reasons: extraneous, gt_mismatch, gt_receiver_coverage, gt_service_coverage, numeric_grounding, semantic
- concrete diagnostics:
  - Schedule mismatch: cron이 다릅니다. GT=`0 18 * * *` vs output=`0 18-20 * * *`.
  - Schedule mismatch: period가 다릅니다. GT=`100` vs output=`3600000`.
  - Missing GT service/member: GT에는 있지만 output/resolved services에서 확인되지 않은 member가 있습니다: `clock_hour`.
  - Missing condition: GT condition `((#Clock).clock_hour >= 20`에 대응되는 output condition을 찾지 못했습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - Minimality: Emit only actions and reads required by the command; remove unrelated reads, duplicate actions, invented wrappers, and unnecessary state changes.
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Owner_Device_Rule: Preserve every command-implied device, owner, location, group, sector, and selector tag in the receiver expression unless the command explicitly broadens the target.
  - Service_Mapping: Include every service family implied by the command, including both sensor reads and actuator actions; do not substitute a semantically adjacent service unless the schema requires it.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
if ((#Clock).clock_hour >= 20) {

    break

}

if ((#Floor1 #PresenceSensor).presencesensor_presence == true) {

    all(#Floor1 #Light).switch_on()

}
```
- output code:
```
if ((#Floor1 #PresenceSensor).presencesensor_presence == true) {
  all(#Floor1 #Light).switch_on()
}
```

### Row 255 - medium (0.50585)
- command_eng: If motion is detected, capture an image every 10 seconds thereafter.
- command_kor: 움직임이 감지되면 그 뒤로 10초마다 사진을 찍어줘.
- strict DET failure reasons: gt_mismatch, numeric_grounding, semantic
- concrete diagnostics:
  - Missing condition: GT condition `active == 0`에 대응되는 output condition을 찾지 못했습니다.
  - Missing wait-until trigger: GT는 `wait until ((#MotionSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#MotionSensor).motionsensor_motion == true)

    active = 1

}

(#Camera).camera_captureimage()
```
- output code:
```
if ((#MotionSensor).motionsensor_motion == true) { (#Camera).camera_captureimage() }
```

### Row 271 - medium (0.50585)
- command_eng: When motion is detected in the lobby, capture an image of the lobby every 30 seconds.
- command_kor: 로비에서 움직임이 감지되면 30초마다 로비 사진을 찍어줘.
- strict DET failure reasons: gt_mismatch, numeric_grounding, semantic
- concrete diagnostics:
  - Missing condition: GT condition `active == 0`에 대응되는 output condition을 찾지 못했습니다.
  - Missing wait-until trigger: GT는 `wait until ((#Lobby #MotionSensor)` 구조를 사용하지만 output에는 대응 wait-until이 없습니다.
- Lang judge scores/rationales:
  - overall_lang: None
  - semantic_intent: None
  - conditions: None
  - time_period: None
  - device_service: None
  - reasoning: ""
- GPT judge:
  - overall_gpt: None
  - reasoning: 
- recommended prompt mutation block/micro-rule:
  - DET_Helper: When the code is schema-valid but not target-equivalent, compare receiver coverage, service coverage, temporal structure, dataflow, numeric units, and enum grounding before final output.
  - Temporal_Rule: Before final JOILang generation, internally derive a temporal and numeric plan: determine cron first when a scheduled trigger exists, determine period only for repeated monitoring loops, convert units using the service descriptor, and do not expose the internal plan in the final output.
  - Skeleton: Choose the JOILang skeleton by first classifying the command as one-shot, condition-action, edge-trigger, cron schedule, period loop, or trigger-then-repeat.
- GT code:
```
active := 0

if (active == 0) {

    wait until ((#Lobby #MotionSensor).motionsensor_motion == true)

    active = 1

}

(#Lobby #Camera).camera_captureimage()
```
- output code:
```
if ((#Lobby #MotionSensor).motionsensor_motion == true) {
  (#Lobby #Camera).camera_captureimage()
}
```
