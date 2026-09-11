# Changelog

All notable changes to Visual Verifier are documented here.

## [Unreleased]

### Added

- A `The missing test after visual processing` section in both README
  surfaces, stating the category rather than only the feature set:
  most tools transform visual media, this one independently tests
  whether the transformation happened, where and when it was required.
  Face blurrers and plate redactors are upstream systems it verifies,
  not competitors
- `docs/llms.txt`, an agent-readable project summary and documentation
  index following the emerging convention
- `docs/robots.txt`, pointing crawlers at the generated sitemap
- Open Graph and Twitter card metadata via a theme override, so a
  shared link renders as a preview rather than a bare URL. Every value
  is a meta tag and the image is served from the site's own origin, so
  the no-third-party-resource guarantee is unchanged
- `scripts/generate_social_card.py`, rendering the 1200x630 preview from
  the bundled fixture rather than by hand, so the plate it shows blurred
  and the plate it shows readable are the frames the demo verifies
- A descriptive home-page title, `Anonymization QA for Images & Videos`,
  in place of a bare product name
- `tests/test_discoverability.py`, covering the sitemap reference, the
  agent index and its links, the card dimensions, the metadata block,
  and the category statement

- The frozen positioning statement in both README surfaces: Visual
  Verifier brings software-testing discipline to processed image and
  video output, rather than trusting that a job completed
- `PYPI_README.md`, a compact project page for PyPI. The repository
  README stays long on purpose; at 21,000 characters it buried the
  install command several screens down on PyPI. The packaged page is
  3,300. `scripts/build_pypi_readme.py` now reads the packaged readme
  from `pyproject.toml`, so the rewriter cannot target a different file
  from the one PyPI renders
- A closing verdict card on the demonstration GIF, so the animation ends
  on `FAIL` and the missed frame numbers rather than stopping mid-run.
  Every number on it is derived from the verification that produced the
  animation
- A measured answer to how precisely a reviewed target must be drawn.
  Boxes up to 40% larger than the object pass at the default coverage
  threshold; at 45% every correctly anonymized frame fails at once,
  because coverage is one ratio per target and crosses together
- First-run guidance for real footage, covering looser boxes, codec
  artefacts against the benchmark's JPEG round trip, and the deliberately
  permissive severity default
- A CI step exercising `actions/download-artifact`, which is used only by
  the release workflow and so was never run on a pull request. A major
  version bump to it would previously have been first exercised during a
  real release

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
- A `Target coverage` section in the console summary, printed only when
  targets were supplied
- Target overlays on the annotated video, coloured by coverage verdict
  and prefixed with `~` when the box was interpolated
- `examples/targets/demo_targets.csv`, which reproduces the demo
  contract: `PASS` against the fully blurred clip and `FAIL` on frames
  4, 8, and 12 against the partially blurred one
- A `Visual Verifier + targets` row in the Anonymization Gap Benchmark,
  labelled as not a like-for-like comparison because it receives
  information no baseline is given
- Comprehensive target regressions across loading, coverage,
  interpolation, end-to-end verification, and media-aware validation,
  including one asserting that supplying no targets leaves every
  previous result identical
- `targets/validation.py`, which checks every target against the
  reference media before a frame is read and again after the run, and
  `tests/test_target_media_validation.py` covering it
- First-class `targets`, `target-min-coverage`, and
  `allow-uncovered-targets` inputs on the GitHub Action, plus
  `target-coverage-percent`, `uncovered-target-frame-count`,
  `uncovered-target-count`, and `uncovered-target-ids` outputs
- A `Required targets` section in the GitHub job summary, and target
  coverage rows in its measurement table
- Target-aware HTML evidence: a target coverage tile, a required-target
  table, the declared target box drawn over each before/after
  comparison, and a per-frame reason naming which of the two failure
  modes applied
- Reviewed targets in the `GitHub Action self-test` job, including a
  check that a target the media cannot contain fails the run
- A `GitHub Action self-test` run on Python 3.10, the minimum the
  package supports. Every other step in that job pins 3.12, so
  3.12-only syntax in the composite wrapper would have passed CI while
  breaking the oldest supported interpreter. `tests/test_github_action.py`
  reads the minimum from `requires-python` and fails if no workflow
  exercises the action on it

### Fixed

- **A target outside the media could produce a false `PASS`.** A target
  declaring a frame the video does not have parsed correctly and then
  vanished: the frame loop never visited it, no coverage was measured,
  and a run that should have failed reported `PASS` with zero targets.
  Verification that silently skips a declared requirement is not
  verification, so both this and an out-of-bounds box now raise
  `TARGET_VALIDATION_ERROR` before any frame is read. A second check
  after the run catches a target that fell out anyway, which media
  metadata disagreeing with a decoder can still cause
- **`frames_without_processing` counted target failures.** It was
  derived from every failing frame, so a run where all 15 frames were
  processed but a target was missed reported 15 frames with processing
  and 15 without. Unprocessed frames, target-failed frames, and failed
  frames are now three separate sets, and the measurement uses the
  first
- **A frame could lose one of its two failure reasons.** Target-failed
  frames were removed from the unprocessed list, so a frame with no
  processing *and* an uncovered target reported only
  `UNCOVERED_TARGETS`. Both codes are now reported independently, which
  is the distinction target-aware verification exists to make
- **A permitted gap was still reported as a failure.** With
  `expect_processing_every_frame=False` an unprocessed frame is allowed,
  but a frame failing for a target reason still listed it under
  `UNPROCESSED_FRAMES`, describing a policy the run was not applying.
  The measurement still counts those frames; only the failure is gated
- **The HTML report described every failing frame as "no processing
  detected"**, including frames where processing was detected and only
  the required region was missed, and carried the generic-policy caveat
  on target-aware runs
- **The action's default requirement was unpinned.** `@v0.3.0` could
  install any later release, defeating the point of pinning the tag. It
  now defaults to `visual-verifier==0.3.0`
- **README images rendered nowhere before the first push.** They used
  absolute `raw.githubusercontent.com/.../main/...` URLs, which return
  404 until that exact ref carries the assets, so an editor preview and
  every fresh clone showed alt text instead. Links are now relative, and
  `scripts/build_pypi_readme.py` converts them at release time because
  PyPI resolves neither form. `tests/test_readme_assets.py` checks that
  every linked file exists, that no absolute URL creeps back in, and
  that the release workflow converts before it builds
- The bug-report and question templates asked reporters for their
  version while suggesting `0.2.0`, and `SECURITY.md` described the
  project as `pre-alpha` and listed `0.2.0` as supported. The classifier
  has been `Alpha` since 0.2.0, and `0.2.0` was never released. A guard
  now fails when any community file advertises a version other than the
  package's own
- The bug-report template's environment example was a maintainer's own
  `doctor` output, naming a specific Windows build number. It is now a
  neutral example, and a guard rejects build numbers in templates
- A determinism test replaced the bare words `first` and `second`
  anywhere in the report, so a repository path containing either word
  made a correct implementation look nondeterministic. It now
  normalizes only the exact output directories that differ
- `pyproject.toml` pointed PyPI at the `docs/` directory rather than the
  published documentation site
- The benchmark's capability table claimed the target-aware row needed
  no tuning, when it reaches 100% only with a raised severity floor. The
  column now states each method's operating point instead

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

Completed but never tagged or published. `v0.2.0` does not exist on the
remote, so this section records the work rather than a release; `0.3.0`
is the first version published to PyPI. It is kept as its own entry
because the work is a distinct milestone, and rewriting it into `0.3.0`
would obscure what changed when.

The first version with documentation assets generated from real
verification runs, and the one that advanced the trove classifier from
`Pre-Alpha` to `Alpha`. Report schemas may still change before V6.0.

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
