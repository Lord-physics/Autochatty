@echo off
cd /d "%~dp0"
echo Instalando dependencias para la aplicacion oficial de ChatGPT para Windows...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
 echo Error de instalacion. Necesitas Python 3.11 o superior.
 pause
 exit /b 1
)
echo Instalacion completada. No se necesita Edge ni Playwright.
pause
