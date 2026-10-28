@echo off
set "HEYMAIL_PYTHON="
where py.exe >nul 2>nul
if not errorlevel 1 (
  set "HEYMAIL_PYTHON=py.exe -3"
  exit /b 0
)
where python.exe >nul 2>nul
if not errorlevel 1 (
  set "HEYMAIL_PYTHON=python.exe"
  exit /b 0
)
if exist "%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe" (
  set HEYMAIL_PYTHON="%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
  exit /b 0
)
echo Python 3.10+ is required. Ask your agent to locate its Python runtime.
exit /b 1
