# Architecture

## Dependency direction

```text
public API / CLI
        |
        v
image and video pipelines
        |
        +--> media readers and normalization
        +--> region detection and measurements
        +--> temporal tracking session
        |       +--> deterministic association
        |       +--> lifecycle state
        |       +--> lineage events
        |       +--> integrity analysis
        |
        +--> annotations and report writers
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

## Compatibility design

Temporal tracking is enabled by default for video verification but remains
non-decisional in V5.2. Disabling it removes temporal reports without changing
frame-level PASS/FAIL outcomes.

Historical scripts under `archive/legacy_cells/` remain read-only and are not
runtime dependencies.
