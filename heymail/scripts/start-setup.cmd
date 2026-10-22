@echo off
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -X utf8 "%~dp0credential_input.py"
) else (
  python.exe -X utf8 "%~dp0credential_input.py"
)
if errorlevel 1 (
  echo.
  echo If no input window appeared, double-click start-setup-console.cmd.
  echo Requires local Windows with Python 3.10 or later. Do not paste codes into chat.
  pause
)
