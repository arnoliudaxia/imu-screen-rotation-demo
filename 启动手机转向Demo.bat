@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv not found. Install uv and Python first.
  pause
  exit /b 1
)
uv run python -m imu_reader.phone_demo
if errorlevel 1 pause
endlocal
