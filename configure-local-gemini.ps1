param(
    [ValidateSet("Save", "Load", "Status")]
    [string]$Action = "Save",
    [switch]$Replace
)

$ErrorActionPreference = "Stop"
if ($env:OS -ne "Windows_NT") {
    throw "This local helper uses Windows DPAPI. On other systems, supply GEMINI_API_KEY through a private environment."
}
$directory = Join-Path $env:LOCALAPPDATA "STYL\AI"
$keyPath = Join-Path $directory "gemini-key.dpapi"
foreach ($path in @((Join-Path $env:LOCALAPPDATA "STYL"), $directory, $keyPath)) {
    if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw "The local AI secret path must not use filesystem links."
    }
}

if ($Action -eq "Status") {
    if (Test-Path -LiteralPath $keyPath -PathType Leaf) {
        Write-Output "Gemini key: stored encrypted for this Windows user. API connectivity is not yet verified."
    } else {
        Write-Output "Gemini key: not configured."
    }
    return
}

if ($Action -eq "Load") {
    if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
        throw "No private Gemini key is configured. Run configure-local-gemini.ps1 -Action Save first."
    }
    $secure = ConvertTo-SecureString ([IO.File]::ReadAllText($keyPath).Trim())
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
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
Set-Acl -LiteralPath $directory -AclObject $acl
$secure = Read-Host "Paste the full Gemini API key (hidden; never paste it into chat)" -AsSecureString
$temporary = Join-Path $directory ("key-" + [guid]::NewGuid().ToString("N") + ".tmp")
try {
    if ($secure.Length -lt 20 -or $secure.Length -gt 512) {
        throw "The key length is invalid. Copy the complete key from Google AI Studio."
    }
    [IO.File]::WriteAllText($temporary, (ConvertFrom-SecureString $secure))
    if (Test-Path -LiteralPath $keyPath) {
        [IO.File]::Replace($temporary, $keyPath, $null)
    } else {
        [IO.File]::Move($temporary, $keyPath)
    }
    Write-Output "Gemini key saved using Windows-user encryption outside Git and OneDrive. No API call or billing change was made."
} finally {
    $secure.Dispose()
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary
    }
}
