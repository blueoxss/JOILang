

---
[GA Prompt Patch Overlay]
[GA block 02 micro_rules]
- Always copy exact canonical service names from the schema with device prefixes and underscores; reject camelCase or paraphrased service names and replace them with schema-valid names before output.
- Select and preserve the receiver tag exactly from the current command target; do not reuse receivers from previous rows and ensure services are attached only to the current receiver.
- Copy enum string arguments exactly from the selected service descriptor; do not translate, paraphrase, or borrow enum values from other devices or previous rows.
[GA block 06 micro_rules]
- Classify schedule type precisely before JSON generation: use period=0 for one-shot or scheduled one-shot commands, preserve explicit cron triggers, and use positive period only for explicit repeated monitoring; never omit or misrepresent cron or period fields.
- Preserve all numeric literals required by the command and bind them to the correct service arguments; convert units as specified by the service descriptor and never drop numeric thresholds or durations.
- Generate each dataset row independently using only the current command; never reuse JSON names, receivers, services, enum arguments, numeric arguments, or code skeletons from previous rows.
- Before final output, verify component-wise equivalence: schedule, receiver, service, numeric, enum, dataflow, and output schema must match target exactly; perform detailed component comparison if schema-valid but not target-equivalent.
