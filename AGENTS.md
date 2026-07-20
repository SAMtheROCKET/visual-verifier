# Visual Verifier Agent Instructions

These instructions apply to human contributors and AI coding assistants.

## Product contract

Visual Verifier is a checker, not a media processor. It compares reference
and candidate media and returns reproducible PASS/FAIL evidence under an
explicit policy.

## Authoritative code

- Active code belongs under `src/visual_verifier/`.
- Tests belong under `tests/`.
- Small reproducible fixtures belong under `examples/`.
- `archive/legacy_cells/` is read-only historical reference.
- Never modify or import archived scripts at runtime.

## Engineering rules

1. Do not add hard-coded machine-specific paths.
2. Do not rely on notebook state or mutable module globals.
3. Keep algorithms deterministic and offline-capable.
4. Every bug fix requires a regression test.
5. Public functions require complete type hints and docstrings.
6. Keep functions and methods at 50 physical lines or fewer.
7. Keep `main()` and command entry points at 100 lines or fewer.
8. Keep source lines at 79 characters or fewer.
9. Use descriptive names; avoid single-letter local variables.
10. Use type-oriented variable suffixes where they improve clarity.
11. Put module constants after imports and use uppercase names.
12. Keep AI integrations optional; core behavior must remain local.
13. Preserve the expected demo contract:
    - raw versus full blur: PASS
    - raw versus partial blur: FAIL
    - failed frames: 4, 8, 12
14. Do not claim production, regulatory, or privacy certification without
    benchmark evidence.

Read `docs/CODE_STYLE.md` before writing or refactoring active code.

## Required checks

Run before declaring work complete:

```powershell
uv run ruff format .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q
```

## Current development phase

V5.1b foundation: modular media readers, metrics, region detection,
filtering, image/video pipelines, CLI, reports, and regression tests.
Tracking and target-aware V3 parity follow after this foundation passes.
