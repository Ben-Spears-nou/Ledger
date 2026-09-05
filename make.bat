@echo off
REM Windows stand-in for `make <target>` (Git Bash / GNU make are optional).
if "%PYTHON%"=="" (
  if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
  ) else (
    set "PYTHON=python"
  )
)
"%PYTHON%" tasks.py %*
