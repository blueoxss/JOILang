

---
[GA Prompt Patch Overlay]
[GA block 06 micro_rules]
- Solve each dataset row independently from the current command only. Never reuse a previous row's JSON name, receiver, service, enum argument, numeric argument, or code skeleton.
- Classify schedule type before writing JSON: one-shot action, fixed cron trigger, repeated period loop, delay sequence, or trigger-then-repeat. Use period=0 for one-shot or scheduled one-shot commands, preserve explicit cron triggers, and use positive period only when repeated monitoring is explicit.
- When code is schema-valid but not target-equivalent, compare schedule, receiver, service, numeric, enum, dataflow, and action order before final output. Verify schedule, receiver, service, numeric, enum, dataflow, and output schema before final JSON.
- Preserve every numeric literal required by the current command and bind it to the selected service argument. Convert units using the service descriptor, such as minutes to seconds for seconds-based arguments, and never drop numeric thresholds or durations.
[GA block 02 micro_rules]
- Never invent service/member names. Copy the exact canonical device-prefixed service member from the injected schema, preserving lowercase, underscores, and device prefix. If a generated member looks camelCase, class-style, capitalized, or paraphrased, replace it with the nearest schema-valid canonical member before final JSON.
- Select the receiver tag from the current command target before choosing any service. Preserve owner/location/group/sector tags exactly and choose only services attached to that receiver; never reuse a receiver from a previous row.
- For enum-valued services, copy the allowed enum string exactly from the selected service descriptor. Do not translate, paraphrase, or borrow enum values from another device or previous row.
