[Derived generation g001 atom: value_function_dataflow]
Lineage parents: 07, 17, 20

- For plain on/off/start/stop commands, prefer the exact `Switch_On` or `Switch_Off` function when the same target device exposes switch behavior. Do not replace plain power control with mode setters such as `SetAirPurifierMode("auto")`, `SetAirConditionerMode("cool")`, `SetDehumidifierMode("dehumidifying")`, or value-state comparisons. Use mode setters only when the command explicitly asks to set a mode.
- Treat categories inside the same connected-device group as shared capabilities of one physical device. If the user says "turn on/켜줘/start/activate" for a semantic target such as `#AirPurifier` and that group exposes `Switch_On`, emit `(#AirPurifier).switch_on()` or `(#Study #AirPurifier).switch_on()`. Do not add `#Switch` to the receiver unless the user explicitly names a switch, and do not use `SetAirPurifierMode("auto")` just because the enum says auto means the fan is on.
- For state preconditions such as "the AC/air conditioner is off" / "에어컨이 꺼져 있으면", test the shared switch state: `(#AirConditioner).switch_switch == false`. Do not infer off-state from `AirConditionerMode == "auto"` or another mode value.
- If the command says "if it is off turn it on, if it is on turn it off" and the target exposes `Switch_Toggle`, use the single toggle action instead of expanding to two branches.

23. Read values from sensors and send side effects to actuators. Never call `Speaker_Speak` on a `TemperatureSensor`, never call camera functions on a `PresenceSensor`, and never set charging state through an invented service if the schema offers `Switch_Off` for the charger.

- Keep the code minimal and directly aligned with the command.
- Separate trigger devices from action devices. Read values from sensors, but call actions on the actual actuator. For example, read temperature from `TemperatureSensor` and speak through `Speaker_Speak`, not through a sensor device.
- For weather reports through speaker, use `WeatherProvider_Weather` in a spoken sentence; do not call `WeatherProvider_GetWeatherInfo(0, 0)` without explicit latitude/longitude.
- For current-time reports through speaker, use `Clock_Hour` and `Clock_Minute` in the spoken text rather than only `Clock_Time`.
