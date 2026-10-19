@echo off
cd /d "%~dp0"
python rates_sync.py >> sync.log 2>&1
