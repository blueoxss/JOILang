[Derived generation g001 atom: receiver_and_connected_scope]
Lineage parents: 03, 04, 18, 19

- Do not copy a condition location into a later action unless the command explicitly scopes that action. Example: "if presence is detected in the living room, turn on all lights" means the condition receiver is `(#LivingRoom #PresenceSensor)` but the action target is global `all(#Light)`, not `all(#LivingRoom #Light)`.
- For WindowCovering/Blind/Shade actions, direction words are strict: "raise", "up", "open", "올려", "열어" -> `WindowCovering_UpOrOpen`; "lower", "down", "close", "내려", "닫아" -> `WindowCovering_DownOrClose`. Do not invert these for blinds.
- If the command says blind/shade/window but the retrieved category is `WindowCovering`, keep the semantic receiver tag from the command: use `(#Blind).windowcovering_uporopen()`, `(#Shade).windowcovering_downorclose()`, or `(#Window).windowcovering_currentposition` rather than bare `(#WindowCovering)` when the natural-language target is specific.
- Normalize floor selector tags: `first floor` -> `#Floor1`, `second floor` -> `#Floor2`, `third floor` -> `#Floor3`. Do not emit duplicate aliases such as `#ThirdFloor #Floor3`.
- For a `#Window` receiver, use `armrobot_currentposition >| 0` for open and `armrobot_currentposition == 0` for closed when this value is available. Do not use `door_doorstate` on `#Window`.

Global rules:
- Use only the provided service_list_snippet, which is derived from `connected_devices` and the authoritative `datasets/service_list_ver2.0.1.json`.
- In the snippet, each `device_group` is one connected-device bundle. Each `capability_binding` is one pair of:
  1. a `category` plus the full authoritative service list for that category
  2. the usable selector tags for that category: `user_defined_tags` and `locations`
- `user_defined_tags` are built from `tags` after removing tags that duplicate category names.
- `locations` are also selector tags. They can be combined with user-defined tags before the category tag.
- Receiver construction rule:
  - base receiver: `(#Category)`
  - filtered receiver: `(#SelectorTag #Category)`
  - combined receiver: `(#Location #CustomTag #Category)`
  - grouped receiver: `all(#Location #CustomTag #Category)`
- If the command does not mention a selector tag, `(#Category)` is valid.
- If the command mentions a location, platform, brand, or custom tag, preserve only the selector tags that are explicitly supported by the matching capability binding.
- For schema fallback, services listed under a capability binding should use that binding category. For connected-device groups with multiple categories, sibling capabilities from the same physical device may be used on the semantic target receiver. Examples: if an AirPurifier group also exposes Switch, use `(#AirPurifier).switch_on()` for plain power control; if a Light group also exposes ColorControl, use `(#Light).colorcontrol_setcolor(...)` for color setting.
- If `connected_devices` is empty, the snippet falls back to the full authoritative schema, so category-only receivers are allowed.
- Never invent devices, categories, tags, locations, values, functions, enum values, helper methods, or argument formats.
- Prefer `canonical_name` exactly when the snippet provides it.
- Use `canonical_name` only as the schema-matching reference. In final JOILang code, every receiver tag after `#` must start with an uppercase English letter; schema category tags must use the exact schema CamelCase. Lowercase only the member token after `).` or `all(...).`. Example: `(#kitchen #light).Light_MoveToRGB(255,255,0)` must be emitted as `(#Kitchen #Light).light_movetorgb(255,255,0)`.
- Never use raw connected-device ids such as `tc1_...` in the final JOILang code. Use tag-based receivers instead.

- Prefer tag-based receivers that preserve every semantic tag in the command, such as `all(#Hallway #Light)`, `all(#Even #RobotVacuumCleaner)`, `(#Entrance #Light)`, or `(#MeetingRoom #Door)`. Do not compress tags into alias-like ids such as `#Hall_Light` or `#Even_Robot`.
- Match spaced or lowercase phrases in the command to CamelCase connected tags when their normalized text is the same. For example, "wine cellar", "winecellar", and "와인 셀러" should preserve the connected tag `#WineCellar` when it is available.
- Treat "any sensor", "any presence sensor", "all sensors", "every sensor", and Korean equivalents such as "아무/모든 센서" as group receiver requests. Use `all(#Location #SensorCategory)` for the trigger receiver instead of dropping the location or using a single `(#SensorCategory)`.
- For Korean speaker announcements that say a temperature changed rapidly (`온도가 급변`), use the concise statement `"<target>의 온도가 급변했습니다"` without extra punctuation. If the target is wine cellar, use `"와인셀러의 온도가 급변했습니다"`.

5. If the command does not mention a selector tag, prefer the base receiver `(#Category)`.
6. If the command addresses a group such as "all", "every", "any", or a plural target, prefer `all(...)` with the same selector tags instead of a single-target receiver.
7. Never emit raw connected-device ids such as `tc1_...` in the JOILang code.
8. Use `canonical_name` only as the schema-matching reference. In the final JOILang code, emit the lowercase form of that member token after the receiver dot. Example: canonical_name `Dishwasher_SetDishwasherMode` becomes `dishwasher_setdishwashermode` in code.
9. Do not output bare raw service names when `canonical_name` is available, and do not preserve uppercase service casing in the final code.
