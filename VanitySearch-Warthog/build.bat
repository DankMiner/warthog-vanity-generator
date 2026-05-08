@echo off
REM Build VanitySearch-Warthog.exe with CUDA + MSVC.
REM Targets RTX 4070 SUPER (sm_89) by default; change CodeGeneration in
REM the .vcxproj if you have a different GPU.
REM Creator: DankMiner

setlocal
pushd "%~dp0"

set "VS=C:\Program Files\Microsoft Visual Studio\2022\Community"
set "VCVARS=%VS%\VC\Auxiliary\Build\vcvars64.bat"

if not exist "%VCVARS%" (
    echo ERROR: vcvars64.bat not found at %VCVARS%
    echo Update the VS path in this script.
    goto :err
)

call "%VCVARS%"
if errorlevel 1 goto :err

echo.
echo === Building Release ^| x64 ===
echo.

msbuild VanitySearch.sln /p:Configuration=Release /p:Platform=x64 /m /verbosity:minimal /nologo
if errorlevel 1 goto :err

if exist x64\Release\VanitySearch.exe (
    copy /Y x64\Release\VanitySearch.exe ..\VanitySearch-Warthog.exe >nul
    echo.
    echo === Built successfully ===
    echo Output: %~dp0..\VanitySearch-Warthog.exe
) else (
    echo Build completed but VanitySearch.exe is missing.
    goto :err
)

popd
endlocal
exit /b 0

:err
echo.
echo Build failed. See messages above.
popd
endlocal
exit /b 1
