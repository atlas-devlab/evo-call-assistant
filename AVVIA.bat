@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
py -3.12 -c "import tkinter" >nul 2>&1
if errorlevel 1 goto missing
py -3.12 run.py
if errorlevel 1 pause
exit /b
:venv
".venv\Scripts\python.exe" run.py
if errorlevel 1 pause
exit /b
:missing
echo Installa Python 3.12 a 64 bit, includendo Tcl/Tk e Python Launcher.
echo Usa il sito ufficiale https://www.python.org/downloads/windows/
echo Poi riapri AVVIA.bat. La demo non richiede altre installazioni.
pause
exit /b 1
