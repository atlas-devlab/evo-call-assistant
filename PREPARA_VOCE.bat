@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" prepara_voce.py
if errorlevel 1 goto failed
echo Modello pronto. Avvia AVVIA.bat.
pause
exit /b 0
:missing
echo Esegui prima INSTALLA_AUDIO.bat.
pause
exit /b 1
:failed
echo Preparazione non completata. Leggi l'errore qui sopra e riprova.
pause
exit /b 1
