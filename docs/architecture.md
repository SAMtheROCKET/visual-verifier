# Architecture

## Dependency direction

```text
public API / CLI
        |
        v
image and video pipelines
        |
        +--> media readers, writers, and normalization
        +--> region detection and measurements
        +--> temporal tracking session
        |       +--> deterministic association
        |       +--> lifecycle state
        |       +--> lineage events
        |       +--> integrity analysis
        |
        +--> annotations, report writers, console renderer
        |
        v
immutable domain models and structured exceptions
```

## Tracking boundary

`tracking/association.py`
: Stateless one-to-one IoU association.

`tracking/tracker.py`
: The only mutable temporal lifecycle owner.

`tracking/events.py`
: Stateless split and merge candidate detection.

`tracking/analysis.py`
: Stateless completed-track metrics.

`tracking/models.py`
: Immutable observations, states, events, frame results, and summaries.

Mutable tracker internals never escape into reports or public APIs. The video
pipeline receives immutable frame tracking results and completed summaries.

## Host-dependent capability

`media/video_writer.py`
: The only module whose behaviour depends on how OpenCV was built. It
tries each MP4-compatible codec in `VIDEO_CODEC_CANDIDATES_TUPLE` in order
and raises `ReportWriteError` listing every attempt when none open.

`visual-verifier doctor` probes the same list, so an environment that
cannot write annotated evidence is reported as `DEGRADED` before a run
rather than failing partway through one. Verification itself never needs
an encoder; only annotated evidence does.

## Presentation boundary

`reporting/console.py`
: Deterministic, side-effect-free rendering of a `VerificationResult` into
readable text. It reads the result only; it never re-derives measurements.

The command-line interface therefore holds no formatting logic. It parses
arguments, builds validated configuration objects, calls the public API,
selects a renderer, and maps the status onto an exit code.

## Compatibility design

Temporal tracking is enabled by default for video verification but remains
non-decisional. Disabling it removes temporal reports without changing any
PASS/FAIL outcome. Reviewed targets are the opposite: they are decisional by
design, and supplying them can change the verdict.

Historical scripts under `archive/legacy_cells/` remain read-only and are not
runtime dependencies.
