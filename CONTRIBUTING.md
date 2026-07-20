# Contributing to Visual Verifier

Thank you for helping improve Visual Verifier.

## Product boundary

Visual Verifier checks processed media. It does not perform anonymization,
redaction, watermarking, or other transformations itself.

Active code belongs under `src/visual_verifier/`. Historical prototypes
under `archive/legacy_cells/` are read-only and must never be imported at
runtime.

## Development setup

On Windows PowerShell:

```powershell
Set-ExecutionPolicy `
    -Scope Process `
    -ExecutionPolicy Bypass `
    -Force

Unblock-File .\scripts\bootstrap_uv.ps1
.\scripts\bootstrap_uv.ps1
```

For later checks:

```powershell
.\scripts\run_quality.ps1
```

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
3. Run `scripts/run_quality.ps1`.
4. Confirm raw vs. full blur passes.
5. Confirm raw vs. partial blur fails on frames `4`, `8`, and `12`.
6. Confirm no generated output or cache files are included.
7. Explain any threshold or schema change in the pull request.

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

Include:

- Visual Verifier version
- Python and operating-system versions
- The exact command or API call
- The expected and actual result
- A minimal reproducible media fixture when sharing is permitted
- Generated `summary.json` and relevant CSV rows

Remove private or identifying media before sharing publicly.
