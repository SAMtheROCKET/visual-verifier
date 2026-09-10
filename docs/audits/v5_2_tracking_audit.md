# V5.2 Final Audit

## Milestone

Visual Verifier `0.2.0a0` adds deterministic temporal tracking and integrity
analysis to the validated V5.1b foundation.

## Required regression contract

- Full blur: PASS
- Partial blur: FAIL
- Failed frames: `4, 8, 12`
- Full fixture: 19 tracks, 41 observations, no track gaps
- Partial fixture: 15 tracks, one gapped primary track
- Primary partial track: missing frames `4, 8, 12`, continuity `0.8`, three
  recoveries

## Quality gate

Run:

```powershell
./scripts/validate_v5_2.ps1
```

The script runs cleanup, locked dependency synchronization, Ruff, Mypy,
Pytest, CLI doctor, deterministic temporal regression checks, package builds,
and wheel-content inspection.

## Safety boundary

Tracking evidence is descriptive in V5.2. It does not alter the established
frame-level verification result and does not claim semantic object identity.

`archive/legacy_cells/` remains unchanged.
