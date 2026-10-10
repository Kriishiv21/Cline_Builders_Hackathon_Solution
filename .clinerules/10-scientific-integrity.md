# 10 — Scientific integrity

- No claimed result, score, or metric may be invented. Every number in
  `experiments/results_ledger.md` must be labelled: "measured by us" (with
  a ledger entry), "reported in the literature", or "not yet run".
- Cline-API-backed signals (Stage-3 SLM, AASIST proxy, phonetic proxy,
  live analyser, content-risk classifier) must always report their true
  `score_semantics` (`model_score` or `unavailable`), never
  `calibrated_probability`, unless a held-out calibration run has actually
  been performed and recorded.
- Never compare raw scores from different signal sources as if they were
  on the same scale.
