# Contributing to Visual Verifier

Thank you for helping improve Visual Verifier.

## Product boundary

Visual Verifier checks processed media. It does not perform anonymization,
redaction, watermarking, or other transformations itself.

Active code belongs under `src/visual_verifier/`. Historical prototypes
under `archive/legacy_cells/` are read-only and must never be imported at
runtime.

## Development setup

Requires Python 3.10 or newer and [uv](https://docs.astral.sh/uv/).

On Linux and macOS:

```bash
uv sync
uv run visual-verifier doctor
```

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Unblock-File ./scripts/bootstrap_uv.ps1
./scripts/bootstrap_uv.ps1
```

Optional but recommended, so the fast checks run before every commit:

```bash
uvx pre-commit install
```

## Running the quality gate

```bash
./scripts/run_quality.sh      # Linux and macOS
```

```powershell
./scripts/run_quality.ps1     # Windows
```

Both run the same four checks CI runs:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q --cov=visual_verifier
```

Coverage is gated in `pyproject.toml`. Raise it when you can; never lower
it to make a change pass.

## Documentation assets

The README images are generated, never hand-drawn. Every pixel comes from
a real verification run over `examples/media/`, and the region boxes are
read back from the generated reports, so the documentation cannot show
behaviour the tool does not have.

Regenerate them after any change to detection thresholds, tracking
behaviour, or the bundled fixtures:

```bash
uv run --with pillow python scripts/generate_readme_assets.py
```

Commit the regenerated files in `docs/assets/` with the change that
caused them to move.

## Engineering requirements

Follow `AGENTS.md` and `docs/CODE_STYLE.md`.

In particular:

- Use complete type hints for public interfaces.
- Use descriptive names.
- Keep functions and methods at 50 physical lines or fewer.
- Keep entry points at 100 physical lines or fewer.
- Keep source lines at 79 characters or fewer.
- Keep algorithms deterministic and offline-capable.
- Do not add machine-specific paths.
- Do not expose placeholders as supported APIs.
- Add a regression test for every defect fix.
- Preserve the example-video regression contract.

## Pull request checklist

Before opening a pull request:

1. Add or update tests for changed behavior.
2. Update documentation for public behavior or schema changes.
3. Add a `CHANGELOG.md` entry for anything user-visible.
4. Run the quality gate for your platform.
5. Confirm raw vs. full blur passes.
6. Confirm raw vs. partial blur fails on frames `4`, `8`, and `12`.
7. Confirm no generated output or cache files are included.
8. Explain any threshold or schema change in the pull request.

The example contract in `examples/expected/demo_expectations.json` is
executed by `tests/test_demo_contract.py`. Changing the documented demo
results means changing that file deliberately, in the same commit, with an
explanation.

## Adding a new capability

A tracking, target, policy, batch, or integration module becomes public
only after it has:

- A typed implementation
- Unit tests
- End-to-end regression tests
- Documented inputs and outputs
- Failure-mode documentation
- Stable package exports
- No dependency on archived runtime code

## Reporting defects

Open a [bug report](https://github.com/SAMtheROCKET/visual-verifier/issues/new/choose)
and include:

- Visual Verifier version, from `visual-verifier --version`
- Python and operating-system versions, from `visual-verifier doctor`
- The exact command or API call
- The expected and actual result, including the exit code and any
  `ERROR [CODE]` line
- A minimal reproducible media fixture when sharing is permitted
- Generated `summary.json` and relevant CSV rows

Remove private or identifying media before sharing publicly. Verification
inputs and evidence often contain faces, licence plates, and locations.

Suspected vulnerabilities follow the private process in `SECURITY.md`.
Conduct concerns follow `CODE_OF_CONDUCT.md`.
