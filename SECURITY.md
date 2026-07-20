# Security Policy

## Supported versions

Visual Verifier is currently pre-alpha. Security fixes are applied only to
the latest development version.

| Version | Supported |
| --- | --- |
| `0.2.0a0` and current main branch | Yes |
| `0.1.0a0` | Security fixes only when reproducible |
| Earlier prototypes | No |

Historical scripts under `archive/legacy_cells/` are retained for research
history and are not supported runtime components.

## Reporting a vulnerability

Do not open a public issue for a vulnerability involving code execution,
dependency compromise, path traversal, unsafe file handling, or disclosure
of private media.

Use the repository's private GitHub security-advisory feature and include:

- A concise description
- Affected version or commit
- Reproduction steps
- Potential impact
- Suggested mitigation, when known

## Media privacy

Verification inputs and outputs may contain faces, licence plates, personal
locations, or other sensitive content.

Visual Verifier operates locally, but users remain responsible for:

- Controlling access to reference and candidate media
- Protecting generated annotated evidence and reports
- Removing sensitive fixtures before publication
- Following applicable privacy, employment, and data-retention rules

## Security limitations

A PASS result does not prove regulatory compliance or irreversible
anonymization. The current generic detector identifies accepted visual
changes; it does not prove that a particular private object was transformed.
