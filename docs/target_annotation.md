# Target Annotation

Target-aware verification is not implemented in the active package.

This document records the intended reviewed-target model for future work.

## Proposed target fields

| Field | Meaning |
| --- | --- |
| `frame_number` | One-based video frame number |
| `target_id` | Stable identifier across frames |
| `target_type` | Optional semantic category |
| `x1`, `y1` | Inclusive top-left coordinates |
| `x2`, `y2` | Exclusive bottom-right coordinates |
| `required` | Whether failure should affect status |
| `source` | Manual, interpolated, or detector-provided |

## Coordinate contract

Coordinates should use the reference-media coordinate system. Boxes should
have positive area and remain within frame dimensions.

## Planned workflow

1. Create or review target boxes.
2. Validate the target file.
3. Interpolate only explicitly permitted frame gaps.
4. Compare accepted processing regions with each target.
5. Report target coverage, continuity, and failures.
6. Preserve reviewed annotations separately from generated outputs.

## Safety note

Automatic targets must never be silently treated as ground truth. Their
provider, confidence, and review state must remain visible in reports.
