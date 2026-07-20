# Architecture

## Dependency direction

```text
public API / CLI
        |
        v
image and video pipelines
        |
        +--> media readers and normalization
        +--> region detection
        |       +--> geometry metrics
        |       +--> pixel metrics
        |       +--> sharpness metrics
        |       +--> severity and filtering
        |
        +--> annotations and report writers
        |
        v
immutable domain models and structured exceptions
```

Lower-level modules do not import the API or CLI.

## Main packages

`api.py`
: Stable one-call Python functions.

`cli.py`
: Command parsing, JSON output, and exit-code conversion.

`models.py`
: Immutable status, metadata, configuration, measurement, frame, failure,
  and result objects.

`media/`
: Metadata reading, image-size normalization, and synchronized video pairs.

`metrics/`
: Stateless geometry, pixel-difference, and sharpness calculations.

`detection/`
: Contour extraction, severity scoring, and region acceptance.

`pipeline/`
: Image and video orchestration.

`reporting/`
: Annotated evidence and CSV/JSON serialization.

## Design choices

- Pure functions are used for stateless mathematical operations.
- Classes own lifecycle state such as video captures and video writers.
- Results are immutable dataclasses.
- Public APIs accept natural argument names.
- Internal variables use descriptive names and type-oriented suffixes.
- Historical scripts are never runtime dependencies.

## Future extension points

The empty `policies`, `targets`, `tracking`, and `integrations` namespaces
reserve future package locations. No implementation is public until tested.
