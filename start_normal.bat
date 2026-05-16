@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   Normal Server - Start
echo ============================================

echo [1/2] Starting Flask (127.0.0.1:5000)...
start "Flask-Real" python app.py
timeout /t 3 /nobreak >nul

echo [2/2] Starting nginx (127.0.0.1:443)...
cd nginx\nginx-1.26.3
nginx.exe -s quit >nul 2>&1
timeout /t 1 /nobreak >nul
start "nginx-REAL" nginx.exe -p . -c conf\nginx.conf
cd ..\..

echo.
echo ============================================
echo   Normal server ready!
echo.
echo   Flask:  http://127.0.0.1:5000
echo   nginx:  https://127.0.0.1:443
echo.
echo   Cloudflare Tunnel (open another terminal):
echo     cloudflared.exe tunnel run --url https://localhost:443 --no-tls-verify security-demo
echo.
echo   Monitor requests:
echo     Get-Content nginx\nginx-1.26.3\logs\access.log -Wait
echo.
echo   Stop: stop_normal.bat
echo ============================================
pause
