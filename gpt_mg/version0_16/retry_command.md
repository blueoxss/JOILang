# version 2025-08-06
"When generating a new JOI Lang code after user feedback, Don't generate the previously generated code ({all_items[choice_no]}) as the same.
    Integrate all newly added conditions with the previous requirements, and ensure the new code satisfies every combined requirement.
    Regenerate the JOI Lang code based on **current sentence** and **the added conditions**.: {current_sentence}

---

- ✅ This rule applies to **function** services (e.g., `switch_on`, `alarm_off`)  
and also to **value** services used in conditions (e.g., `temperatureMeasurement_temperature > 30`)

- ❗ When the input mentions broad categories like "모든 장치" or "all devices",  
you must **not generalize to all known devices** with the matching function (e.g., switch_off).
Instead, follow this stricter rule:

✅ Only include device categories that have already been **explicitly or implicitly referenced** in the original input or earlier part of the code.

- Example:
- Input: "조명을 꺼줘 + 모든 장치 꺼줘."
- Since only `조명 (Light)` was mentioned, only `Light` is a valid inferred category.
- Final code: `all(#Light).switch_off()`

❌ Do not auto-include all categories like `#Fan`, `#DoorLock`, `#Feeder`, etc.  
unless they were **previously mentioned** or **explicitly covered by tag filters** in connected_devices.