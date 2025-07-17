@echo off
REM launch-train-graph.bat — wraps the PowerShell launcher for double‑click

pushd "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\launch-train-graph.ps1" %*

popd
