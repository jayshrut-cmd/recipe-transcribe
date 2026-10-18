@echo off
REM Double-click friendly launcher for transcribe-video.py
cd /d %~dp0
python transcribe-video.py %*
pause
