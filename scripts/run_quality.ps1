<#
.SYNOPSIS
Runs the complete Visual Verifier quality gate.

.DESCRIPTION
Checks formatting, linting, static types, and tests without installing Python,
synchronizing dependencies, or modifying repository files.
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PYTHON_VERSION_TEXT = "3.12"
$SOURCE_DIRECTORY_NAME = "src"

function Resolve-RepositoryPath {
    <#
    .SYNOPSIS
    Resolves the repository directory containing the scripts folder.
    #>

    $repository_path_obj = Split-Path -Parent $PSScriptRoot
    return (Resolve-Path $repository_path_obj).Path
}

function Assert-UvAvailable {
    <#
    .SYNOPSIS
    Confirms that uv is available on the current PATH.
    #>

    $uv_command_obj = Get-Command uv -ErrorAction SilentlyContinue
    if ($null -eq $uv_command_obj) {
        $error_message_text = (
            "uv is not installed or available on PATH. " +
            "Run scripts/bootstrap_uv.ps1 before this quality script."
        )
        throw $error_message_text
    }
}

function Invoke-UvCommand {
    <#
    .SYNOPSIS
    Runs one uv command and fails immediately on a nonzero exit code.

    .PARAMETER ArgumentList
    Ordered command-line arguments passed to uv.
    #>

    param(
        [Parameter(Mandatory)]
        [string[]] $ArgumentList
    )

    $display_command_text = "uv " + ($ArgumentList -join " ")
    Write-Host $display_command_text -ForegroundColor DarkGray

    & uv @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        $error_message_text = (
            "Command failed with exit code " +
            "$LASTEXITCODE`: $display_command_text"
        )
        throw $error_message_text
    }
}

$repository_path_obj = Resolve-RepositoryPath
Set-Location $repository_path_obj

Write-Host "Visual Verifier - quality gate" -ForegroundColor Cyan
Write-Host "Repository: $repository_path_obj"

Assert-UvAvailable

Invoke-UvCommand @(
    "run",
    "ruff",
    "format",
    "--check",
    "."
)
Invoke-UvCommand @(
    "run",
    "ruff",
    "check",
    "."
)
Invoke-UvCommand @(
    "run",
    "mypy",
    $SOURCE_DIRECTORY_NAME,
    "--python-version",
    $PYTHON_VERSION_TEXT
)
Invoke-UvCommand @(
    "run",
    "pytest",
    "-q"
)

Write-Host "All quality checks passed." -ForegroundColor Green
