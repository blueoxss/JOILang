[Derived generation g001 atom: temporal_cron_period]
Lineage parents: 11, 12

- Encode wall-clock start/day filters in `cron` and repeated intervals in `period`. Do not wrap the whole code in duplicate weekday/hour checks when `cron` already anchors the start/day. For time windows ending at midnight, use `if ((#Clock).clock_hour == 0) { break }`.
- For "from now until 3 PM" / "오후 3시까지", use `if ((#Clock).clock_hour == 15) { break }`, not `>= 15`.
- For two wall-clock actions in one scenario, use the first time as `cron` and a blocking `delay(...)` for the later action. Example: 8 AM odd blinds then 9 AM even blinds -> `delay(1 HOUR)`, not `wait until clock_hour == 9`.

- If the command is a repeated event trigger such as "whenever", "each time", "every time", "button is pressed", "door is opened", or "fully charged", prefer `period = 100` and edge-trigger logic such as `prev/curr` or triggered-state guards. Do not collapse repeated triggers into a one-shot `wait until`.
- If the command is a one-shot trigger introduced by a plain "when" without repeated wording, `wait until` is acceptable.
- For "check/read/measure now and again after N minutes; if it changed by T or more" commands, use a snapshot pattern: read the original value into a variable, `delay(N MIN)`, read the same value service again from the same receiver tags, then compare `new >= original + T or new <= original - T`. Do not use `wait until true`, `period`, or `prev/curr` edge-trigger logic for this one-shot recheck pattern.
