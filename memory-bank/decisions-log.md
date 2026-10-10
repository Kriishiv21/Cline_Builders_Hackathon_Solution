# Decisions Log

| Date | Decision | Rationale |
| --- | --- | --- |
| 2026-10-10 | Replace every architecture "train a model" step with a Cline API call | Task instruction: use a Cline API key structure instead of training |
| 2026-10-10 | Package named `uspi` instead of `platform` | Avoids shadowing Python's stdlib `platform` module |
| 2026-10-10 | Contextual bandit implemented as online LinUCB in plain Python, not via Cline | It is an online learner adapting from logged feedback, not an offline-trained model; the "replace training with Cline" instruction targets offline-trained detectors/classifiers |
| 2026-10-10 | GNN prior (C05) shipped but disabled by default | Architecture marks it "Specified, unproven"; ablation-gated per `configs/gnn_prior.yaml` |
| 2026-10-10 | Truecaller adapter stubbed, mock used by default | Capability unconfirmed per architecture section 16.3 |
| 2026-10-10 | Added a shared `uspi/speech/pipeline.py` (`SpeechPipeline`: STT -> refinement) used by both the recorded-voice (V1) and live-call (V2) input tracks | User request: add the STT + refinement components (modelled on a reference meeting-assistant pipeline) with stable ids/timestamps, streamlined and in sync across both tracks |
| 2026-10-10 | STT output is `uspi.common.schema.TranscriptSegment` with a deterministic `segment_id` (`uspi.common.hashing.new_segment_id`, keyed on case_id+window+index) | Lets content-risk, live-analyser, fusion `evidence_ids` and the voice/live report all trace back to the exact same transcript span |
| 2026-10-10 | Refinement (`uspi/speech/refine.py`) is a Cline-backed structured call per segment batch, gated by a `difflib` similarity guard (`min_similarity_ratio`) | Same "replace training with Cline" pattern as other LLM-backed components; the guard prevents the LLM from fabricating content over a raw ASR mistake, matching the reference app's edit-guard concept |
| 2026-10-10 | Whisper/STT itself (not the refinement step) stays outside the Cline substitution | It is a pretrained ASR model, not something this platform trains; only `WhisperSTTAdapter`'s wiring is a stub, left for a real integration |
