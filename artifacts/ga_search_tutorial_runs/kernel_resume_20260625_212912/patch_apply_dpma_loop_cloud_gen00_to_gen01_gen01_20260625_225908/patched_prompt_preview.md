

---
[GA Prompt Patch Overlay]
[GA block 02 micro_rules]
- Never invent service/member names. Copy the exact canonical device-prefixed service member from the injected schema; do not emit camelCase, class-style, capitalized, or paraphrased service names.
- Include every service implied by the current command and select services only from the injected schema under the selected receiver; do not substitute adjacent service families.
- Select receiver tags from the current command target before service selection. Preserve owner, location, group, and sector tags exactly, and never reuse a receiver from another row.
- For enum-valued services, copy the allowed enum string exactly from the selected service descriptor; do not translate, paraphrase, or borrow enum values from another device or previous row.
[GA block 06 micro_rules]
- Classify schedule type before writing JSON. Use period=0 for one-shot or scheduled one-shot commands, preserve explicit cron triggers, and use positive period only when repeated monitoring is explicit.
- For explicit fixed times, weekdays, midnight, or scheduled commands, derive cron first and preserve it exactly; do not replace a fixed schedule with only a period loop or Clock guard.
- Preserve every numeric literal required by the current command and bind it to the selected service argument or condition. Convert units using the selected service descriptor and never drop thresholds, durations, or target values.
- Before final JSON, compare schedule, receiver, service, numeric literals, enum arguments, dataflow, and action order against the current command; repair concrete mismatches before output.
