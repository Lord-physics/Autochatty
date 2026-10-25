@echo off
cd /d "%~dp0"
if exist "%~dp0ControladorChatGPT.exe" (
 start "" "%~dp0ControladorChatGPT.exe"
 exit /b 0
)
start "" pyw -3 "%~dp0controller.py"
if errorlevel 1 ( echo Instala Python 3.11 y ejecuta instalar.bat & pause )
