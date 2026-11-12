@echo off
cd /d "%~dp0"
where pyw >nul 2>&1
if errorlevel 1 (
    echo Python не найден. Установите Python 3 с python.org
    pause
    exit /b 1
)
start "" pyw -3 "%~dp0eye_gym.py"
