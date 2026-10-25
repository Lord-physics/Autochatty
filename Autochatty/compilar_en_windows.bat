@echo off
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (echo Error instalando dependencias & pause & exit /b 1)
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name ControladorChatGPT --hidden-import=win32timezone --collect-submodules=pywinauto --add-data "wake_task.ps1;." controller.py
if errorlevel 1 (echo Error compilando & pause & exit /b 1)
echo EXE generado en dist\ControladorChatGPT.exe
pause
