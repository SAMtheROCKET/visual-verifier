# Release Checklist

## Repository hygiene

- Run `scripts/clean_repository.ps1`.
- Confirm no cache, bytecode, egg-info, build, or generated output remains.
- Confirm `archive/legacy_cells/` is unchanged.
- Confirm unsupported placeholder modules are absent.

## Quality

- `uv sync --locked`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src --python-version 3.12`
- `uv run pytest -q`
- `uv run visual-verifier doctor`

## Frame regression contract

- Raw vs. full blur: `PASS`
- Raw vs. partial blur: `FAIL`
- Failed frames: `4`, `8`, and `12`

## Temporal regression contract

- Full fixture: 19 tracks and 41 observations
- Full fixture: no gapped tracks
- Partial fixture: 15 tracks
- Partial primary track: missing frames `4`, `8`, and `12`
- Partial primary track: continuity `0.8` and three recoveries

## Packaging

- Build the source distribution and wheel.
- Confirm the wheel contains `visual_verifier/py.typed`.
- Confirm active tracking and track-report modules are included.
- Confirm tests, archives, caches, and placeholders are excluded.
- Confirm version metadata is `0.2.0a0`.
- Review `CHANGELOG.md`, `ROADMAP.md`, and `CITATION.cff`.

Run `scripts/validate_v5_2.ps1` for the complete automated gate.
