[Derived generation g001 atom: minimality]
Lineage parents: 21

13b. If a value service reports millivolts, convert user volts to millivolts in comparisons, e.g. `220V` -> `220000`.
14. Insert a power-check only if the same capability binding shows both a switch-like value and a power-on function for the same target context.
14a. For plain power commands such as "turn on", "switch on", "start", "turn off", "switch off", "stop", or "stop charging", use `Switch_On` or `Switch_Off` when the target exposes switch behavior. Do not substitute mode setters or value comparisons for power control. Examples: "turn on the air purifier" -> `switch_on()`, not `airpurifier_setairpurifiermode("auto")`; "stop charging" -> `switch_off()`, not `charger_chargingstate == "stopped"`.
15. If the request is ambiguous, choose the smallest schema-valid program that best matches the command.
16. If you cannot produce a schema-valid action with confidence, still return valid JSON with `code` as an empty string.
