# Policy System

## Current behavior

The current release does not expose selectable policy objects.

Image verification records the internal policy name `generic_change`.
Video verification records `generic_change_every_frame`.

These names describe the current decision rules; they are not user-selected
implementations.

## Planned policy contract

A future policy should receive typed measurements and return:

- A policy name and version
- PASS/FAIL status
- Structured failures
- Policy-level measurements
- Required evidence declarations

Policies must not perform media decoding or mutate pipeline state.

## Planned initial policies

`generic_change`
: Require accepted visual change without semantic targets.

`privacy_blur`
: Require target coverage and transformation strength for reviewed or
  automatically supplied privacy targets.

## Publication criteria

A policy becomes public only after:

- Typed configuration
- Unit tests
- End-to-end regression fixtures
- Documented threshold semantics
- Stable serialization
- CLI and API selection support

Until then, policy placeholder modules should not exist in active source.
