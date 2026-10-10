# Progress

- [x] Phase 0: repo skeleton, canonical event schema, replay harness
- [x] Phase 3 (adapted): audio preprocessing, VAD, quality metadata, windowing
- [x] Phase 4 (adapted): text core (Stage1/Room2/enrichment) + Cline-backed Stage 3
- [x] Phase 6 (adapted): calibration/fusion (voice), ablation-ready interfaces
- [x] Phase 9 (adapted): live path (analyser client, call risk engine, RAG store, caller hint, authenticity adapter)
- [x] Added: shared STT + refinement component (`uspi/speech/pipeline.py`), wired identically
      into both the recorded-voice (V1) and live-call (V2) input tracks, with deterministic
      segment ids/timestamps propagated into content-risk/live-analyser signals and reports
- [x] Phase 10: fusion + policy engine, reviewer console, feedback ledger
- [x] Phase 11: Part 04 bandit (context, actions, safety constraints, LinUCB, OPE, policy manager)
- [ ] Phase 12: robustness harness, security red-team (basic injection guard shipped, full harness is future work)
- [ ] Phase 13: signed bundle OTA (lifecycle stage machine shipped; signing not implemented)
- [ ] Phase 14: GNN kept disabled; payment merge minimal; source-filter branch not built (per cut order)

This is a design-fidelity reference implementation, not a validated
product. No accuracy numbers are claimed.
