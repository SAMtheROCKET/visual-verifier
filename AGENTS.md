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
    The package must never import a networking library; this is
    enforced by `tests/test_local_execution.py`, not by review.
13. Preserve the expected demo contract:
    - raw versus full blur: PASS
    - raw versus partial blur: FAIL
    - failed frames: 4, 8, 12
14. Do not claim production, regulatory, or privacy certification without
    benchmark evidence.
15. Keep every command in documentation copy-pasteable. Use forward
    slashes in example paths; `tests/test_repository_hygiene.py` fails the
    build on stray control characters.
16. Keep the version in one place. `visual_verifier.__version__` is the
    single source; packaging and citation metadata are asserted against it.

Read `docs/CODE_STYLE.md` before writing or refactoring active code.

## Required checks

Run before declaring work complete:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q --cov=visual_verifier
```

Ruff enforces the rules above mechanically: `D` for docstrings, `ANN` for
type hints, `E501` for line length, and `C90` for complexity. The coverage
gate in `pyproject.toml` must not be lowered to make a change pass.

`scripts/run_quality.sh` and `scripts/run_quality.ps1` run the same gate.

## Current development phase

V5.3, released as `0.3.0`: the modular typed foundation, deterministic
temporal tracking, and reviewed target-aware verification.

Two rules govern what may change a verdict, and they differ:

- **Tracking is evidence-only.** It must never change the frame-level
  PASS/FAIL decision.
- **Targets are a requirement, and deliberately do change it.** A frame
  carrying an uncovered required target fails even when other processing
  occurred. Supplying no targets must leave every previous result
  identical, which `tests/test_target_verification.py` asserts.

Never present an interpolated target box as a reviewed one. Provenance
travels with every target into every report.

The selectable policy system (V5.4) follows; see `ROADMAP.md`.
