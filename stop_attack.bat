@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================
echo   MITM Attack Demo - Stop
echo ============================================

echo [1/4] Stopping rogue DNS...
taskkill /fi "WINDOWTITLE eq RogueDNS*" /f >nul 2>&1
pkill -f "rogue_dns.py" >nul 2>&1

echo [2/5] Stopping attacker nginx + Flask...
cd nginx\nginx-1.26.3
nginx.exe -s quit >nul 2>&1
cd ..\..

pkill -f "attacker.py" >nul 2>&1

echo [3/5] Stopping real server...
pkill -f "app.py" >nul 2>&1

echo [4/5] Removing virtual IP...
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
    echo   Adapter not found, skipping
) else (
    netsh interface ip delete address "!IFACE_NAME!" 192.168.137.10 >nul 2>&1
    echo   Removed 192.168.137.10 from !IFACE_NAME!
)

echo [5/5] Restoring hotspot...
net start SharedAccess >nul 2>&1

echo.
echo Done. Normal state restored.
pause
