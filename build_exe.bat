@echo off
REM build_exe.bat — Clean build a Windows EXE via cx_Freeze (and optional MSI)

setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >NUL

REM --- Configuration ----------------------------------------------------------
REM Allow overrides: set PYTHON_BIN=C:\Path\To\python.exe
set "PYTHON_BIN=%PYTHON_BIN%"
if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"

set "APP_NAME=AnycubicNFCTaggerQT5"
set "ENTRY_EXE=%APP_NAME%.exe"
set "BUILD_DIR=build"
set "DIST_DIR=dist"
set "DO_MSI=%DO_MSI%"
if "%DO_MSI%"=="" set "DO_MSI=1"

REM --- Helpers ----------------------------------------------------------------
set "ESC="
for /F "delims=" %%A in ('echo prompt $E^| cmd') do set "ESC=%%A"
set "INFO=%ESC%[1;34m[INFO]%ESC%[0m"
set "WARN=%ESC%[1;33m[WARN]%ESC%[0m"
set "ERR =%ESC%[1;31m[ERR ]%ESC%[0m"

echo %INFO% Using Python: %PYTHON_BIN%

REM --- Checks: python present -------------------------------------------------
where "%PYTHON_BIN%" >NUL 2>&1
if errorlevel 1 (
  echo %ERR % Python not found. Set PYTHON_BIN to a valid Python 3.11/3.12 interpreter.
  exit /b 1
)

REM --- Checks: ensure cx_Freeze and PyQt5 installed --------------------------
"%PYTHON_BIN%" -c "import cx_Freeze" >NUL 2>&1
if errorlevel 1 (
  echo %WARN% cx_Freeze not found. Installing...
  "%PYTHON_BIN%" -m pip install -U cx_Freeze || (echo %ERR % Failed to install cx_Freeze & exit /b 1)
)

"%PYTHON_BIN%" -c "import PyQt5" >NUL 2>&1
if errorlevel 1 (
  echo %WARN% PyQt5 not found. Installing...
  "%PYTHON_BIN%" -m pip install -U PyQt5 || (echo %ERR % Failed to install PyQt5 & exit /b 1)
)

REM --- Read version from pyproject.toml (fallback 0.3.0) ----------------------
set "VERSION=0.3.0"
for /f "usebackq delims=" %%V in (`
  "%PYTHON_BIN%" -c "import pathlib,sys; 
try:
 import tomllib as tl
except Exception:
 import tomli as tl
 p=pathlib.Path('pyproject.toml')
 print(tl.loads(p.read_text(encoding='utf-8')).get('project',{}).get('version','0.3.0'))"
`) do set "VERSION=%%V"
echo %INFO% Project version: %VERSION%

REM --- Try to close any running instance -------------------------------------
echo %INFO% Closing running app if present...
taskkill /IM "%ENTRY_EXE%" /F >NUL 2>&1

REM --- Clean previous build/dist ---------------------------------------------
if exist "%BUILD_DIR%" (
  echo %INFO% Removing "%BUILD_DIR%"...
  rmdir /S /Q "%BUILD_DIR%" || (
    echo %WARN% First removal attempt failed; retrying...
    timeout /t 1 >NUL
    rmdir /S /Q "%BUILD_DIR%" || (echo %ERR % Could not remove build directory & exit /b 1)
  )
)

if exist "%DIST_DIR%" (
  echo %INFO% Removing "%DIST_DIR%"...
  rmdir /S /Q "%DIST_DIR%" || (
    echo %WARN% First removal attempt failed; retrying...
    timeout /t 1 >NUL
    rmdir /S /Q "%DIST_DIR%" || (echo %ERR % Could not remove dist directory & exit /b 1)
  )
)

REM --- Build portable EXE -----------------------------------------------------
echo %INFO% Building EXE via cx_Freeze (build_exe)...
"%PYTHON_BIN%" freeze_setup.py build_exe
if errorlevel 1 (
  echo %ERR % Build failed (build_exe).
  exit /b 1
)

REM --- Locate built EXE -------------------------------------------------------
set "FOUND_EXE="
for /r "%BUILD_DIR%" %%F in ("%ENTRY_EXE%") do (
  set "FOUND_EXE=%%F"
  goto :found_exe
)
:found_exe

if "%FOUND_EXE%"=="" (
  echo %WARN% Could not find "%ENTRY_EXE%" under "%BUILD_DIR%". Listing build tree:
  dir /S /B "%BUILD_DIR%"
) else (
  echo %INFO% Built EXE: "%FOUND_EXE%"
)

REM --- Optional: Build MSI installer -----------------------------------------
if "%DO_MSI%"=="1" (
  echo %INFO% Building MSI installer (bdist_msi)...
  "%PYTHON_BIN%" freeze_setup.py bdist_msi
  if errorlevel 1 (
    echo %WARN% MSI build failed. You can disable MSI by setting DO_MSI=0
  ) else (
    echo %INFO% MSI created under "%DIST_DIR%"
  )
) else (
  echo %INFO% Skipping MSI build (DO_MSI=0)
)

REM --- Done -------------------------------------------------------------------
echo %INFO% Done.
echo.
echo Portable EXE under: "%BUILD_DIR%"
if "%DO_MSI%"=="1" echo MSI package (if successful) under: "%DIST_DIR%"
echo.
echo To run:
if not "%FOUND_EXE%"=="" echo   "%FOUND_EXE%"

exit /b 0