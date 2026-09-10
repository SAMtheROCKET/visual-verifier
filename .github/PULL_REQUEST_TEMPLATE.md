## What this changes

<!-- One paragraph. Link the issue this closes, if any. -->

## Why

<!-- The verification problem this solves, or the defect it fixes. -->

## Verification contract

- [ ] Raw vs. fully blurred still `PASS`
- [ ] Raw vs. partially blurred still `FAIL`
- [ ] Failed frames remain exactly `4`, `8`, and `12`
- [ ] Any intentional change to this contract is explained below

## Checklist

- [ ] Tests added or updated for the changed behaviour
- [ ] Every defect fix has a regression test
- [ ] Documentation updated for public behaviour or schema changes
- [ ] `CHANGELOG.md` updated for user-visible changes
- [ ] `uv run ruff format --check .` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run mypy src --python-version 3.12` passes
- [ ] `uv run pytest -q --cov=visual_verifier` passes
- [ ] No generated output, cache, or private media is included
- [ ] `archive/legacy_cells/` is unchanged

## Threshold or schema changes

<!-- Explain any detection, tracking, or report-schema change, and the
     evidence that justifies the new values. Write "None" if not applicable. -->
