param(
    [switch]$SkipBuild,
    [switch]$UseConfiguredBackend
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$composeCommand = @("compose")
Push-Location $repositoryRoot

try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker no esta instalado o no esta disponible en PATH."
    }

    docker info --format '{{.ServerVersion}}' | Out-Null
    if (-not $UseConfiguredBackend) {
        $composeCommand += @("-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml")
    }
    & docker @composeCommand config --quiet
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config no termino correctamente."
    }

    $composeArguments = $composeCommand + @("up", "-d", "--wait")
    if (-not $SkipBuild) {
        $composeArguments += "--build"
    }
    & docker @composeArguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose up no termino correctamente."
    }

    $expectedServices = @("api", "db", "web", "worker")
    $runningServices = @(& docker @composeCommand ps --services --filter status=running)
    $missingServices = @($expectedServices | Where-Object { $_ -notin $runningServices })
    if ($missingServices.Count -gt 0) {
        throw "Servicios no activos: $($missingServices -join ', ')"
    }

    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health"
    if ($health.status -ne "ok") {
        throw "La API no respondio con estado ok."
    }
    $catalog = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/demo/agencies"
    if (@($catalog.agencies).Count -lt 2) {
        throw "El catalogo no contiene las dos agencias de demostracion."
    }
    Write-Host ""
    Write-Host "PRE-FLIGHT OK" -ForegroundColor Green
    Write-Host "Aplicacion: http://localhost:5173"
    Write-Host "API/Swagger: http://localhost:8000/docs"
    Write-Host "Agencias configuradas: $(@($catalog.agencies).Count)"
    Write-Host "Extractor: $(if ($UseConfiguredBackend) { 'configurado en .env' } else { 'local determinista' })"
    Write-Host "Para las cifras conocidas, seleccione IMR Demo y luego Escenario A."
}
catch {
    Write-Host ""
    Write-Host "PRE-FLIGHT FALLO: $($_.Exception.Message)" -ForegroundColor Red
    & docker @composeCommand ps
    throw
}
finally {
    Pop-Location
}
