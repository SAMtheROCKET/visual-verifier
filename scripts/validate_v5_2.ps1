<#
.SYNOPSIS
Runs the complete V5.2 temporal tracking release gate.

.DESCRIPTION
Runs the base release validation and then executes the deterministic V5.2
temporal regression contract from a temporary Python script.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-RepositoryPath {
    <#
    .SYNOPSIS
    Resolves the repository directory containing the scripts folder.
    #>

    $repository_path_obj = Split-Path -Parent $PSScriptRoot
    return (Resolve-Path $repository_path_obj).Path
}

function Assert-CommandSucceeded {
    <#
    .SYNOPSIS
    Raises an error when the previous native command failed.

    .PARAMETER CommandName
    Human-readable command name included in the error.
    #>

    param(
        [Parameter(Mandatory)]
        [string] $CommandName
    )

    if ($LASTEXITCODE -ne 0) {
        throw (
            "$CommandName failed with exit code " +
            "$LASTEXITCODE."
        )
    }
}

function Invoke-TemporalRegression {
    <#
    .SYNOPSIS
    Runs the deterministic V5.2 temporal regression contract.
    #>

    $regression_code_str = @'
from pathlib import Path

from visual_verifier import verify_video


media = Path("examples/media")
reference = media / "video_raw.mp4"

full = verify_video(
    reference,
    media / "video_blur.mp4",
    save_annotated_video=False,
)
partial = verify_video(
    reference,
    media / "video_blur_partial.mp4",
    save_annotated_video=False,
)

assert full.passed
assert full.failed_frames == ()
assert partial.failed
assert partial.failed_frames == (4, 8, 12)

full_tracking = full.measurements["tracking"]
partial_tracking = partial.measurements["tracking"]

assert full_tracking["track_count"] == 19
assert full_tracking["observation_count"] == 41
assert full_tracking["tracks_with_gaps"] == 0

assert partial_tracking["track_count"] == 15
primary = partial_tracking["track_summaries"][0]
assert primary["track_label"] == "T001"
assert primary["missing_frames"] == [4, 8, 12]
assert primary["continuity_ratio"] == 0.8
assert primary["recovery_count"] == 3

print("V5.2 temporal regression contract passed.")
'@

    $temporary_file_obj = New-TemporaryFile

    try {
        Set-Content `
            -LiteralPath $temporary_file_obj.FullName `
            -Value $regression_code_str `
            -Encoding UTF8

        & uv run python $temporary_file_obj.FullName
        Assert-CommandSucceeded `
            -CommandName "V5.2 temporal regression"
    }
    finally {
        Remove-Item `
            -LiteralPath $temporary_file_obj.FullName `
            -Force `
            -ErrorAction SilentlyContinue
    }
}

$repository_path_obj = Resolve-RepositoryPath
Set-Location $repository_path_obj

Write-Host "Visual Verifier V5.2 - temporal release gate" `
    -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "validate_release.ps1")
if (-not $?) {
    throw "Base release validation failed."
}

Invoke-TemporalRegression

Write-Host "V5.2 release validation completed successfully." `
    -ForegroundColor Green
