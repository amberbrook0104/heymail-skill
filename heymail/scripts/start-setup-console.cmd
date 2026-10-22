@echo off
where py.exe >nul 2>nul
if not errorlevel 1 (
  py.exe -3 -X utf8 "%~dp0credential_input.py" --console
) else (
  python.exe -X utf8 "%~dp0credential_input.py" --console
)
echo.
echo Return to chat after saving. Next: upload your resume, then provide the sender email.
pause
