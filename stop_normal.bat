@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Normal Server - Stop
echo ============================================

echo [1/2] Stopping nginx...
cd nginx\nginx-1.26.3
nginx.exe -s quit >nul 2>&1
cd ..\..

echo [2/2] Stopping Flask...
pkill -f "app.py" >nul 2>&1

echo.
echo Done.
pause
