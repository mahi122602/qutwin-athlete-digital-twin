@echo off
cd /d "%~dp0"
python -m utils.check_coach_database --setup
pause
