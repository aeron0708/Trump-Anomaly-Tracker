@echo off
title TSADS Local High-Frequency Monitor
cd /d "%~dp0"
echo Starting TSADS Local Monitor...
python src/main_monitor.py
pause
