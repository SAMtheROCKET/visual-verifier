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
- `uv run pytest -q --cov=visual_verifier`
- Coverage meets the gate in `pyproject.toml`
- `uv run visual-verifier doctor`
- `uv run visual-verifier --version` matches `visual_verifier.__version__`

## Documentation integrity

- Every documented command is copy-pasteable and free of control
  characters, verified by `tests/test_repository_hygiene.py`
- `examples/expected/demo_expectations.json` matches the README table
- `CHANGELOG.md` records every user-visible change
- `CITATION.cff` version matches the package version
- README assets regenerated with
  `uv run --with pillow python scripts/generate_readme_assets.py` and the
  PASS/FAIL frames they show still match the demo contract
- README image links stay **relative** in the repository, so an editor
  preview and GitHub's repository view render them. The release workflow
  runs `scripts/build_pypi_readme.py --ref <tag>` before building,
  because PyPI resolves neither relative paths nor a ref that does not
  exist yet. `tests/test_readme_assets.py` enforces both halves
- `uv run --with twine twine check --strict dist/*` passes
- `uv run python scripts/check_release_version.py vX.Y.Z` passes for the
  tag you are about to push; the release workflow runs it too
- The `SAMtheROCKET/visual-verifier@vX.Y.Z` references in `README.md`
  and `docs/ci.md` name the tag being pushed, asserted by
  `tests/test_github_action.py`

## GitHub Action

- The `GitHub Action self-test` job passed on the commit being tagged; it
  runs `action.yml` against both bundled fixtures and asserts the
  reported status, exit code, failed-frame count, and coverage
- Push the tag before announcing the action, since `uses:` resolves the
  tag rather than the branch

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
- Confirm the wheel installs into a clean environment and that
  `visual-verifier doctor` runs from it.
- Confirm version metadata matches `visual_verifier.__version__`.
- Review `CHANGELOG.md`, `ROADMAP.md`, and `CITATION.cff`.

The `Release` workflow performs the packaging checks automatically on a
`v*` tag and publishes through PyPI trusted publishing.

Run `scripts/validate_v5_2.ps1` for the complete automated gate. It runs
`validate_release.ps1` first and then the frozen V5.2 temporal regression
contract. That contract is retained on purpose: it pins the temporal
behaviour that shipped in V5.2 so later milestones cannot drift it
unnoticed. The script name refers to the contract it preserves, not to the
current product version.
