@echo off
call "%~dp0find-python.cmd"
if errorlevel 1 exit /b 1
%HEYMAIL_PYTHON% -X utf8 "%~dp0credential_input.py" --console
echo.
echo Return to chat after saving. Next: upload your resume, then provide the sender email.
pause
