<#
.SYNOPSIS
Runs the final Visual Verifier release validation.

.DESCRIPTION
Cleans the repository, verifies the lock file, runs all quality checks,
builds distributions, and inspects the wheel contents.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$REQUIRED_WHEEL_PATHS = @(
    "visual_verifier/__init__.py",
    "visual_verifier/api.py",
    "visual_verifier/cli.py",
    "visual_verifier/py.typed",
    "visual_verifier/media/video_writer.py",
    "visual_verifier/tracking/association.py",
    "visual_verifier/tracking/tracker.py",
    "visual_verifier/tracking/analysis.py",
    "visual_verifier/tracking/events.py",
    "visual_verifier/reporting/track_report.py",
    "visual_verifier/reporting/console.py"
)

$FORBIDDEN_WHEEL_FRAGMENTS = @(
    "__pycache__",
    ".pyc",
    "archive/",
    "tests/",
    "batch_pipeline.py",
    "pytest_plugin.py",
    "policies/base.py",
    "targets/auto_provider.py",
    "tracking/iou_tracker.py"
)

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

function Assert-WheelContents {
    <#
    .SYNOPSIS
    Confirms required wheel files and rejects forbidden paths.
    #>

    param(
        [Parameter(Mandatory)]
        [System.IO.FileInfo] $WheelFile
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive_obj = [System.IO.Compression.ZipFile]::OpenRead(
        $WheelFile.FullName
    )

    try {
        $entry_names_list = @(
            $archive_obj.Entries |
                ForEach-Object { $_.FullName }
        )
        foreach ($required_path_str in $REQUIRED_WHEEL_PATHS) {
            if ($required_path_str -notin $entry_names_list) {
                throw "Wheel is missing $required_path_str"
            }
        }
        foreach ($fragment_str in $FORBIDDEN_WHEEL_FRAGMENTS) {
            $invalid_entry_obj = $entry_names_list |
                Where-Object { $_ -like "*$fragment_str*" } |
                Select-Object -First 1
            if ($null -ne $invalid_entry_obj) {
                throw (
                    "Wheel contains forbidden path " +
                    "$invalid_entry_obj"
                )
            }
        }
    }
    finally {
        $archive_obj.Dispose()
    }
}

$repository_path_obj = Resolve-RepositoryPath
Set-Location $repository_path_obj

Write-Host "Visual Verifier - release validation" `
    -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "clean_repository.ps1")
if (-not $?) {
    throw "Repository cleanup failed."
}

& uv sync --locked
Assert-CommandSucceeded -CommandName "uv sync --locked"

& (Join-Path $PSScriptRoot "run_quality.ps1")
if (-not $?) {
    throw "Quality gate failed."
}

& uv run visual-verifier doctor
Assert-CommandSucceeded -CommandName "visual-verifier doctor"

& uv run python -m build
Assert-CommandSucceeded -CommandName "package build"

$wheel_files_list = @(
    Get-ChildItem `
        -Path (Join-Path $repository_path_obj "dist") `
        -Filter "*.whl"
)

if ($wheel_files_list.Count -ne 1) {
    throw (
        "Expected exactly one wheel, found " +
        "$($wheel_files_list.Count)."
    )
}

Assert-WheelContents -WheelFile $wheel_files_list[0]

Write-Host "Release validation completed successfully." `
    -ForegroundColor Green
