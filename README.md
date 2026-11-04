# lspec bench

The evaluation harness for [live-spec](https://github.com/claybford/live-spec):
scripted sessions that instantiate and operate living specifications under the
tool, scored against a pre-registered rubric. It is governed by its own living
specification, `bench-spec.html`; an agent session starts with `AGENTS.md`.

The artifact under test is a live-spec checkout named by `LSPEC_SRC`; this
repository carries its own copy of `lspec.py` and `hooks/` to operate itself.
Run reports live outside the repo (`bench-spec.html#dl-reports`).

Tests: `python3 -m unittest discover tests`.

MIT. Clayton Ford, 2026.
