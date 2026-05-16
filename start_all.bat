@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   MITM Attack Demo - Start
echo ============================================

REM --- 1. Find hotspot adapter, add virtual IP ---
echo [1/7] Adding attacker IP 192.168.137.10...

set IFACE_NAME=
for /L %%i in (1,1,20) do (
    if "!IFACE_NAME!"=="" (
        netsh interface ip show addresses "本地连接* %%i" >nul 2>&1 && (
            netsh interface ip show addresses "本地连接* %%i" 2>&1 | findstr "192.168.137" >nul && set IFACE_NAME=本地连接* %%i
        )
    )
    if "!IFACE_NAME!"=="" (
        netsh interface ip show addresses "Local Area Connection* %%i" >nul 2>&1 && (
            netsh interface ip show addresses "Local Area Connection* %%i" 2>&1 | findstr "192.168.137" >nul && set IFACE_NAME=Local Area Connection* %%i
        )
    )
)

if "!IFACE_NAME!"=="" (
    echo [WARN] Hotspot adapter not found, skipping IP setup
) else (
    netsh interface ip add address "!IFACE_NAME!" 192.168.137.10 255.255.255.0 >nul 2>&1
    if errorlevel 1 (echo   IP exists or add failed - OK) else (echo   Added 192.168.137.10 to !IFACE_NAME!)
)

REM --- 2. Free port 53 ---
echo [2/7] Freeing port 53...
net stop SharedAccess >nul 2>&1
echo   Done

REM --- 3. Start Flask ---
echo [3/7] Starting real Flask (127.0.0.1:5000)...
start "Flask-Real" python app.py
timeout /t 3 /nobreak >nul

echo [4/7] Starting attacker Flask (127.0.0.1:5001)...
start "Flask-Attacker" python attacker.py
timeout /t 2 /nobreak >nul

REM --- 4. Start nginx ---
echo [5/7] Starting real nginx (127.0.0.1:443)...
cd nginx\nginx-1.26.3
nginx.exe -s quit >nul 2>&1
timeout /t 1 /nobreak >nul
start "nginx-REAL" nginx.exe -p . -c conf\nginx.conf

echo [6/7] Starting attacker nginx (192.168.137.10:443)...
start "nginx-ATTACKER" nginx.exe -p . -c conf\nginx_attacker.conf
cd ..\..

REM --- 5. Start rogue DNS ---
echo [7/7] Starting rogue DNS (port 53, hijack security-demo-lab.xyz)...
start "RogueDNS" python rogue_dns.py
timeout /t 1 /nobreak >nul

REM --- 6. Restore hotspot ---
echo Restoring hotspot...
net start SharedAccess >nul 2>&1

echo.
echo ============================================
echo   All services started!
echo.
echo   Phone: connect to hotspot
echo          visit https://security-demo-lab.xyz
echo          TLS cert warning = DNS hijack BLOCKED!
echo.
echo   Attacker log: http://127.0.0.1:5001/attacker-log
echo.
echo   Cloudflare Tunnel (optional):
echo     cloudflared.exe tunnel run --url https://localhost:443 --no-tls-verify security-demo
echo.
echo   Stop: run stop_all.bat
echo ============================================
pause
