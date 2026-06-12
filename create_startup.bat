@echo off
title TSADS - 建立開機啟動捷徑
cd /d "%~dp0"

set SCRIPT="%TEMP%\create_tsads_lnk.vbs"
if exist %SCRIPT% del %SCRIPT%

echo Set oWS = CreateObject("WScript.Shell") >> %SCRIPT%
echo sLinkFile = "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Trump Anomaly Tracker.lnk" >> %SCRIPT%
echo Set oLink = oWS.CreateShortcut(sLinkFile) >> %SCRIPT%
echo oLink.TargetPath = "C:\Antigravity專案\自動交易\Trump Anomaly Tracker\run_stealth.vbs" >> %SCRIPT%
echo oLink.WorkingDirectory = "C:\Antigravity專案\自動交易\Trump Anomaly Tracker" >> %SCRIPT%
echo oLink.Save >> %SCRIPT%

cscript /nologo %SCRIPT%
if exist %SCRIPT% del %SCRIPT%

echo ===================================================
echo [TSADS] 開機自動啟動捷徑已成功建立！
echo 捷徑已放置於: %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
echo 系統將於每次開機時自動在背景靜默運行監控程序。
echo ===================================================
pause
