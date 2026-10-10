# Project Brief

Reference implementation of the Unified Scam Intelligence Platform
(text + recorded voice + live call) described in `docs/architecture.md`.

Key constraint for this build: every "trained model" called for by the
architecture (Stage-3 SLM, AASIST branch, phonetic branch, live voice
authenticity adapter, content-risk classifier) is implemented as a
structured call to the Cline API (`uspi/common/cline_client.py`) using an
API key, rather than as a locally trained model. Deterministic code
(thresholds, calibration bookkeeping, fusion, hysteresis, tiers, bandit)
remains in plain Python.
