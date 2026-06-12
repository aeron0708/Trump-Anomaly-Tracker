Set WshShell = CreateObject("WScript.Shell")
' Run python script in absolute stealth mode (0 = Hidden, False = Do not wait)
WshShell.Run "cmd /c python src/main_monitor.py", 0, False
