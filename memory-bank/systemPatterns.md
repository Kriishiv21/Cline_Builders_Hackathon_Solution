# System Patterns

- **Single Cline gateway**: `uspi/common/cline_client.py` is the only
  module performing network calls to the Cline API. All "trained model"
  adapters (`uspi/text/slm_stage3.py`, `uspi/voice/aasist_adapter.py`,
  `uspi/voice/phonetic_adapter.py`, `uspi/live/analyser_client.py`,
  `uspi/speech/content_signals.py`) call through it with a component name,
  system prompt, JSON schema, and fallback.
- **Unified Signal schema**: every detector/adapter emits
  `uspi.common.schema.Signal`; the fusion stacker only consumes signals
  through this interface.
- **Config-driven thresholds**: all weights/thresholds live in
  `configs/*.yaml`, loaded via `uspi.common.config.load_yaml`.
- **Safety constraints outside the bandit**: `uspi/bandit/safety_constraints.py`
  filters eligible actions before the bandit ever sees them.
- **Shared speech pipeline**: `uspi/speech/pipeline.py::SpeechPipeline` is
  the single STT -> refinement component used by both `uspi/voice/pipeline.py`
  (recorded-voice, V1) and `uspi/live/pipeline.py` (live call, V2). Every
  transcript unit is a `uspi.common.schema.TranscriptSegment` carrying a
  deterministic `segment_id` + `start_s`/`end_s`, produced by
  `uspi.common.hashing.new_segment_id`. Downstream Cline-backed analysers
  (`ContentRiskAnalyser`, `LiveAnalyserClient`) receive that `segment_id`
  and copy it into `Signal.evidence_ids`, so every signal, the fusion
  report, and the live/voice report can be traced back to the exact
  timestamped span it came from, on either input track.
