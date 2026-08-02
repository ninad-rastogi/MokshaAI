param(
    [string]$OutputPath = "deploy\certs\caddy-local-root.crt",
    [string]$ComposeProject = "moksha_ai",
    [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location $root

$output = Join-Path $root $OutputPath
$outputDir = Split-Path -Parent $output
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$composeArgs = @("compose")
if ($EnvFile -ne "") {
    $composeArgs += @("--env-file", $EnvFile)
}
$composeArgs += @("-p", $ComposeProject, "-f", "docker-compose.yml")

& docker @composeArgs up -d caddy | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not start Caddy service."
}
& docker @composeArgs cp "caddy:/data/caddy/pki/authorities/local/root.crt" $output | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Could not export Caddy local root certificate."
}

if (-not (Test-Path -LiteralPath $output)) {
    throw "Caddy local root certificate was not exported."
}

Import-Certificate -FilePath $output -CertStoreLocation Cert:\CurrentUser\Root | Out-Null

Write-Host "Trusted Moksha local Caddy CA for current Windows user:"
Write-Host $output
Write-Host "Restart Chrome after running this script."
