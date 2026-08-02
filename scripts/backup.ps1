param(
    [string]$Destination = "backups",
    [string]$Database = $env:POSTGRES_DB,
    [string]$DatabaseUser = $env:POSTGRES_USER
)

$ErrorActionPreference = "Stop"
if (-not $Database) { $Database = "moksha" }
if (-not $DatabaseUser) { $DatabaseUser = "moksha_user" }
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backupRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Destination))
if (-not $backupRoot.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Backup destination must stay inside project root."
}
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $backupRoot $stamp
[System.IO.Directory]::CreateDirectory($target) | Out-Null

$databasePath = Join-Path $target "database.dump"
$arguments = @(
    "compose", "exec", "-T", "db",
    "pg_dump", "-Fc", "-U", $DatabaseUser, "-d", $Database
)
$process = Start-Process -FilePath "docker" -ArgumentList $arguments `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput $databasePath
if ($process.ExitCode -ne 0) {
    throw "Database backup failed with exit code $($process.ExitCode)."
}

$dataPath = Join-Path $projectRoot "data"
if (Test-Path -LiteralPath $dataPath) {
    Compress-Archive -LiteralPath $dataPath -DestinationPath (Join-Path $target "data.zip")
}
@{
    created_at = (Get-Date).ToUniversalTime().ToString("o")
    database = $Database
    includes_data = (Test-Path -LiteralPath (Join-Path $target "data.zip"))
    excludes_secrets = $true
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $target "manifest.json") -Encoding utf8

Write-Output "Backup created at $target"
Write-Output "BYOK keyring is intentionally excluded; back it up in an encrypted secret store."
