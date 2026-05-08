@echo off
REM Warthog Vanity Generator - GUI launcher (no console window)
REM Creator: DankMiner   v1.0.0
setlocal
pushd "%~dp0"

REM Prefer pythonw.exe so no black console pops up.
set "PYW="
for /f "delims=" %%I in ('where pythonw 2^>nul') do (
    if not defined PYW set "PYW=%%I"
)
if not defined PYW (
    for /f "delims=" %%I in ('py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul') do (
        if exist "%%I" set "PYW=%%I"
    )
)

if defined PYW (
    start "" "%PYW%" warthog_gui.py
) else (
    REM Last resort: regular python (will show a console)
    start "" py -3 warthog_gui.py
)

popd
endlocal
