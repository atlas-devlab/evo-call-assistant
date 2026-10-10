@echo off
setlocal
cd /d "%~dp0"
echo Questo passaggio scarica i componenti audio da PyPI in una cartella .venv locale.
echo Non servono privilegi di amministratore. Richiede Internet.
py -3.12 -c "import struct, tkinter; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install --only-binary=:all: -r requirements-audio.txt
if errorlevel 1 goto failed
echo.
echo Componenti installati. Ora esegui PREPARA_VOCE.bat una sola volta.
pause
exit /b 0
:missing
echo Manca Python 3.12 a 64 bit con Tcl/Tk e Python Launcher.
echo Scaricalo dal sito ufficiale https://www.python.org/downloads/windows/
pause
exit /b 1
:failed
echo Installazione non completata. Leggi l'errore qui sopra.
echo Puoi comunque usare la demo con Python 3.12.
pause
exit /b 1
