[Derived generation g001 atom: language_preservation]
Lineage parents: 24

- For speaker/report/notify/output commands, call `Speaker_Speak(...)`; never invent `MediaPlayback_Speak`.
- If command_kor contains an explicit quoted Korean message, preserve that exact Korean message in `speaker_speak(...)` rather than translating it to English. Prefer Korean output text when both command_eng and command_kor are provided.
