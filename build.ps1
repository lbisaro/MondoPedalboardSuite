# =============================================================
#  build.ps1 - Mondo PedalBoard Suite | Build Script
#  Uso: .\build.ps1 [-SkipBuild]
#
#  La version se gestiona automaticamente en version.json:
#    major   -> numero mayor (cambiar manualmente cuando corresponda)
#    release -> se incrementa automaticamente en cada build
#
#  Genera: MondoPBSuite.exe en la raiz del proyecto
# =============================================================
param(
    [switch]$SkipBuild   # Saltar el paso de PyInstaller (usa el exe ya existente)
)

$ErrorActionPreference = "Stop"

# -- Rutas ------------------------------------------------------------------
$ProjectRoot  = $PSScriptRoot
$Venv         = Join-Path $ProjectRoot ".venv\Scripts"
$PyInstaller  = Join-Path $Venv "pyinstaller.exe"
$SpecFile     = Join-Path $ProjectRoot "MondoPBSuite.spec"
$VersionFile  = Join-Path $ProjectRoot "version.json"
$ExePath      = Join-Path $ProjectRoot "MondoPBSuite.exe"

# -- Helpers ----------------------------------------------------------------
function Write-Step { param($msg) Write-Host "" ; Write-Host ">>  $msg" -ForegroundColor Cyan }
function Write-Ok   { param($msg) Write-Host "[OK]  $msg" -ForegroundColor Green }
function Write-Fail { param($msg) Write-Host "[ERR] $msg" -ForegroundColor Red; exit 1 }
function Write-Info { param($msg) Write-Host "      $msg" -ForegroundColor DarkGray }

function Invoke-Cleanup {
    param([string]$Label)
    Write-Step "Limpiando carpetas temporales ($Label)..."
    $dirsToClean = @(
        (Join-Path $ProjectRoot "build"),
        (Join-Path $ProjectRoot "dist")
    )
    foreach ($dir in $dirsToClean) {
        if (Test-Path $dir) {
            Write-Info "Eliminando $dir ..."
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 800
    Write-Ok "Limpieza completada"
}

# -- Banner -----------------------------------------------------------------
Clear-Host
Write-Host ""
Write-Host "  +==========================================+" -ForegroundColor DarkCyan
Write-Host "  |   MONDO PEDALBOARD SUITE - Build Tool   |" -ForegroundColor Cyan
Write-Host "  +==========================================+" -ForegroundColor DarkCyan
Write-Host ""

# -- 0. Leer y auto-incrementar version ------------------------------------
Write-Step "Calculando version..."

if (-not (Test-Path $VersionFile)) {
    Write-Fail "No se encontro version.json en: $VersionFile"
}

$verData  = Get-Content $VersionFile -Raw | ConvertFrom-Json
$major    = [int]$verData.major
$release  = [int]$verData.release + 1
$Version  = "$major.$release"

$verData.release = $release
$verData | ConvertTo-Json | Set-Content -Path $VersionFile -NoNewline
Write-Ok "Version: $Version  (major=$major, release=$release)"

# -- 1. Precheck ------------------------------------------------------------
Write-Step "Verificando dependencias..."

if (-not (Test-Path $PyInstaller)) {
    Write-Fail "PyInstaller no encontrado en .venv. Ejecuta: .venv\Scripts\pip install pyinstaller"
}
Write-Ok "PyInstaller : $PyInstaller"

# -- 2. Build ---------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Step "Compilando ejecutable con PyInstaller..."
    Write-Info "Esto puede tardar 2-4 minutos (modo onefile)..."

    Invoke-Cleanup "pre-build"

    # --distpath apunta a la raiz del proyecto -> MondoPBSuite.exe queda ahi directamente
    & $PyInstaller "--noconfirm", "--distpath", $ProjectRoot, $SpecFile
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "PyInstaller fallo (exit code $LASTEXITCODE)"
    }
    if (-not (Test-Path $ExePath)) {
        Write-Fail "El ejecutable no fue generado en: $ExePath"
    }
    Write-Ok "Ejecutable generado: MondoPBSuite.exe"

    Invoke-Cleanup "post-build"
} else {
    Write-Info "[SKIP] Paso PyInstaller saltado (-SkipBuild)"
    if (-not (Test-Path $ExePath)) {
        Write-Fail "No existe MondoPBSuite.exe en la raiz. No podes saltar el build si no existe."
    }
}

# -- 3. Resumen final -------------------------------------------------------
Write-Host ""
Write-Host "  +==========================================+" -ForegroundColor DarkGreen
Write-Host "  |          BUILD COMPLETADO!              |" -ForegroundColor Green
Write-Host "  +==========================================+" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  Version  : v$Version" -ForegroundColor Yellow
Write-Host "  Ejecutable: MondoPBSuite.exe" -ForegroundColor Yellow
Write-Host "  user_data: compartida con el entorno de desarrollo" -ForegroundColor DarkGray
Write-Host ""
