@echo off
REM Warthog Vanity Generator v1.0.0
REM Creator: DankMiner
REM
REM Installs the baseline (ecdsa + pycryptodome) plus the optional fast
REM EC backend (coincurve). The tool falls back gracefully if coincurve
REM has no prebuilt wheel for your Python version.
setlocal
pushd "%~dp0"

set PY=py -3
where py >nul 2>&1
if not %errorlevel%==0 set PY=python

echo.
echo === [1/4] Upgrading pip ===
%PY% -m pip install --upgrade pip

echo.
echo === [2/4] Baseline: ecdsa + pycryptodome (fast RIPEMD-160) ===
%PY% -m pip install ecdsa pycryptodome
if errorlevel 1 goto :err

echo.
echo === [3/4] Optional: Pillow (logo + multi-res icon support) ===
%PY% -m pip install --only-binary=:all: Pillow
if errorlevel 1 (
    echo     No Pillow wheel - the GUI still works, but the logo will use
    echo     a stylized canvas fallback instead of warthog_logo.png.
)

echo.
echo === [4/4] Optional: coincurve (fast EC, ~30x speedup) ===
echo     This may fail on Python 3.14. That's OK - the tool falls back to ecdsa.
%PY% -m pip install --only-binary=:all: "coincurve>=18.0.0"
if errorlevel 1 (
    echo     No prebuilt wheel - skipping coincurve. ecdsa fallback will be used.
    echo     For maximum CPU speed, install Python 3.11 or 3.12 from python.org.
)

echo.
echo === Done. ===
echo Run "Warthog-Vanity.bat" to launch the GUI.
echo.

popd
endlocal
pause
exit /b 0

:err
echo.
echo BASELINE INSTALL FAILED. The tool cannot run without ecdsa.
popd
endlocal
pause
exit /b 1
