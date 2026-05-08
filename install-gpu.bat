@echo off
REM Optional GPU support via pyopencl (used for the GPU detection check).
REM Creator: DankMiner   v1.0.0
REM
REM NOTE: Real end-to-end GPU vanity scanning (EC point multiplication
REM       on the GPU) requires VanitySearch-Warthog.exe, built from the
REM       VanitySearch-Warthog/ source tree using build.bat. pyopencl is
REM       only used by the GUI to display "GPU device: <name>".
setlocal
pushd "%~dp0"

set PY=py -3
where py >nul 2>&1
if not %errorlevel%==0 set PY=python

echo Installing pyopencl...
%PY% -m pip install --only-binary=:all: pyopencl numpy
if errorlevel 1 (
    echo.
    echo No prebuilt pyopencl wheel for this Python.
    echo Try Python 3.11 or 3.12, or grab a wheel from
    echo https://www.lfd.uci.edu/~gohlke/pythonlibs/
)

popd
endlocal
pause
