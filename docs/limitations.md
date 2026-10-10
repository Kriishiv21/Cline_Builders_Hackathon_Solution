# Limitations

- This is a design-fidelity reference implementation, not a validated
  fraud-detection product. No accuracy, recall, or EER numbers are
  claimed anywhere in this repository.
- Every component that the architecture document asks to be *trained*
  (Stage-3 SLM, AASIST branch, phonetic/formant branch, live voice
  authenticity adapter, content-risk classifier) is implemented as a
  Cline-API-backed structured judgement instead, per explicit task
  instructions. These are NOT validated anti-spoofing or scam-detection
  models; their quality depends entirely on the underlying Cline model and
  prompt, and has not been benchmarked against ASVspoof, real call
  recordings, or any labelled scam dataset.
- The GNN prior (C05) ships disabled by default; it is unproven per the
  architecture and would need an ablation study before enabling.
- Truecaller integration is a documented stub; only a mock caller-hint
  adapter is enabled unless `TRUECALLER_ENABLED=true` and a real key is
  supplied (and even then the SDK call is unimplemented, since the
  underlying capability is unconfirmed per architecture section 16.3).
- Speaker diarization is a single-speaker fallback stand-in; pyannote
  integration is not vendored.
- Whisper/STT integration is a mock; `MockSTTAdapter` returns no
  transcript text. Real STT must be wired in for live/content-risk
  signals to receive non-empty transcripts.
- No signed OTA bundle mechanism, no real shadow-mode traffic splitting,
  no production drift (PSI) monitoring is implemented; the lifecycle
  module models the state machine only.
- No real telephony integration; the live pipeline expects transcript
  chunks pushed via the API (see `web/static/index.html` for a simulator).
