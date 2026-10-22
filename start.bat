@echo off
rem J5 EV Dashboard - Windows one-click start. No Docker, no terminal knowledge needed.
rem Double-click this file. First run installs what it needs, then opens the dashboard.
setlocal
cd /d "%~dp0"
title J5 EV Dashboard

set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python

if not defined PY (
  echo Python is not installed. Installing it now ^(about 1 minute^)...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo.
  echo Python installed. Please CLOSE this window and double-click start.bat again.
  pause
  exit /b
)

%PY% -c "import requests, websocket" >nul 2>nul
if errorlevel 1 (
  echo First run: installing the two small libraries it needs...
  %PY% -m pip install --quiet requests websocket-client
  if errorlevel 1 (
    echo.
    echo Install failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

%PY% tools\run.py
pause
