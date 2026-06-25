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
