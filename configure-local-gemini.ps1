param(
    [ValidateSet("Save", "Load", "Status")]
    [string]$Action = "Save",
    [switch]$Replace
)

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "configure-local-ai.ps1") -Provider Gemini -Action $Action -Replace:$Replace
