@echo off
setlocal ENABLEEXTENSIONS
rem Force predictable working dir = this script's folder
cd /d "%~dp0" || (echo Failed to cd into script dir & exit /b 1)

rem --- CONFIG ---
set "PYTHON=python"
set "FREEZE_SETUP=freeze_setup2.py"

rem --- CHECK PYTHON ---
where "%PYTHON%" >nul 2>nul || (
  echo Python not found in PATH.
  exit /b 1
)

rem --- PRINT ENV ---
echo [INFO] Using Python: %PYTHON%
for /f "delims=" %%V in ('%PYTHON% -c "import sys;print(sys.version)"') do set "PYVER=%%V"
echo [INFO] Python version: %PYVER%

rem --- ENSURE PIP ---
%PYTHON% -m ensurepip --upgrade >nul 2>nul
%PYTHON% -m pip --version || (
  echo [ERR ] pip not available
  exit /b 1
)

rem --- INSTALL/LOCK BUILD DEPS ---
echo [INFO] Installing build deps...
%PYTHON% -m pip install --upgrade "pip<25" wheel ^
  "setuptools<=80.9.0,>=65.6.3" ^
  "cx_Freeze==8.4.1" ^
  "PyQt5>=5.15,<5.16" ^
  "pillow" ^
  "pyscard>=2.0,<3.0" || goto :pip_fail

rem --- CLEAN ---
echo [INFO] Cleaning build/ dist/ ...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

rem --- RUN BUILD ---
echo [INFO] Building with cx_Freeze...
%PYTHON% "%FREEZE_SETUP%" build || goto :build_fail

echo.
echo [OK] Build finished.
echo [INFO] Contents of dist:
dir /b /s dist
echo.
pause
exit /b 0

:pip_fail
echo [ERR ] pip install failed.
exit /b 1

:build_fail
echo [ERR ] cx_Freeze build failed.
exit /b 1
