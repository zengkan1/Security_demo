@echo off
echo ============================================
echo   信息安全演示平台 - 启动脚本
echo ============================================
echo.

REM 设置项目根目录
set PRJ_DIR=%~dp0

echo [1/3] 启动 Flask 服务器 (端口 5000)...
start "Flask" python "%PRJ_DIR%app.py"

REM 等 Flask 启动
timeout /t 3 /nobreak >nul

echo [2/3] 启动 nginx (端口 80/443)...
cd /d "%PRJ_DIR%nginx\nginx-1.26.3"
start "nginx" nginx.exe -p "%PRJ_DIR%nginx\nginx-1.26.3"

echo [3/3] 完成！
echo.
echo ============================================
echo   访问地址:
echo   HTTP:  http://localhost
echo   HTTPS: https://localhost
echo.
echo   局域网访问 (手机/其他设备):
echo   先查看本机IP: ipconfig ^| findstr "IPv4"
echo   然后访问: https://你的IP地址
echo.
echo   注意: 自签名证书会触发浏览器安全警告，
echo   这是正常的教学演示行为。
echo ============================================
echo.
pause
