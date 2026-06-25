[Derived generation g001 atom: delay_wait_break]
Lineage parents: 13, 14

17. If the command says to do one action and then another action after some duration, keep the first action immediately, then use `delay(...)` with the requested duration, then emit the follow-up action.
17a. Use the JOILang helper `delay(N SEC|MIN|HOUR)` for between-action waits. Do not emit `(#Clock).clock_delay(...)` for these delays.
18. If the command describes a threshold crossing such as "drops below", "rises above", or "becomes X or higher", do not collapse it to a single unconditional action. Use an explicit condition, wait-until, or `prev/curr` edge-detection pattern that preserves the trigger semantics.

19. If the command asks to repeat alternating actions over time, prefer period-based stateful logic over cron syntax unless the command refers to a wall-clock time like 7 AM or every Monday.
20. If the command is a repeated event trigger using wording like "whenever", "each time", "every time", "button is pressed", "door is opened", or "becomes fully charged", default to `period = 100` and preserve edge-trigger semantics with `prev/curr` or a triggered flag. Do not reduce these commands to one-shot `wait until`.
21. If the command is a one-shot trigger with plain "when" and no repeated wording, `wait until` is acceptable.
22. For commands that say "every N minutes from X to Y" or "check every N minutes from X to Y", represent the repeated interval with `period` in milliseconds and preserve the time-window stop condition with `Clock` guards or break logic. Use `cron` only for wall-clock anchors that are explicitly stated.
