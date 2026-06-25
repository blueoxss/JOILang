5. If the command does not mention a selector tag, prefer the base receiver `(#Category)`.
6. If the command addresses a group such as "all", "every", "any", or a plural target, prefer `all(...)` with the same selector tags instead of a single-target receiver.
7. Never emit raw connected-device ids such as `tc1_...` in the JOILang code.
8. Use `canonical_name` only as the schema-matching reference. In the final JOILang code, emit the lowercase form of that member token after the receiver dot. Example: canonical_name `Dishwasher_SetDishwasherMode` becomes `dishwasher_setdishwashermode` in code.
9. Do not output bare raw service names when `canonical_name` is available, and do not preserve uppercase service casing in the final code.
