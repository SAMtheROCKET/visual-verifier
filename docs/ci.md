# Use it in CI

The exit code is the whole integration surface. No wrapper script, no
plugin, and no report parsing required. The GitHub Action below is a
convenience over that contract, not a replacement for it.

| Exit code | Meaning |
| ---: | --- |
| `0` | Verification completed and passed |
| `1` | Verification could not be completed |
| `2` | Verification completed and failed |

Distinguishing `1` from `2` matters. `1` means the tool could not do its
job, such as media missing, unreadable, or a threshold rejected. `2` means
it did its job and the answer was no.

## GitHub Action

On GitHub the bundled action is three lines:

```yaml
- name: Verify anonymization coverage
  uses: SAMtheROCKET/visual-verifier@v0.3.0
  with:
    reference: fixtures/source.mp4
    candidate: build/anonymized.mp4
```

It installs the tool, runs the comparison, publishes a job summary naming
the failing frames, uploads the evidence, and can keep one updated
pull-request comment. It is listed on the
[GitHub Marketplace](https://github.com/marketplace/actions/visual-verifier). Every input and output is documented on the
[GitHub Action](github_action.md) page.

## GitHub Actions without the action

The action is a convenience, not a requirement. Two steps do the same job
if you would rather not take the dependency.

```yaml
- name: Install Visual Verifier
  run: pip install visual-verifier

- name: Verify anonymization coverage
  run: |
    visual-verifier video \
      --reference fixtures/source.mp4 \
      --candidate build/anonymized.mp4 \
      --output artifacts/verification \
      --quiet

- name: Upload evidence
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: anonymization-evidence
    path: artifacts/verification/
```

`if: always()` matters. The evidence is most useful on the run that failed,
and without it the upload is skipped exactly when you need it.

Reviewers open `artifacts/verification/index.html` and see the failing
frames without knowing anything about this tool.

## GitLab CI

```yaml
verify-anonymization:
  image: python:3.12-slim
  script:
    - pip install visual-verifier
    - visual-verifier video
      --reference fixtures/source.mp4
      --candidate build/anonymized.mp4
      --output artifacts/verification
      --quiet
  artifacts:
    when: always
    paths:
      - artifacts/verification/
```

## As a test assertion

`raise_for_failure()` turns a result into a structured exception, so the
check reads like any other test:

```python
from visual_verifier import verify_video


def test_every_frame_is_anonymized() -> None:
    result = verify_video("fixtures/source.mp4", "build/anonymized.mp4")
    result.raise_for_failure()
```

The raised `VerificationFailedError` carries the policy name, the failed
frame numbers, and the failure count in its structured context.

## Reading the result from a script

```bash
visual-verifier video \
    --reference raw.mp4 --candidate out.mp4 --json > result.json
```

`--json` prints the same document written to `summary.json`. A regression
test asserts the two carry the same content, so either source is safe to
parse.

```bash
jq -r '.failed_frames | length' result.json
jq -r '.measurements.processing_coverage_percent' result.json
```

## Gating on coverage instead of any gap

By default every frame must contain accepted processing. To allow gaps and
gate on coverage instead, pass `--allow-unprocessed-frames` and read the
measurement yourself:

```bash
visual-verifier video \
  --reference raw.mp4 --candidate out.mp4 \
  --allow-unprocessed-frames --json > result.json

python -c "import json,sys; d=json.load(open('result.json')); sys.exit(0 if d['measurements']['processing_coverage_percent'] >= 99.5 else 1)"
```

## Performance notes

Verification is single-pass and decodes both videos in lockstep, so runtime
scales with frame count and resolution rather than with clip length in
seconds. `--no-annotated-video` skips re-encoding and is the largest single
saving when you only need the machine-readable result.

The HTML report captures at most 24 failing frames as downscaled JPEGs, so
its size does not grow with the length of the input.

## Handling missing codecs on a runner

Minimal container images sometimes ship an OpenCV build that cannot write
MP4. Verification does not need an encoder; only annotated video does.

```bash
visual-verifier doctor        # reports DEGRADED when no codec is available
```

Add `--no-annotated-video` on such runners and the rest of the evidence set
is produced normally.
