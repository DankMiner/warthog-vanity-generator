@echo off
REM Warthog Vanity Generator - CLI launcher
REM Creator: DankMiner   v1.0.0
setlocal
pushd "%~dp0"

set PY=py -3
where py >nul 2>&1
if not %errorlevel%==0 set PY=python

%PY% warthog_cli.py %*

popd
endlocal
