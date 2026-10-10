# 40 — Privacy and safety

- Raw phone numbers, UPI ids, names, and audio bytes must never appear in
  a Cline API payload. Use `uspi.common.hashing` to pseudonymize before
  building any `user_payload` dict passed to `ClineClient.call_structured`.
- Never log full transcripts or raw audio. `HASH_SALT` must come from the
  environment, never be hardcoded.
- Every Cline-backed component must define a documented fallback
  (`score_semantics = "unavailable"`) and must never silently promote a
  fallback result to "safe" or "no risk".
- `CLINE_API_KEY` must only be read via `uspi.common.config.cline_settings()`
  and must never be printed, logged, or embedded in a prompt string.
