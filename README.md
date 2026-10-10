# Unified Scam Intelligence Platform (Text + Voice)

Reference implementation of the architecture described in
`docs/architecture.md` (source: *Unified Scam Intelligence Platform —
Complete Architecture*, 10 Oct 2026).

> **Design note on "training".** The source architecture calls for several
> trained models: the text Stage-3 SLM, the AASIST spoof-detection branch,
> the phonetic/formant logistic-regression branch, the live voice
> authenticity adapter, the content-risk classifier, and (new) the STT
> **refinement** step. This repository does **not** ship or train any of
> those models. Every place the architecture says "train a model" is
> instead implemented as a call to the **Cline API** (`CLINE_API_KEY` +
> `CLINE_API_BASE`) through a single shared client
> (`uspi/common/cline_client.py`). The LLM returns a schema-validated
> structured signal (score + semantics + confidence + rationale); all
> thresholds, calibration, fusion, hysteresis, tiers and bandit logic
> remain deterministic code, per principle 4 and 6 of the architecture
> ("Deterministic decisions live in the backend"). Whisper/STT itself is
> the one exception: it is a pretrained ASR model, not something this
> platform trains, so it is not routed through Cline.

> **STT + refinement (new).** `uspi/speech/pipeline.py::SpeechPipeline`
> runs speech-to-text (`uspi/speech/stt_adapter.py`) followed by a
> Cline-backed refinement pass (`uspi/speech/refine.py`) that corrects
> garbled ASR output without inventing content (guarded by a `difflib`
> similarity check). Every transcript unit carries a stable, deterministic
> `segment_id` + timestamps (`uspi.common.schema.TranscriptSegment`), so
> the content-risk signal, the live analyser, fusion `evidence_ids`, and
> the voice/live reports can all trace back to the exact span it came
> from. The **same** `SpeechPipeline` is used on both input tracks:
> `uspi/voice/pipeline.py::RecordedVoicePipeline` (recorded voice, V1) and
> `uspi/live/pipeline.py::LiveCallPipeline` (live call, V2 — via both
> `process_audio_chunk` for raw audio and `process_chunk` for an
> externally supplied transcript chunk), so the two input tracks stay in
> sync with every step that comes after.

This is a design-fidelity reference implementation meant to be run locally,
unit-tested, and extended — it is **not** a validated fraud-detection
product and must not be presented as one. No real scores are claimed.

## Layout

See `docs/architecture.md` §14 for the full repository layout rationale.

```
.clinerules/        Cline rules pack (plan/act workflow, scientific integrity, privacy, etc.)
memory-bank/         Cline Memory Bank (project brief, decisions log, progress)
third_party/aasist/  Placeholder for the vendored official AASIST repo (not vendored here;
                     the adapter in uspi/voice/aasist_adapter.py calls the Cline API instead)
uspi/                All pipeline code (ingestion, text, voice, speech, live, fusion, bandit, ...)
                     Named "uspi" (Unified Scam Intelligence Platform) rather than "platform" to
                     avoid shadowing Python's stdlib "platform" module; this is the "platform/"
                     package referenced throughout docs/architecture.md section 14.
web/                 Minimal call-simulator front end for the live (V2) demo
configs/             YAML configuration: thresholds, weights, tiers, bandit actions, Cline model ids
experiments/         Results ledger + split-file placeholders (section 12.3 "three labelled groups" rule)
tests/               pytest unit/integration tests (all Cline API calls are mocked)
docs/                Architecture copy, decisions log, limitations, demo script, evaluation protocol
```

## Quick start

```bash
python -m venv .venv
. .venv/Scripts/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then fill in CLINE_API_KEY
pytest -q                       # all Cline calls are mocked in tests, no network/key required
uvicorn uspi.api.app:app --reload --port 8000
```

Open `web/static/index.html` in a browser (served statically or via
`python -m http.server` from `web/static`) to try the live-call simulator
against the local API.

## Environment variables

See `.env.example`. The only required secret is `CLINE_API_KEY`. All Cline
calls go through `uspi/common/cline_client.py`, which is the single
place that knows about `CLINE_API_BASE`, `CLINE_MODEL_ID`, retries, timeouts
and JSON-schema validation/repair. No other module is allowed to import an
HTTP client directly (enforced by `.clinerules/40-privacy-and-safety.md`
and `tests/test_no_direct_http.py`).

## Status

Design-fidelity reference implementation. Every numeric threshold and
weight lives in `configs/*.yaml`, never hardcoded in code, per §14 of the
architecture. Every component in `docs/architecture-component-inventory.md`
is implemented at least as a typed stub with the documented interface, so
the fusion engine, bandit, and report builder are exercised end-to-end by
`tests/test_end_to_end.py`, using mocked Cline responses.
