# 11 — Baseline preservation

- `uspi/bandit/baseline_policy.py` must always remain available and
  importable independent of `uspi/bandit/contextual_bandit.py`, so the
  offline evaluation (baseline vs bandit) in section 12.2 of the
  architecture can always be run.
- Do not delete or weaken `uspi/bandit/safety_constraints.py` checks to
  make a bandit experiment look better. Safety constraints are enforced
  outside any learned policy and are not tunable by experiment results.
