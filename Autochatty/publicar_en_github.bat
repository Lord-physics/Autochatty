@echo off
setlocal
cd /d "%~dp0"
where git >nul 2>nul || (echo Instala Git para Windows: https://git-scm.com/ & pause & exit /b 1)
where gh >nul 2>nul || (echo Instala GitHub CLI: https://cli.github.com/ & pause & exit /b 1)
gh auth status >nul 2>nul || gh auth login
if errorlevel 1 exit /b 1
if not exist .git\config git init
if errorlevel 1 exit /b 1
git remote get-url origin >nul 2>nul
if errorlevel 1 git remote add origin https://github.com/Lord-physics/Autochatty.git
for /f "delims=" %%i in ('git remote get-url origin') do set "TARGET=%%i"
if /I not "%TARGET%"=="https://github.com/Lord-physics/Autochatty.git" (
 echo El remoto no es Lord-physics/Autochatty. Cancelado por seguridad.
 pause
 exit /b 1
)
git branch -M main
if errorlevel 1 exit /b 1
git config user.name >nul 2>nul || git config user.name "Autochatty Installer"
git config user.email >nul 2>nul || git config user.email "autochatty@users.noreply.github.com"
git fetch origin main
if errorlevel 1 goto fail
if exist .git\refs\heads\main (
 git merge --allow-unrelated-histories --no-edit origin/main
 if errorlevel 1 goto fail
)
git add -A
if errorlevel 1 goto fail
git commit -m "Autochatty v6: descubrimiento automático y selector directo"
if errorlevel 1 echo Sin cambios nuevos.
git push -u origin main
if errorlevel 1 goto fail
echo Codigo actualizado en https://github.com/Lord-physics/Autochatty
pause
exit /b 0
:fail
echo Fallo al subir. No se forzara ningun cambio remoto.
pause
exit /b 1
