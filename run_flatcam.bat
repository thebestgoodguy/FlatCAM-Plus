@echo off
setlocal
cd /d %~dp0
echo Starting FlatCAM Plus...
python flatcam.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo FlatCAM exited with error code %ERRORLEVEL%
    pause
)
