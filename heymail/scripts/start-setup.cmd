@echo off
call "%~dp0find-python.cmd"
if errorlevel 1 exit /b 1
%HEYMAIL_PYTHON% -X utf8 "%~dp0credential_input.py" --launch
if errorlevel 1 (
  echo.
  echo If no input window appeared, double-click start-setup-console.cmd.
  echo Requires local Windows with Python 3.10 or later. Do not paste codes into chat.
  pause
)
