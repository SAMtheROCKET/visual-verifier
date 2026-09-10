# Benchmarks

Nothing here ships in the wheel.

Tests and benchmarks answer different questions. A test says the
implementation behaves the way it was designed to. A benchmark says the
design solves a problem a simpler method would not.

## Anonymization Gap Benchmark

```bash
uv run python -m benchmarks.run_anonymization_gap --output results
```

Measures how reliably a method finds frames where a target that should
have been anonymized was left exposed, against mean pixel difference,
PSNR, and SSIM baselines.

The published results and the full protocol are in
[`docs/benchmarks.md`](../docs/benchmarks.md). Read the protocol before
quoting a number from it: the baselines are given a held-out calibration
set and an oracle upper bound, and Visual Verifier runs untuned, because
a benchmark that flatters the tool publishing it is worthless.

| Module | Purpose |
| --- | --- |
| `scenarios.py` | Generates the labelled sequence families |
| `baselines.py` | Mean difference, PSNR, and SSIM implementations |
| `scoring.py` | Confusion counts and threshold selection |
| `runner.py` | Runs every method and applies the split protocol |
| `report.py` | Renders the markdown and JSON results |

`tests/test_benchmark_harness.py` covers the scoring and split logic, so
a benchmark reporting a wrong number fails the normal test run.
