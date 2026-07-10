<#
.SYNOPSIS
    Build FlatCAM Plus standalone .exe using PyInstaller
.DESCRIPTION
    Creates a virtualenv, installs dependencies, and packages with PyInstaller.
    Skips: svgtrace (needs greenlet which fails on Python 3.13), gdal, rasterio.
#>
$ErrorActionPreference = "Continue"
$VenvDir = "c:\temp\fcvenv"
$Python = Join-Path $VenvDir "Scripts\python.exe"
$Pip = Join-Path $VenvDir "Scripts\pip.exe"
$RootDir = $PSScriptRoot

# --- Step 1: Ensure venv exists ---
if (-not (Test-Path $Python)) {
    Write-Host "=== Step 0: Creating venv ===" -ForegroundColor Cyan
    py -3.13 -m venv $VenvDir
}

Write-Host "=== Step 1: Upgrade pip ===" -ForegroundColor Cyan
& $Python -m pip install --upgrade pip setuptools wheel 2>&1 | Select-Object -Last 3
Write-Host "pip upgrade exit code: $LASTEXITCODE"

Write-Host ""
Write-Host "=== Step 2: Install PyInstaller ===" -ForegroundColor Cyan
& $Pip install pyinstaller 2>&1 | Select-Object -Last 3
Write-Host "pyinstaller install exit code: $LASTEXITCODE"

Write-Host ""
Write-Host "=== Step 3: Install requirements ===" -ForegroundColor Cyan
# Split into batches to isolate failures.
# Batch A: Core packages (no native compilation issues)
& $Pip install numpy cycler python-dateutil kiwisolver six dill simplejson `
    "qrcode>=6.1" rtree "shapely>=2.0" lxml "svg.path>=4.0" svglib `
    fontTools ezdxf "reportlab>=3.5" "pyserial>=3.4" "pikepdf>=2.0" `
    "matplotlib>=3.5.0" pyopengl darkdetect freetype-py pyparsing pillow `
    2>&1 | Select-Object -Last 5
Write-Host "Batch A exit code: $LASTEXITCODE"

# Batch B: PyQt6
& $Pip install "PyQt6==6.11.0" "PyQt6-Qt6==6.11.0" "PyQt6-sip>=13.8,<14" `
    2>&1 | Select-Object -Last 3
Write-Host "Batch B (PyQt6) exit code: $LASTEXITCODE"

# Batch C: vispy
& $Pip install "vispy>=0.9.0" 2>&1 | Select-Object -Last 3
Write-Host "Batch C (vispy) exit code: $LASTEXITCODE"

# Batch D: OR-Tools (optional, large)
& $Pip install "ortools>=7.0" 2>&1 | Select-Object -Last 3
Write-Host "Batch D (ortools) exit code: $LASTEXITCODE"

# Skip: svgtrace (pulls playwright -> greenlet which fails on 3.13)
# Skip: pyppeteer (pulls websockets source build, optional)
# Skip: gdal, rasterio (need special wheels)

Write-Host ""
Write-Host "=== Step 4: Check key imports ===" -ForegroundColor Cyan
& $Python -c "import PyQt6; print('PyQt6 OK')"
& $Python -c "import vispy; print('vispy OK')"
& $Python -c "import shapely; print('shapely OK')"
& $Python -c "import numpy; print('numpy OK')"
& $Python -c "import matplotlib; print('matplotlib OK')"

Write-Host ""
Write-Host "=== Step 5: Run PyInstaller ===" -ForegroundColor Cyan
Set-Location $RootDir

# Use absolute paths for --add-data (source;dest format on Windows)
$assetsPath = Join-Path $RootDir "assets"
$configPath = Join-Path $RootDir "config"
$localePath = Join-Path $RootDir "locale"
$preprocessorsPath = Join-Path $RootDir "preprocessors"
$libsPath = Join-Path $RootDir "libs"

$pyInstallerArgs = @(
    "-m", "PyInstaller", "flatcam.py",
    "--name", "FlatCAMPlus",
    "--windowed",
    "--clean",
    "--noconfirm",
    "--distpath", (Join-Path $RootDir "dist\standalone"),
    "--workpath", (Join-Path $RootDir "build\pyinstaller"),
    "--specpath", (Join-Path $RootDir "build\pyinstaller"),
    "--add-data", "${assetsPath};assets",
    "--add-data", "${configPath};config",
    "--add-data", "${localePath};locale",
    "--add-data", "${preprocessorsPath};preprocessors",
    "--add-data", "${libsPath};libs",
    "--collect-submodules", "appCommon",
    "--collect-submodules", "appEditors",
    "--collect-submodules", "appGUI",
    "--collect-submodules", "appHandlers",
    "--collect-submodules", "appObjects",
    "--collect-submodules", "appParsers",
    "--collect-submodules", "appPlugins",
    "--collect-submodules", "tclCommands",
    "--collect-all", "PyQt6",
    "--collect-all", "vispy",
    "--collect-all", "shapely",
    "--collect-all", "OpenGL",
    "--collect-all", "matplotlib",
    "--collect-all", "ortools",
    "--collect-all", "google.protobuf",
    "--collect-all", "certifi",
    "--collect-all", "rasterio",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PySide2",
    "--exclude-module", "PySide6",
    "--exclude-module", "matplotlib.tests",
    "--exclude-module", "vispy.testing",
    "--exclude-module", "OpenGL.Tk"
)

& $Python @pyInstallerArgs
Write-Host "PyInstaller exit code: $LASTEXITCODE"

$exePath = Join-Path $RootDir "dist\standalone\FlatCAMPlus\FlatCAMPlus.exe"
if (Test-Path $exePath) {
    $size = [math]::Round((Get-Item $exePath).Length / 1MB, 2)
    $folderSize = [math]::Round(((Get-ChildItem -Recurse (Split-Path $exePath) | Measure-Object -Property Length -Sum).Sum) / 1MB, 0)
    Write-Host ""
    Write-Host "=== BUILD SUCCESS ===" -ForegroundColor Green
    Write-Host "Executable: $exePath"
    Write-Host "Exe size: ${size} MB"
    Write-Host "Total folder: ~${folderSize} MB"
} else {
    Write-Host ""
    Write-Host "=== BUILD FAILED ===" -ForegroundColor Red
    Write-Host "Executable not found at: $exePath"
    Write-Host "Check logs above for errors."
}
