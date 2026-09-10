#!/usr/bin/env bash
#
# Run the complete Visual Verifier quality gate on Linux and macOS.
#
# Checks formatting, linting, static types, tests, and coverage without
# installing Python, synchronizing dependencies, or modifying repository
# files. This is the POSIX counterpart of scripts/run_quality.ps1.

set -Eeuo pipefail

PYTHON_VERSION_TEXT="3.12"
SOURCE_DIRECTORY_NAME="src"
COVERAGE_TARGET_NAME="visual_verifier"

repository_path="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repository_path"

printf 'Visual Verifier - quality gate\n'
printf 'Repository: %s\n\n' "$repository_path"

if ! command -v uv >/dev/null 2>&1; then
    printf 'uv is not installed or available on PATH.\n' >&2
    printf 'Install it from https://docs.astral.sh/uv/ first.\n' >&2
    exit 1
fi

run_step() {
    printf '\n==> %s\n' "$*"
    "$@"
}

run_step uv run ruff format --check .
run_step uv run ruff check .
run_step uv run mypy "$SOURCE_DIRECTORY_NAME" \
    --python-version "$PYTHON_VERSION_TEXT"
run_step uv run pytest -q "--cov=$COVERAGE_TARGET_NAME"

printf '\nAll quality checks passed.\n'
