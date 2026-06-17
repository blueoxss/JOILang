## Step-by-Step Guide for Separating `value` and `function` in Natural Language Commands (Prompt Guide)

---

## Purpose
Your task is to:
1. Clearly separate **conditions (`value` services)** and **actions (`function` services)**.
2. Respect and preserve the **logical order** and **pairing** of condition → action in the original sentence.
3. Output must be **valid JOI Lang syntax**, with strictly defined structure and service names.

---

## CRITICAL Naming Rule for `service_list_ver2.0.1`

The v2.0.1 service schema stores the device name and service name in separate fields:
- `device`: e.g. `Television`
- `service`: e.g. `SetChannel`

When writing JOI Lang code, you must **compose the final JOI service identifier** as:
- **`{device}_{service}`**

This is a mandatory transformation rule for both values and functions.

### Required conversion examples
- device=`Television`, service=`SetChannel` -> `Television_SetChannel`
- device=`Television`, service=`Channel` -> `Television_Channel`
- device=`Speaker`, service=`Speak` -> `Speaker_Speak`
- device=`Safe`, service=`Lock` -> `Safe_Lock`

### Forbidden output patterns
- Do NOT output only the bare service name:
  - `(#Television).SetChannel(30)`  <- wrong
  - `(#Television).setChannel(30)`  <- wrong
  - `(#Television).Channel`         <- wrong

### Required output patterns
- `(#Television).television_setchannel(30)` <- correct
- `(#Television).television_channel`        <- correct

### Internal self-check before final output
Before returning the final JOI JSON, verify every value/function token in the code:
1. Find the matched schema row.
2. Read both `device` and `service`.
3. Rewrite the final JOI identifier as `{device}_{service}` exactly.
4. If the final code contains a bare service name without the device prefix, fix it before output.

---

## Step 1: Distinguish Conditional vs. Action Phrases
### Conditions: Characteristics of `value` Phrases
Purpose: Used for state evaluation or comparison conditions
- Used for evaluating the state of sensors or devices.
- Includes expressions like: "if", "when", "greater than", "in case", "is on", "equals", "during", etc.
- You must only use `value` services defined in [service_list_value]
- Both device tags and service names must exactly match the entries
- For v2.0.1 schemas, the final JOI token must be `{device}_{service}`, not the bare `service`
- Do NOT create or assume any service name that is not explicitly listed
- If a device does not exist in the full list, use a device only if it exists in [connected_devices]
- Do not use undefined value services (e.g., windowControl_window) in condition expressions
#### [Correct Examples]
- if ((#Television).Television_Channel == 30)
#### [Incorrect Examples]
- (#Television).Channel == 30
- This is missing the device prefix in the final JOI token


### Actions: Characteristics of `function` Phrases
Purpose: Used for device control or command execution
- Used for executing control commands on devices.
- Includes verbs like: "turn on", "turn off", "open", "close", "send", "activate", etc.
- You must only use `function` services defined in [service_list_function]
- Both device tags and function names must exactly match the entries
- For v2.0.1 schemas, convert the matched pair `(device, service)` into `{device}_{service}` in the final JOI code
- If a device is not available in the full list, use only those available in [connected_devices]
- Do not use value-type services as functions
#### [Correct Examples]
- (#Television).Television_SetChannel(30)
- (#Speaker).Speaker_Speak("hello")
#### [Incorrect Examples]
- (#Television).SetChannel(30)
- This uses only the schema `service` field and omits the required device prefix



---


## Step 2: Prepare extracted `value`/`function` for JOI Lang processing
### Split compound natural language commands into:
- `value` expressions (conditions) → Convert into sensor evaluation expression:  
  `if ((#Sensor).attribute >= value)`
- `function` expressions (actions) → Convert into device command expression:  
  `(#Tag).function_on()`
#### [Example]  
Command: “If it’s raining and the window is open, close the window.”
- `value`:
  - “It’s raining”
  - “The window is open”
- `function`:
  - “Close the window”


---


## Step 3: Extract `value` and `function` + Preserve Temporal **Execution Order**
### General Patterns of Execution Flow
- Your job is not just to separate them, but also to **preserve the execution order as implied by the natural sentence**, not just by grammar structure.
- Natural language commands can appear in different logical forms.  
- The model must handle the correct **temporal relationship** between condition and action.

#### ✅ Pattern 1: Condition → Action (Most common)
- Evaluate condition first, then execute one or more actions.
[Example]:  
> “If it’s raining and the window is open, close the window.”
```
if ((#RainSensor).rainStatus == "on" and (#Window).windowControl_door == "open") {
    (#Window).windowControl_close()
}
```
#### ✅ Pattern 2: Action → Condition → Termination or Follow-up
- The command begins with an action, and later introduces a condition for stopping, switching, or repeating.
[Example]:  
> “Turn on the irrigator. When the light exceeds 500 lux, turn it off and stop.“
```
(#Irrigator).switch_on()
wait until ((#LightSensor).lightLevel_light >= 500)
(#Irrigator).switch_off()
break
```
#### ✅ Pattern 3: Multiple Independent Condition → Action Pairs
- Each condition controls its own action. They are not necessarily sequential or nested.
- Always **evaluate the condition before executing any related action**.
- Never reverse the order from the original command unless explicitly indicated.
[Example]:  
> “If soil is dry, start irrigation. If temperature is high, turn on the fan.”
```
if ((#SoilSensor).moisture < 30) {
    (#Irrigator).switch_on()
}
if ((#Thermometer).temperatureMeasurement_temperature >= 30) {
    (#Fan).switch_on()
}
```
#### ✅ Pattern 4: Mixed or Nested Execution Flow
- Commands can involve a **combination of patterns**, such as:
  - A condition triggering multiple actions,
  - Then a follow-up condition for termination,
  - Or nested conditions within an action block.
[Example]:  
> “If it's morning and no one is home, open the curtains. Then, when the light exceeds 800 lux, turn them off.”
```
if ((#Clock).clock_time >= 600 and (#Presence).presence == "not_present") {
    (#Curtain).curtain_open()
    wait until ((#LightSensor).lightLevel_light >= 800)
    (#Curtain).curtain_close()
}
```


---


## Additional Syntax Rules for Mapping
### For **value services**:
Use the **return_descriptor** to determine comparison format and semantics.

#### [Example]
- If "device": "Clock", "service": "clock_time" has return_descriptor = {"format": "hhmm"},
then use:
"code": if ((#Clock).clock_time == 1515)

### For **function services**:
Use **argument_type** or **argument_format** to determine the correct format.
Use **argument_bounds** or **argument_descriptor** to determine the correct format.




---


## Summary Table of Examples

| Natural Language Command                               | value                          | function       |
|--------------------------------------------------------|--------------------------------|----------------|
| If the door is open, trigger the alarm                 | Check door status              | Trigger alarm  |
| If the window is closed and temperature exceeds 30°C   | Window status, temp condition  | Turn on fan    |
| When the button is pressed, turn off the lights        | Button press                   | Turn off light |
| If any humidity sensor in Group 1 reads below 30       | Group 1 humidity condition     | Water the area |

---

## Proceeding to the Next Step

1. Use `value` → map automatically from [`service_list_value`] (`service_list_ver2.0.1_value.json`)
2. Use `function` → map from [`service_list_function`] (`service_list_ver2.0.1_function.json`)
3. Assemble both into a complete JoI-Lang code block  
