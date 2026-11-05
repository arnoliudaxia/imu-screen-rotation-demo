@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Install uv and Python, then try again.
  echo https://docs.astral.sh/uv/getting-started/installation/
  pause
  exit /b 1
)
uv run python -m imu_reader
if errorlevel 1 (
  echo Launch failed. See the error above.
  pause
)
endlocal
