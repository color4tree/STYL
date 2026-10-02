param(
    [ValidateSet("Gemini", "OpenAI")]
    [string]$Provider = "Gemini",
    [ValidateSet("Save", "Load", "Status")]
    [string]$Action = "Save",
    [switch]$Replace
)

$ErrorActionPreference = "Stop"
$variableName = if ($Provider -eq "OpenAI") { "OPENAI_API_KEY" } else { "GEMINI_API_KEY" }
if ($env:OS -ne "Windows_NT") {
    throw "This local helper uses Windows DPAPI. On other systems, supply $variableName through a private environment."
}
$directory = Join-Path $env:LOCALAPPDATA "STYL\AI"
$keyPath = Join-Path $directory ($Provider.ToLowerInvariant() + "-key.dpapi")
foreach ($path in @((Join-Path $env:LOCALAPPDATA "STYL"), $directory, $keyPath)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "The local AI secret path must not use filesystem links."
    }
}

if ($Action -eq "Status") {
    if (Test-Path -LiteralPath $keyPath -PathType Leaf) {
        Write-Output "${Provider} key: stored encrypted for this Windows user. API connectivity is not yet verified."
    } else {
        Write-Output "${Provider} key: not configured."
    }
    return
}

if ($Action -eq "Load") {
    if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
        throw "No private $Provider key is configured. Run configure-local-ai.ps1 -Provider $Provider -Action Save first."
    }
    $secure = ConvertTo-SecureString ([IO.File]::ReadAllText($keyPath).Trim())
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        [Environment]::SetEnvironmentVariable($variableName, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim(), "Process")
    } finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        $secure.Dispose()
    }
    return
}

if ((Test-Path -LiteralPath $keyPath) -and -not $Replace) {
    throw "A private key already exists. Use -Replace only when intentionally replacing it."
}
$existingDirectory = Test-Path -LiteralPath $directory -PathType Container
[IO.Directory]::CreateDirectory($directory) | Out-Null
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$identities = @(
    [Security.Principal.WindowsIdentity]::GetCurrent().User,
    (New-Object Security.Principal.SecurityIdentifier "S-1-5-18"),
    (New-Object Security.Principal.SecurityIdentifier "S-1-5-32-544")
)
foreach ($identity in $identities) {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        $identity, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow"
    )))
}
if ($existingDirectory) {
    $existingAcl = Get-Acl -LiteralPath $directory
    $allowedSids = @($identities | ForEach-Object { $_.Value })
    $unexpected = @($existingAcl.Access | Where-Object {
        $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
        $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin $allowedSids
    })
    if (-not $existingAcl.AreAccessRulesProtected -or $unexpected.Count -gt 0) {
        throw "The existing AI secret directory has broader permissions than expected. Review its access before saving a key."
    }
} else {
    Set-Acl -LiteralPath $directory -AclObject $acl
}
$secure = Read-Host "Paste the full $Provider API key (hidden; never paste it into chat)" -AsSecureString
$temporary = Join-Path $directory ("key-" + [guid]::NewGuid().ToString("N") + ".tmp")
try {
    if ($secure.Length -lt 20 -or $secure.Length -gt 512) {
        throw "The key length is invalid. Copy the complete key from your $Provider developer account."
    }
    [IO.File]::WriteAllText($temporary, (ConvertFrom-SecureString $secure))
    if (Test-Path -LiteralPath $keyPath) {
        [IO.File]::Replace($temporary, $keyPath, $null)
    } else {
        [IO.File]::Move($temporary, $keyPath)
    }
    Write-Output "$Provider key saved using Windows-user encryption outside Git and OneDrive. No API call or billing change was made."
} finally {
    $secure.Dispose()
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary
    }
}
