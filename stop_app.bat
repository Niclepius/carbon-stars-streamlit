@echo off
setlocal
set NAME=carbon-stars-app
docker rm -f %NAME% >nul 2>&1 && echo App stopped. || echo App was not running.
pause
