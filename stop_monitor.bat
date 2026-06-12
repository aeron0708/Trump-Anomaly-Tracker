@echo off
title 關閉 TSADS 監控程序
cd /d "%~dp0"
echo =========================================================
echo             TSADS - 關閉背景/視窗監控程序
echo =========================================================
echo 正在搜尋並結束所有執行中的 main_monitor.py 程序...
echo.

powershell -NoProfile -Command "   $processes = Get-CimInstance Win32_Process -Filter \"CommandLine like '%%main_monitor.py%%'\";   if ($processes) {       foreach ($p in $processes) {           Stop-Process -Id $p.ProcessId -Force;           Write-Host \"[成功] 已關閉監控進程 ID: $($p.ProcessId)\" -ForegroundColor Green;       }   } else {       Write-Host \"[提示] 未偵測到正在運行的 main_monitor.py 進程。\" -ForegroundColor Yellow;   }"

echo.
echo =========================================================
echo 關閉程序執行完畢。
pause
