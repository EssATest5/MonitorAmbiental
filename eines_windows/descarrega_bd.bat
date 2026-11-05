@echo off
chcp 65001 >nul
rem descarrega_bd.bat - Baixa al PC una còpia fresca de la base de dades de la RPi3.
rem Necessita el client SSH de Windows 10/11 (ssh i scp), que ve instal·lat.
rem Edita aquestes dues línies:
set RPI=pi@192.168.1.50
set DESTI=%USERPROFILE%\Documents\MonitorAmbiental

if not exist "%DESTI%" mkdir "%DESTI%"
echo Creant la còpia a la RPi3...
ssh %RPI% "python3 /home/pi/MonitorAmbiental/exporta_copia.py"
if errorlevel 1 goto error
echo Descarregant...
scp %RPI%:/home/pi/MonitorAmbiental/dades/copia.db "%DESTI%\sensors_copia.db"
if errorlevel 1 goto error
echo.
echo Fet: %DESTI%\sensors_copia.db
echo Obre-la amb DB Browser for SQLite.
pause
exit /b 0

:error
echo.
echo Ha fallat. Comprova la IP de la RPi3 i que funcioni: ssh %RPI%
pause
exit /b 1
