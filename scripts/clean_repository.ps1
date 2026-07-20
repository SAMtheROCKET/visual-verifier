<#
.SYNOPSIS
Removes generated artifacts and unsupported placeholder modules.

.DESCRIPTION
Cleans only known active-repository paths. The historical
archive/legacy_cells directory is never modified.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$GENERATED_RELATIVE_PATHS = @(
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".coverage",
    "coverage.xml",
    "htmlcov",
    "build",
    "dist",
    "src/visual_verifier.egg-info"
)

$PLACEHOLDER_RELATIVE_PATHS = @(
    "src/visual_verifier/pipeline/batch_pipeline.py",
    "src/visual_verifier/integrations/pytest_plugin.py",
    "src/visual_verifier/policies/base.py",
    "src/visual_verifier/policies/generic_change.py",
    "src/visual_verifier/policies/privacy_blur.py",
    "src/visual_verifier/targets/auto_provider.py",
    "src/visual_verifier/targets/csv_provider.py",
    "src/visual_verifier/targets/interpolation.py",
    "src/visual_verifier/targets/validation.py",
    "src/visual_verifier/tracking/iou_tracker.py",
    "src/visual_verifier/tracking/track_analysis.py"
)

$ACTIVE_DIRECTORY_NAMES = @(
    ".github",
    "benchmarks",
    "docs",
    "examples",
    "notebooks",
    "scripts",
    "src",
    "tests"
)

function Resolve-RepositoryPath {
    <#
    .SYNOPSIS
    Resolves the repository directory containing the scripts folder.
    #>

    $repository_path_obj = Split-Path -Parent $PSScriptRoot
    return (Resolve-Path $repository_path_obj).Path
}

function Remove-KnownPath {
    <#
    .SYNOPSIS
    Removes one known generated or placeholder path when it exists.

    .PARAMETER RepositoryPath
    Absolute repository root path.

    .PARAMETER RelativePath
    Repository-relative path approved for deletion.
    #>

    param(
        [Parameter(Mandatory)]
        [string] $RepositoryPath,

        [Parameter(Mandatory)]
        [string] $RelativePath
    )

    $target_path_obj = Join-Path $RepositoryPath $RelativePath
    if (Test-Path $target_path_obj) {
        Remove-Item $target_path_obj -Recurse -Force
        Write-Host "Removed: $RelativePath"
    }
}

function Remove-ActivePythonCaches {
    <#
    .SYNOPSIS
    Removes Python bytecode only from active repository directories.

    .PARAMETER RepositoryPath
    Absolute repository root path.
    #>

    param(
        [Parameter(Mandatory)]
        [string] $RepositoryPath
    )

    foreach ($directory_name_str in $ACTIVE_DIRECTORY_NAMES) {
        $active_path_obj = Join-Path (
            $RepositoryPath
        ) $directory_name_str

        if (-not (Test-Path $active_path_obj)) {
            continue
        }

        Get-ChildItem `
            -Path $active_path_obj `
            -Directory `
            -Recurse `
            -Filter "__pycache__" |
            Remove-Item -Recurse -Force

        Get-ChildItem `
            -Path $active_path_obj `
            -File `
            -Recurse `
            -Include "*.pyc", "*.pyo" |
            Remove-Item -Force
    }
}

function Clear-ExampleOutputs {
    <#
    .SYNOPSIS
    Removes generated example outputs while preserving `.gitkeep`.

    .PARAMETER RepositoryPath
    Absolute repository root path.
    #>

    param(
        [Parameter(Mandatory)]
        [string] $RepositoryPath
    )

    $output_path_obj = Join-Path (
        $RepositoryPath
    ) "examples/outputs"

    if (-not (Test-Path $output_path_obj)) {
        return
    }

    Get-ChildItem -Path $output_path_obj -Force |
        Where-Object { $_.Name -ne ".gitkeep" } |
        Remove-Item -Recurse -Force
}

$repository_path_obj = Resolve-RepositoryPath
Set-Location $repository_path_obj

Write-Host "Visual Verifier - repository cleanup" `
    -ForegroundColor Cyan
Write-Host "Repository: $repository_path_obj"
Write-Host "Historical archive remains untouched."

foreach ($relative_path_str in $GENERATED_RELATIVE_PATHS) {
    Remove-KnownPath `
        -RepositoryPath $repository_path_obj `
        -RelativePath $relative_path_str
}

foreach ($relative_path_str in $PLACEHOLDER_RELATIVE_PATHS) {
    Remove-KnownPath `
        -RepositoryPath $repository_path_obj `
        -RelativePath $relative_path_str
}

Remove-ActivePythonCaches `
    -RepositoryPath $repository_path_obj
Clear-ExampleOutputs `
    -RepositoryPath $repository_path_obj

Write-Host "Repository cleanup completed." `
    -ForegroundColor Green
