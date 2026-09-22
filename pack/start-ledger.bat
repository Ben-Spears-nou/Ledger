@echo off
setlocal EnableExtensions
rem Team-lead start script. Works from a packed copy (this file next to
rem pyproject.toml) or from pack\ in the git repo (uses the repo root).

set "HERE=%~dp0"
if exist "%HERE%pyproject.toml" (
  cd /d "%HERE%"
) else if exist "%HERE%..\pyproject.toml" (
  cd /d "%HERE%.."
) else (
  echo Could not find pyproject.toml next to this script or in the parent folder.
  exit /b 1
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
set "PREPARE=%CD%\prepare_instance.py"
if not exist "%PREPARE%" set "PREPARE=%CD%\pack\prepare_instance.py"

if not exist "%VENV_PY%" (
  echo Creating .venv ...
  python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
  if errorlevel 1 (
    echo Need Python 3.11 or newer on PATH.
    exit /b 1
  )
  python -m venv .venv
  if errorlevel 1 exit /b 1
  "%VENV_PY%" -m pip install --upgrade pip --extra-index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org
  if errorlevel 1 exit /b 1
  "%VENV_PY%" -m pip install "setuptools>=68" wheel --extra-index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org
  if errorlevel 1 exit /b 1
  "%VENV_PY%" -m pip install --no-build-isolation -e . --extra-index-url https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org
  if errorlevel 1 exit /b 1
)

"%VENV_PY%" "%PREPARE%"
if errorlevel 1 exit /b 1
"%VENV_PY%" tasks.py db-init
if errorlevel 1 exit /b 1
"%VENV_PY%" tasks.py run
exit /b %ERRORLEVEL%
