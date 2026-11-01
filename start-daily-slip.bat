@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py daily_slip_helper.py) || (python daily_slip_helper.py)
if errorlevel 1 echo.& echo Python 3 is needed. Install it from python.org or the Microsoft Store, then run this again.
pause
