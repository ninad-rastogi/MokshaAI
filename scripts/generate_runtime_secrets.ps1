param(
    [string]$OutputDirectory = "deploy/runtime-secrets"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$target = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
if (-not $target.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output directory must stay inside project root."
}
[System.IO.Directory]::CreateDirectory($target) | Out-Null

function New-UrlSafeSecret([int]$ByteCount) {
    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($bytes)
    }
    finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_")
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$keyringPath = Join-Path $target "byok-keyring.json"
if (Test-Path -LiteralPath $keyringPath) {
    throw "BYOK keyring already exists. Refusing to overwrite it."
}
$keyring = @{
    active_version = 1
    keys = @{
        "1" = New-UrlSafeSecret 32
    }
}
Write-Utf8NoBom $keyringPath ($keyring | ConvertTo-Json -Depth 4)

$hostPath = $keyringPath.Replace("\", "/")
$environmentPath = Join-Path $target "runtime.env"
$environment = @(
    "DJANGO_SECRET_KEY=$(New-UrlSafeSecret 64)"
    "POSTGRES_PASSWORD=$(New-UrlSafeSecret 32)"
    "MOKSHA_METRICS_TOKEN=$(New-UrlSafeSecret 32)"
    "MOKSHA_BYOK_KEYRING_HOST_FILE=$hostPath"
)
Write-Utf8NoBom $environmentPath (($environment -join [Environment]::NewLine) + [Environment]::NewLine)

Write-Output "Created $keyringPath"
Write-Output "Created $environmentPath"
Write-Output "Back up both files in an encrypted secret store before adding BYOK keys."
