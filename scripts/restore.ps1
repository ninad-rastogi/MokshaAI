param(
    [Parameter(Mandatory = $true)]
    [string]$BackupDirectory,
    [switch]$ConfirmRestore,
    [string]$Database = $env:POSTGRES_DB,
    [string]$DatabaseUser = $env:POSTGRES_USER
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) {
    throw "Restore changes the active database. Re-run with -ConfirmRestore."
}
if (-not $Database) { $Database = "moksha" }
if (-not $DatabaseUser) { $DatabaseUser = "moksha_user" }
$source = (Resolve-Path -LiteralPath $BackupDirectory).Path
$databasePath = Join-Path $source "database.dump"
if (-not (Test-Path -LiteralPath $databasePath -PathType Leaf)) {
    throw "Backup database.dump is missing."
}

& (Join-Path $PSScriptRoot "backup.ps1") -Destination "backups/pre-restore"
docker compose stop django worker generation-worker model-installer scheduler
try {
    $arguments = @(
        "compose", "exec", "-T", "db",
        "pg_restore", "--clean", "--if-exists",
        "-U", $DatabaseUser, "-d", $Database
    )
    $process = Start-Process -FilePath "docker" -ArgumentList $arguments `
        -NoNewWindow -Wait -PassThru -RedirectStandardInput $databasePath
    if ($process.ExitCode -ne 0) {
        throw "Database restore failed with exit code $($process.ExitCode)."
    }
    $dataArchive = Join-Path $source "data.zip"
    if (Test-Path -LiteralPath $dataArchive -PathType Leaf) {
        $projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
        Expand-Archive -LiteralPath $dataArchive -DestinationPath $projectRoot -Force
    }
}
finally {
    docker compose start django worker generation-worker model-installer scheduler
}
Write-Output "Restore completed from $source"
