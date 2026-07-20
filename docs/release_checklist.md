# Release Checklist

## Repository hygiene

- Run `scripts/clean_repository.ps1`.
- Confirm no cache, bytecode, egg-info, build, or generated output remains.
- Confirm `archive/legacy_cells/` is unchanged.
- Confirm placeholder source modules are absent.

## Quality

- `uv sync --locked`
- `uv run ruff format --check .`
- `uv run ruff check .`
- `uv run mypy src --python-version 3.12`
- `uv run pytest -q`
- `uv run visual-verifier doctor`

## Regression contract

- Raw vs. full blur: `PASS`
- Raw vs. partial blur: `FAIL`
- Failed frames: `4`, `8`, and `12`

## Packaging

- Build the source distribution and wheel.
- Confirm the wheel contains `visual_verifier/py.typed`.
- Confirm the wheel excludes tests, archives, caches, and placeholders.
- Confirm version metadata is `0.1.0a0`.
- Review `CHANGELOG.md`, `ROADMAP.md`, and `CITATION.cff`.

Run `scripts/validate_release.ps1` to execute the automated portion.
