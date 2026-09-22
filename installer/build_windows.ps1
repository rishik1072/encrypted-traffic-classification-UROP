$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Encrypted Traffic Monitor - Split Windows Package Build" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "[*] Project root: $ProjectRoot"

# ------------------------------------------------------------------
# 1. Check Python
# ------------------------------------------------------------------
Write-Host "[*] Checking Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python was not found on PATH."
    exit 1
}
python --version

# ------------------------------------------------------------------
# 2. Check PyInstaller
# ------------------------------------------------------------------
Write-Host "[*] Checking PyInstaller..."
$pyinstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyinstaller) {
    Write-Host "[*] PyInstaller not found. Installing..." -ForegroundColor Yellow
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install PyInstaller."
        exit 1
    }
}
pyinstaller --version

# ------------------------------------------------------------------
# 3. Setup Staging Directories
# ------------------------------------------------------------------
$distBuildDir = Join-Path $ProjectRoot "dist_build"
$packageDir = Join-Path (Join-Path $ProjectRoot "dist") "EncryptedTrafficMonitor"

# ------------------------------------------------------------------
# ------------------------------------------------------------------
# 4. Build EncryptedTrafficDashboard.exe
# ------------------------------------------------------------------
Write-Host "`n[*] [1/2] Compiling EncryptedTrafficDashboard.exe..." -ForegroundColor Green
$dashDistPath = Join-Path $distBuildDir "dashboard"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --name "EncryptedTrafficDashboard" `
    --onedir `
    --console `
    --distpath $dashDistPath `
    --paths "." `
    --collect-all "streamlit" `
    --collect-all "altair" `
    --collect-all "tornado" `
    --collect-all "click" `
    --collect-all "dashboard" `
    --add-data "dashboard;dashboard" `
    --add-data "config;config" `
    --add-data "results/models;results/models" `
    --add-data "product/manifest.json;product" `
    --add-data "product/VERSION;product" `
    --add-data "config.yaml;." `
    product/dashboard_launcher.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build for EncryptedTrafficDashboard failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# ------------------------------------------------------------------
# 5. Build EncryptedTrafficMonitor.exe
# ------------------------------------------------------------------
Write-Host "`n[*] [2/2] Compiling EncryptedTrafficMonitor.exe..." -ForegroundColor Green
$monitorDistPath = Join-Path $distBuildDir "monitor"

python -m PyInstaller `
    --noconfirm `
    --clean `
    --name "EncryptedTrafficMonitor" `
    --onedir `
    --console `
    --distpath $monitorDistPath `
    --paths "." `
    --collect-all "scapy" `
    --collect-all "lightgbm" `
    --collect-all "sklearn" `
    --collect-all "joblib" `
    --collect-all "yaml" `
    --collect-all "dashboard" `
    --add-data "dashboard;dashboard" `
    --add-data "config;config" `
    --add-data "results/models;results/models" `
    --add-data "product/manifest.json;product" `
    --add-data "product/VERSION;product" `
    --add-data "config.yaml;." `
    product/launcher.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build for EncryptedTrafficMonitor failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

# ------------------------------------------------------------------
# 6. Assemble Unified Distribution Directory
# ------------------------------------------------------------------
Write-Host "`n[*] Assembling unified split-executable package in $packageDir..." -ForegroundColor Cyan

python -c @"
import shutil, os

project_root = r'$ProjectRoot'
dist_dir = os.path.join(project_root, 'dist', 'EncryptedTrafficMonitor')
dash_dir = os.path.join(project_root, 'dist_build', 'dashboard', 'EncryptedTrafficDashboard')
monitor_dir = os.path.join(project_root, 'dist_build', 'monitor', 'EncryptedTrafficMonitor')

os.makedirs(dist_dir, exist_ok=True)
shutil.copytree(monitor_dir, dist_dir, dirs_exist_ok=True)
shutil.copy2(os.path.join(dash_dir, 'EncryptedTrafficDashboard.exe'), os.path.join(dist_dir, 'EncryptedTrafficDashboard.exe'))

dash_internal = os.path.join(dash_dir, '_internal')
if os.path.exists(dash_internal):
    shutil.copytree(dash_internal, os.path.join(dist_dir, '_internal'), dirs_exist_ok=True)

for folder in ['dashboard', 'config']:
    src = os.path.join(project_root, folder)
    dst = os.path.join(dist_dir, folder)
    shutil.copytree(src, dst, dirs_exist_ok=True)
    # Also synchronize directly into _internal
    dst_int = os.path.join(dist_dir, '_internal', folder)
    if os.path.exists(os.path.join(dist_dir, '_internal')):
        shutil.copytree(src, dst_int, dirs_exist_ok=True)

models_src = os.path.join(project_root, 'results', 'models')
models_dst = os.path.join(dist_dir, 'results', 'models')
shutil.copytree(models_src, models_dst, dirs_exist_ok=True)

shutil.copy2(os.path.join(project_root, 'config.yaml'), os.path.join(dist_dir, 'config.yaml'))
"@

# ------------------------------------------------------------------
# 7. Verify Output
# ------------------------------------------------------------------
$monitorExe = Join-Path $packageDir "EncryptedTrafficMonitor.exe"
$dashboardExe = Join-Path $packageDir "EncryptedTrafficDashboard.exe"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Build completed successfully" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

if ((Test-Path $monitorExe) -and (Test-Path $dashboardExe)) {
    Write-Host "[+] Monitor Executable:   $monitorExe" -ForegroundColor Green
    Write-Host "[+] Dashboard Executable: $dashboardExe" -ForegroundColor Green
    
    $mSize = (Get-Item $monitorExe).Length / 1MB
    $dSize = (Get-Item $dashboardExe).Length / 1MB
    Write-Host ("[+] Monitor Size:   {0:N2} MB" -f $mSize)
    Write-Host ("[+] Dashboard Size: {0:N2} MB" -f $dSize)
} else {
    Write-Error "Build verification failed: One or both executables were not found in $packageDir."
    exit 1
}

Write-Host ""
Write-Host "[+] Windows split package is ready." -ForegroundColor Green
Write-Host ""