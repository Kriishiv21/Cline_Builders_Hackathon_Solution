# 00 — Master workflow

- Plan first for anything touching scoring logic, thresholds, fusion,
  bandit safety constraints, or the Cline client contract. Use Plan mode;
  do not jump to Act mode for these changes.
- Small milestones: implement one module, add/extend its tests, run
  `pytest -q`, commit, then continue.
- Never hardcode a threshold, weight, or window parameter in code — add it
  to `configs/*.yaml` and read it via `uspi.common.config.load_yaml`.
- Every number that appears in a report, ledger entry, or results table
  must trace to a config version and (if applicable) a Cline model id
  (see `docs/decisions-log.md`).
- `uspi/common/cline_client.py` is the ONLY module allowed to perform an
  HTTP call to the Cline API. Adding a second HTTP client anywhere else is
  a rule violation (enforced by `tests/test_no_direct_http.py`).
