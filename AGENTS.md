# AGENTS.md

Guidance for any AI coding agent (Cline or otherwise) working in this repo.

- Read `docs/architecture.md` and `.clinerules/*.md` before making changes.
- `uspi/common/cline_client.py` is the only module allowed to call the
  Cline API directly. Do not add a second HTTP client.
- Never hardcode thresholds/weights; put them in `configs/*.yaml`.
- Never commit secrets, recordings, or raw transcripts.
- Run `pytest -q` before considering a change complete; all Cline calls in
  tests are mocked via `tests/conftest.py::stub_cline_client`.
- Update `memory-bank/progress.md` and `memory-bank/decisions-log.md` when
  completing a phase or making a non-trivial design decision.
