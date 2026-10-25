@echo off
cd /d "%~dp0"
if exist "%~dp0Actualizador_ControladorChatGPT.exe" (
 start "" "%~dp0Actualizador_ControladorChatGPT.exe"
) else (
 powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0actualizador.ps1"
)
