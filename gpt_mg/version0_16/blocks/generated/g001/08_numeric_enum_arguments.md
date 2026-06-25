[Derived generation g001 atom: numeric_enum_arguments]
Lineage parents: 08, 09, 10

Hard generation rules:
1. Use only categories, values, functions, enum values, and receiver tags supported by the provided capability bindings.
2. When `connected_devices` is non-empty, do not use categories that are absent from the snippet. When it is empty, the snippet is schema fallback and category-only receivers are allowed.
3. In schema fallback, a service should be used through the category that owns it. In connected-device groups, sibling capabilities from the same physical device may be used through the semantic target receiver, e.g. `(#AirPurifier).switch_on()` or `all(#Light).colorcontrol_setcolor(...)`.
4. If the command mentions a location, platform, brand, or custom tag, keep only the selector tags that are both explicitly implied by the command and present in the matching binding.
5. If the command does not mention a selector tag, prefer the base receiver `(#Category)`.
6. If the command addresses a group such as "all", "every", "any", or a plural target, prefer `all(...)` with the same selector tags instead of a single-target receiver.
7. Never emit raw connected-device ids such as `tc1_...` in the JOILang code.
8. Use `canonical_name` only as the schema-matching reference. In the final JOILang code, emit the lowercase form of that member token after the receiver dot. Example: canonical_name `Dishwasher_SetDishwasherMode` becomes `dishwasher_setdishwashermode` in code.
9. Do not output bare raw service names when `canonical_name` is available, and do not preserve uppercase service casing in the final code.
10. Use value entries in conditions and function entries in actions.
10a. Prefer the most specific schema-valid service: if the command supplies all required slots for a parameterized function in `argument_bounds`, use that function instead of a generic value service. If required slots are missing, do not hallucinate them; use the generic value service only when it is the best schema-supported fallback.
10b. MenuProvider specificity rule: `MenuProvider_TodayMenu` is only for broad requests like "today's menu" with no specific place and no specific meal-time. If the command contains date/day, place, and meal-time, use `MenuProvider_GetMenu` with one STRING argument ordered as `"<date> <place> <meal>"`. Example: "오늘의 301동 점심 메뉴를 스피커로 알려줘" -> `menu = (#MenuProvider).menuprovider_getmenu("오늘 301동식당 점심")` then `(#Speaker).speaker_speak("오늘의 메뉴는 " + menu + "입니다")`. If the command says only "오늘 점심 메뉴" without a place, do not invent a cafeteria; fall back to `menuprovider_todaymenu`.
11. Match argument counts and argument types exactly.
12. For ENUM arguments, use only enum values explicitly present in the snippet.
13. If the command implies time or measurement units, convert to the service unit described by `descriptor`, `return_descriptor`, `argument_descriptor`, `argument_bounds`, and `argument_format` in the snippet. `period` always uses milliseconds.
13a. For `Oven_SetCookingParameters` and `RiceCooker_SetCookingParameters`, the cooking-time argument is seconds. Convert minutes to seconds, e.g. 30 minutes -> 1800. Do not use milliseconds and do not leave raw minutes.

- For dehumidifier "internal care" / "내부케어" in this dataset, use `Dehumidifier_SetDehumidifierMode("auto")` unless the snippet has an explicit internal-care enum.
- If a light color is specified by name and the snippet exposes `Light_MoveToRGB` or equivalent RGB control, convert the named color to explicit RGB values instead of drifting to a generic `SetColor` call.
- If the schema exposes an exact capture or close or lock action such as `Camera_CaptureImage`, `Switch_Off`, `Valve_Close`, or `DoorLock_Lock`, prefer that exact canonical action over invented synonyms such as `TakePicture` or `SetChargingState`.
- For `#Light` color actions, prefer `Light_MoveToRGB(r, g, b)` over `ColorControl_SetColor("r,g,b")` when `Light_MoveToRGB` is available.
- Do not use invalid off enums such as `Siren_SetSirenMode("off")`; use `Switch_Off()` when a siren must stop after a duration.
- Do not use empty siren mode strings such as `siren_setsirenmode("")`; use `switch_off()` when the siren must stop.
- For multi-button button 2, use `DimmerSwitch_Button2 == "pushed"` when available; do not invent `MultiButton_Button2` or `"pressed"`.
- Never emit lowercase receiver tags such as `#bedroom`, `#sector1`, `#entrance`, or `#temperaturesensor`. Use `#Bedroom`, `#Sector1`, `#Entrance`, and schema category tags such as `#TemperatureSensor`. Only lowercase the service or value member token after the receiver dot.

- Convert human time and measurement phrases to the unit expected by the chosen service. Use `descriptor`, `return_descriptor`, `argument_descriptor`, `argument_bounds`, and `argument_format` as authoritative unit/format hints. Use milliseconds only for `period`. Use service-specific units for function arguments and value comparisons.
