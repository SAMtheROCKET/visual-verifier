# Changelog

All notable changes to Visual Verifier are documented here.

## [Unreleased]

### Planned

- Selectable policy system with a typed policy protocol
- Batch verification and aggregate reports
- Alignment and synchronization diagnostics

## [0.3.0] - 2026-09-11

V5.3, target-aware verification. Until now the tool could say that
accepted visual change occurred in every frame. It could not say that
*the region which had to be anonymized* was the region that changed. A
frame where two of three licence plates were blurred passed, correctly
under the contract and uselessly for the reviewer.

The published benchmark measures the difference: without targets, plain
change detection scores 0% on weak blur, partially covered targets, and
a missed plate among several. With reviewed targets and a strict
severity floor it scores 100% on all three, taking the whole benchmark
from 79% to 100% recall with no false alarms.

### Added

- `--targets PATH`, accepting a reviewed target CSV that declares the
  regions which must be anonymized. Supplying it changes the policy from
  `generic_change_every_frame` to `target_coverage_every_frame`
- `visual_verifier.targets`, with `Target`, `TargetCoverage`,
  `TargetSource`, `TargetSummary`, `load_targets`, `interpolate_targets`,
  `measure_frame_targets`, and `summarize_targets`
- `TargetConfig` and `DEFAULT_TARGET_CONFIG`, exposing the coverage
  threshold, interpolation limit, and whether an uncovered target fails
  the run, with `--target-min-coverage`, `--target-max-gap`,
  `--no-target-interpolation`, and `--allow-uncovered-targets`
- `targets` and `target_config` arguments on `verify_video`, accepting
  either a file path or already-loaded targets
- Coverage measured as the **union** of every accepted region
  overlapping a target rather than the best single region, so two
  overlapping blur passes are not double counted and two partial passes
  can jointly cover a target
- Linear interpolation between reviewed boxes, refused across gaps
  longer than `--target-max-gap`, because a target can leave and re-enter
  a scene and a straight line across that would fabricate evidence
- An `UNCOVERED_TARGETS` failure reported separately from
  `UNPROCESSED_FRAMES`, so a reviewer can tell a skipped frame from a
  frame processed in the wrong place
- `target_report.csv` with one row per target per frame, and
  `measurements.targets` in `summary.json`
- A  section in the console summary, printed only when
  targets were supplied
- Target overlays on the annotated video, coloured by coverage verdict
  and prefixed with `~` when the box was interpolated
- `examples/targets/demo_targets.csv`, which reproduces the demo
  contract: `PASS` against the fully blurred clip and `FAIL` on frames
  4, 8, and 12 against the partially blurred one
- A `Visual Verifier + targets` row in the Anonymization Gap Benchmark,
  labelled as not a like-for-like comparison because it receives
  information no baseline is given
- 58 target regressions across `tests/test_targets.py` and
  `tests/test_target_verification.py`, including one asserting that
  supplying no targets leaves every previous result identical

### Changed

- Strict target validation rejects a file rather than verifying part of
  it. A missing column, a frame number below one, a box with no positive
  area, a negative coordinate, a duplicate identifier within one frame,
  or an unrecognized `required` or `source` value each fail with the
  offending line number. Treating an unreadable flag as `true` would
  have hidden the typo a reviewer needs to see
- Provenance travels with every target into every output, so a box this
  package generated is never presented as one a human reviewed
- `docs/target_annotation.md` documents shipped behaviour instead of
  recording an intended design

## [0.2.0] - 2026-09-10

First release published to PyPI, and the first with documentation
assets generated from real verification runs. The trove classifier
stays `Pre-Alpha`: report schemas may still change before V6.0.

### Added

- Readable console summaries for `visual-verifier image` and
  `visual-verifier video`, rendered by `reporting/console.py`
- `--json` for the previous machine-readable output and `--quiet` for
  exit-code-only reporting
- Help text, metavars, usage examples, and documented exit codes on every
  command-line option
- `--diff-threshold`, `--min-box-area`, `--min-changed-ratio`,
  `--min-mean-diff`, and `--min-severity` detection controls on the
  command line
- Structured `ERROR [CODE]` reporting on standard error, with the failing
  configuration fields listed
- Top-level exports for `DetectionConfig`, `TrackingConfig`, the default
  configurations, the result models, and the full exception hierarchy
- `examples/expected/demo_expectations.json`, executed by
  `tests/test_demo_contract.py`, so the published demo results cannot drift
- Repository hygiene, CLI, configuration-validation, console-rendering,
  codec-support, and metadata-consistency test suites; 32 collected tests
  grew to 270 and coverage from 88% to 91%
- `media/video_writer.py`, which tries each MP4-compatible codec in
  turn and reports every attempt when none can be opened
- A codec probe in `visual-verifier doctor`, reporting `DEGRADED` when
  the host OpenCV build cannot write annotated evidence
- `scripts/run_quality.sh` for Linux and macOS contributors
- macOS CI, a wheel install-and-run smoke check, a coverage gate, and a
  tag-triggered PyPI release workflow using trusted publishing
- A composite GitHub Action, `action.yml`, that installs the tool, runs
  the comparison, publishes a job summary with a frame timeline and the
  failing frame numbers, uploads the evidence, and can keep one updated
  pull-request comment. It exposes the status, exit code, unprotected
  frame count, and processing coverage as step outputs, and gates the
  job by default. `scripts/render_github_summary.py` renders the summary
  from `summary.json` alone, so it cannot drift from the documented
  output. A `GitHub Action self-test` job runs the action against both
  bundled fixtures on every pull request, because a composite action is
  shell that no unit test can reach
- A `GitHub Action` documentation page listing every input, output, and
  required permission
- The Anonymization Gap Benchmark under `benchmarks/`, measuring
  Visual Verifier against mean pixel difference, PSNR, and SSIM over 78
  generated sequences carrying 13 labelled failure modes. The baselines
  are given a held-out calibration set and an oracle upper bound while
  Visual Verifier runs untuned, because a benchmark that flatters the
  tool publishing it is worthless. Published results are in
  `docs/benchmarks.md`; `tests/test_benchmark_harness.py` covers the
  scoring and split logic so a wrong number fails the normal test run
- A documentation site built with MkDocs Material and published to
  GitHub Pages, with new Getting started, Anonymization QA, CI,
  Command line, and Python API pages that previously existed only as
  fragments of the README
- `scripts/check_site_privacy.py`, which fails the docs build if the
  site would load any third-party script, stylesheet, font, or media.
  A privacy tool whose own documentation phones home would undercut
  the claim it is making
- `tests/test_documentation_coverage.py`, which compares the published
  CLI reference against the real argument parser and fails when an
  option is undocumented, stale, or a page is orphaned from the nav
- A self-contained `index.html` evidence report written beside the CSV and
  JSON outputs, with a frame timeline, a before/after wipe comparison for
  every unprotected frame, and the tracked-region table. It references no
  external resource, embeds its own thumbnails, and is deterministic
- `--no-html-report` and the `save_html_report` API argument
- `media/thumbnails.py`, which bounds embedded evidence by capturing only
  failing frames and downscaling each one before encoding
- `visual-verifier demo`, a zero-clone demonstration that synthesizes a
  sample clip locally, verifies it, and writes the full evidence set.
  The sample is generated rather than shipped, so the wheel stays small
  and nothing is downloaded
- `tests/test_local_execution.py`, which parses every shipped module and
  fails if one gains the ability to open a socket, turning the "runs
  locally" privacy claim into an enforced property
- `scripts/check_release_version.py`, asserting that the Git tag, the
  package version, and `CITATION.cff` all agree before a tag can
  publish, with its own regression tests
- An AST-based test enforcing the 50-line function and 100-line entry
  point limits from `AGENTS.md`, which were previously documented but
  never measured
- README demonstration assets generated by
  `scripts/generate_readme_assets.py` from a real verification run, with
  region boxes read back from the generated reports
- `CODE_OF_CONDUCT.md` with private-only conduct reporting, a Q&A
  discussion template, and issue contact links separating questions,
  security reports, and conduct concerns
- `.gitattributes`, `.pre-commit-config.yaml`, `docs/README.md`, issue
  and pull-request templates, and Dependabot

### Changed

- `visual-verifier image` and `visual-verifier video` print a readable
  summary by default instead of a full JSON document. Pass `--json` to
  restore the previous output; a regression test asserts it carries the
  same document as `summary.json`, so scripted callers lose nothing
- `--output` is now optional, so verification can run without writing files
- Command-line defaults are read from the shipped configuration objects
  instead of duplicated literals
- Packaging version is derived from `visual_verifier.__version__`, and
  tests assert that packaging and citation metadata match it
- Ruff now enforces docstrings, annotations, complexity, naming, pathlib
  use, and pytest style in addition to the previous rule set
- `FINAL_AUDIT.md` and `V5_2_AUDIT.md` moved to `docs/audits/`
- Positioning leads with anonymization QA, the use case people search
  for, while stating that the engine verifies any pixel-level change
- Trove classifier advanced from `2 - Pre-Alpha` to `3 - Alpha`
- Documented that the default `--min-severity` of `8.0` accepts a blur
  too weak to anonymize, and that `--min-severity 50` rejects it with no
  new false alarms on the benchmark. The permissive default is kept
  because a high severity floor rejects legitimate processing on real
  footage
- The README headline says *verify* rather than *prove*. `PASS` reports
  that accepted visual change was detected under the configured
  thresholds; proving that a required semantic target was transformed
  is V5.3 work
- Detection and tracking threshold arguments are declared as data
  tables rather than repeated `add_argument` calls
- `pypa/gh-action-pypi-publish` is pinned to the reviewed commit for
  v1.14.2 rather than the mutable `release/v1` branch

### Fixed

- `summary.json` now lists every generated evidence path. `evidence_paths`
  was always written empty, so a machine consumer reading the documented
  entry point could not discover the reports beside it
- Annotated-video output no longer depends on a single codec being
  available, and the annotated-evidence regression now decodes the written
  file instead of only checking that it is non-empty
- Stray control characters in `README.md` and the V5.2 audit that silently
  corrupted the documented bootstrap, example, and validation commands
- Replaced the unused `examples/expected/demo_expectations.yaml`, which
  declared a contract nothing enforced

### Preserved

- Raw vs. fully blurred video remains `PASS`
- Raw vs. partially blurred video remains `FAIL`
- Failed frames remain exactly `4`, `8`, and `12`
- Tracking does not change the frame-level policy decision

## [0.2.0a0] - 2026-07-21

### Added

- Deterministic one-to-one IoU association
- Tentative, confirmed, lost, recovered, and closed lifecycle states
- Configurable confirmation and short-gap tolerance
- Monotonic non-reused track and event IDs
- Split and merge lineage evidence using overlap coefficients
- Continuity, fragmentation, association, motion, and stability metrics
- `track_report.csv`
- `track_observation_report.csv`
- `track_event_report.csv`
- Persistent track labels in annotated video
- Public `TrackingConfig`
- Python API and CLI tracking controls
- Dedicated temporal tracking documentation
- V5.2 unit and example-video regression tests
- V5.2 release-validation script

### Changed

- Video verification enables temporal tracking evidence by default
- Package version advanced to `0.2.0a0`
- Video evidence sets now include three temporal CSV reports
- Package and release validation inspect active tracking modules

### Preserved

- Raw vs. fully blurred video remains `PASS`
- Raw vs. partially blurred video remains `FAIL`
- Failed frames remain exactly `4`, `8`, and `12`
- Tracking does not change the frame-level policy decision

## [0.1.0a0] - 2026-07-20

### Added

- Typed image and video verification APIs
- Multi-region detection, filtering, severity, reports, and annotations
- CLI, quality scripts, package typing, and 23-test V5.1b foundation
