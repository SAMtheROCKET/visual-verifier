# Visual Verifier Code Style

These rules apply to active code under `src/visual_verifier/` and to tests.
Historical files under `archive/legacy_cells/` remain unchanged.

## Structure

- Put reusable code under `src/visual_verifier/`.
- Prefer focused classes and functions over long procedural scripts.
- Keep a function or method at 50 physical lines or fewer.
- Keep command entry points and `main()` at 100 lines or fewer.
- Keep every source line at 79 characters or fewer.
- Put module constants after imports and write them in uppercase.
- Do not use machine-specific paths or notebook-global state.

## Naming

Use descriptive names that communicate physical or logical meaning.
Avoid one-letter and ambiguous names.

For local variables, add a useful type-oriented suffix when it improves
clarity. Examples:

```python
reference_path_obj: Path
candidate_image_ndarray: ImageArray
failed_frames_tuple: tuple[int, ...]
coverage_percent_float: float
region_rows_list: list[ReportRow]
verification_status_enum: VerificationStatus
```

Do not append a suffix mechanically when it makes a public API awkward.
Public API names should remain natural, stable, and easy to use.

## Type hints

- Type every public function, method, argument, and return value.
- Use typed dataclasses for structured state and results.
- Prefer immutable tuples for result collections.
- Use `numpy.typing.NDArray` aliases for image arrays.
- Use explicit tuple annotations before assigning a non-empty tuple.

## Docstrings

Public classes, functions, and methods require docstrings containing:

- A one-line operation summary.
- `Args` when arguments are not obvious.
- `Returns` for non-trivial return values.
- `Raises` for expected errors.
- `Warning` when behavior has an important limitation.

## Required checks

```powershell
uv run ruff format .
uv run ruff check .
uv run mypy src --python-version 3.12
uv run pytest -q
```
