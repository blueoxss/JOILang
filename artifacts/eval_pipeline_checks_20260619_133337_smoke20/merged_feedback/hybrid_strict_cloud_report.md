# Hybrid Strict DET + Cloud Semantic Judge Report

## 1. Summary
- total strict rows: 20
- joined cloud rows: 20
- strict-only rows: 0
- cloud-only rows: 0
- join quality: good (row_no_match)
- effective feedback mode: hybrid
- strict DET failed rows: 2
- mean strict_det_score: 96.685305
- mean overall_lang: None
- mean overall_gpt: None
- top failure reasons:
  - gt_mismatch: 5
  - gt_receiver_coverage: 2
  - gt_service_coverage: 2
  - arg_type: 1
  - extraneous: 1
  - service_match: 1
  - unknown_service:cloudserviceprovider_savefile: 1
- top recommended mutation blocks:
  - Service_Mapping: 4
  - DET_Helper: 2
  - Owner_Device_Rule: 2
  - Minimality: 1
  - Enum_Grounding: 1
- top root causes:
  - valid_json_nonempty: 20

## 2. Failure reason × cloud judge correlation

| failure_reason | count | mean overall_lang | mean overall_gpt |
|---|---:|---:|---:|
| gt_mismatch | 5 | None | None |
| gt_receiver_coverage | 2 | None | None |
| gt_service_coverage | 2 | None | None |
| extraneous | 1 | None | None |
| arg_type | 1 | None | None |
| service_match | 1 | None | None |
| unknown_service | 1 | None | None |

- numeric_grounding ↔ ls_time_period mean: None
- unknown_service/service_match/gt_service_coverage ↔ ls_device_service mean: None
- semantic/gt_mismatch ↔ ls_semantic_intent mean: None
- semantic/gt_mismatch ↔ GPT mean: None
- gt_receiver_coverage ↔ conditions mean: None
- gt_receiver_coverage ↔ device_service mean: None

## 3. High-priority advisor rows

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

### Row 18 - low (0.020828)
- command_eng: Tell me the lunch menu for Building 301 today through the speaker.
- command_kor: 오늘의 301동 점심 메뉴를 스피커로 알려줘.
- strict DET failure reasons: gt_mismatch
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
menu = (#MenuProvider).menuprovider_getmenu("오늘 301동식당 점심")

(#Speaker).speaker_speak("오늘의 메뉴는 " + menu + "입니다")
```
- output code:
```
menu = (#MenuProvider).menuprovider_getmenu("오늘 301동식당 점심")
(#Speaker).speaker_speak(menu)
```

### Row 19 - low (0.018236)
- command_eng: Ask the cloud AI what an LLM is, and output its answer through the speaker.
- command_kor: 클라우드 AI한테 llm이 무엇인지 질문하고 답을 스피커로 출력해줘.
- strict DET failure reasons: gt_mismatch
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
answer = (#CloudServiceProvider).cloudserviceprovider_chatwithai("What is LLM?")

(#Speaker).speaker_speak(answer)
```
- output code:
```
llm_description = (#CloudServiceProvider).cloudserviceprovider_chatwithai("What is an LLM?")
(#Speaker).speaker_speak(llm_description)
```

### Row 10 - low (0.012735)
- command_eng: Tell me the current humidity through the speaker.
- command_kor: 현재 습도를 스피커로 말해줘.
- strict DET failure reasons: gt_mismatch
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
hum = (#HumiditySensor).humiditysensor_humidity

(#Speaker).speaker_speak("현재 습도는 " + hum + "%입니다")
```
- output code:
```
humidity = (#AirQualitySensor).airqualitysensor_humidity
(#Speaker).speaker_speak(humidity)
```

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

### Row 3 - low (0.0)
- command_eng: Start the rice cooker on cooking mode for 30 minutes.
- command_kor: 밥솥을 조리 모드로 30분 작동시켜.
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
(#RiceCooker).ricecooker_setcookingparameters("cooking", 1800)
```
- output code:
```
(#RiceCooker).ricecooker_setcookingparameters("cooking", 1800)
```

### Row 4 - low (0.0)
- command_eng: Set the siren to emergency mode.
- command_kor: 사이렌을 응급모드로 울려줘.
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
(#Siren).siren_setsirenmode("emergency")
```
- output code:
```
(#Siren).siren_setsirenmode("emergency")
```

### Row 5 - low (0.0)
- command_eng: Set the speaker volume to 30.
- command_kor: 스피커의 볼륨을 30으로 설정해줘.
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
(#Speaker).speaker_setvolume(30)
```
- output code:
```
(#Speaker).speaker_setvolume(30)
```

### Row 6 - low (0.0)
- command_eng: Turn the TV channel down by one.
- command_kor: TV 채널을 하나 내려줘.
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
(#Television).television_channeldown()
```
- output code:
```
(#Television).television_channeldown()
```

### Row 7 - low (0.0)
- command_eng: Switch the TV to channel 7.
- command_kor: TV로 7번 채널을 틀어줘.
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
(#Television).television_setchannel(7)
```
- output code:
```
(#Television).television_setchannel(7)
```

### Row 8 - low (0.0)
- command_eng: Announce the temperature through the speaker.
- command_kor: 현재 온도를 스피커로 알려줘.
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
temp = (#TemperatureSensor).temperaturesensor_temperature

(#Speaker).speaker_speak("현재 온도는 " + temp + "도입니다")
```
- output code:
```
temp = (#TemperatureSensor).temperaturesensor_temperature
(#Speaker).speaker_speak("현재 온도는 " + temp + "°C 입니다")
```

### Row 9 - low (0.0)
- command_eng: Tell me the outdoor temperature through the speaker.
- command_kor: 외부 온도를 스피커로 출력해줘.
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
temp = (#WeatherProvider).weatherprovider_temperatureweather

(#Speaker).speaker_speak("외부 온도는 " + temp + "도입니다")
```
- output code:
```
temp = (#WeatherProvider).weatherprovider_temperatureweather
(#Speaker).speaker_speak(temp)
```

### Row 11 - low (0.0)
- command_eng: Tell me the outdoor humidity through the speaker.
- command_kor: 외부 습도를 스피커로 말해줘.
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
hum = (#WeatherProvider).weatherprovider_humidityweather

(#Speaker).speaker_speak("외부 습도는 " + hum + "%입니다")
```
- output code:
```
humidity = (#WeatherProvider).weatherprovider_humidityweather
(#Speaker).speaker_speak("현재 외부 습도는 " + humidity + "%입니다")
```

### Row 12 - low (0.0)
- command_eng: Output today's weather through the speaker.
- command_kor: 오늘의 날씨를 스피커로 출력해줘.
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
weather = (#WeatherProvider).weatherprovider_weather

(#Speaker).speaker_speak("오늘 날씨는 " + weather + "입니다")
```
- output code:
```
weather = (#WeatherProvider).weatherprovider_weather
(#Speaker).speaker_speak(weather)
```

### Row 14 - low (0.0)
- command_eng: Announce the outdoor fine dust level using the speaker.
- command_kor: 외부 미세먼지 농도를 스피커로 알려줘.
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
dust = (#WeatherProvider).weatherprovider_pm10weather

(#Speaker).speaker_speak("외부 미세먼지 농도는 " + dust + "입니다")
```
- output code:
```
dust_level = (#WeatherProvider).weatherprovider_pm10weather
(#Speaker).speaker_speak("현재 외부 미세먼지 농도는 " + dust_level + " 입니다.")
```

### Row 16 - low (0.0)
- command_eng: Output the charger's power consumption through the speaker.
- command_kor: 충전기의 전력소모량을 스피커로 출력해줘.
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
power = (#Charger).charger_power

(#Speaker).speaker_speak("전력소모량은 " + power + "입니다")
```
- output code:
```
power = (#Charger).charger_power
(#Speaker).speaker_speak(power)
```

### Row 17 - low (0.0)
- command_eng: Tell me today's menu using the speaker.
- command_kor: 오늘의 메뉴를 스피커로 출력해줘.
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
menu = (#MenuProvider).menuprovider_todaymenu

(#Speaker).speaker_speak("오늘의 메뉴는 " + menu + "입니다")
```
- output code:
```
menu = (#MenuProvider).menuprovider_todaymenu
(#Speaker).speaker_speak(menu)
```

### Row 20 - low (0.0)
- command_eng: Set the hue of the light to 200 and the saturation to 50.
- command_kor: 조명의 색조를 200, 채도는 50으로 설정해줘.
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
(#Light).light_movetohueandsaturation(200, 50)
```
- output code:
```
(#Light).light_movetohue(200)
(#Light).light_movetosaturation(50)
```
