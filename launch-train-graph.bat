@echo off
REM launch-train-graph.bat — wraps the PowerShell launcher for double‑click

pushd "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python is not installed or not in PATH.
    echo Please install Python 3 and try again.
    pause
    popd
    goto :eof
)

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\launch-train-graph.ps1" %*

popd
