@echo off
REM demo.bat - one-click NDI demo for NDIForPython.
REM   Launches the send_example.py sender (animated 1280x720 BGRA gradient,
REM   visible on the LAN as "NDIForPython demo") plus the cv2 preview, which
REM   discovers the source and shows it live.
REM
REM Press Ctrl+C in either cmd window (or 'q' / ESC in the cv2 preview) to stop.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

start "NDIForPython sender" cmd /K "python ""%~dp0send_example.py"""
REM 2-second pause without depending on `timeout` (Git-Bash users have a
REM Unix `timeout` first in PATH that rejects /t).
ping -n 3 127.0.0.1 >nul
start "NDIForPython preview (cv2)" cmd /K "python ""%~dp0preview_example.py"""

echo.
echo Two windows opened: sender + cv2 preview.
echo You should see the animated gradient appear in the preview within a second.
echo Other NDI receivers on the LAN (TouchDesigner, OBS, vMix, ...) will also
echo see the source named "NDIForPython demo".
endlocal
