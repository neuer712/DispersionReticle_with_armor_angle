@echo off
setlocal

set PY27=C:\Python27\python.exe

if not exist "%PY27%" (
    echo Python 2.7 not found at %PY27% - install it or edit this script's PY27 path.
    exit /b 1
)

"%PY27%" "%~dp0build_wotmod.py" %*
