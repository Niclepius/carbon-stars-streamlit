@echo off
setlocal
set IMAGE=carbon-stars:obs
set NAME=carbon-stars-app
echo Checking Docker...
docker version >nul 2>&1 || (echo ^> Instale/abra Docker Desktop y reintente. & pause & exit /b 1)

echo Building image (this may take a few minutes)...
docker build -t %IMAGE% . || (echo Build failed. & pause & exit /b 1)

echo Stopping previous container (if any)...
docker rm -f %NAME% >nul 2>&1

echo Starting app on http://localhost:8501 ...
docker run -d --name %NAME% -p 8501:8501 %IMAGE% || (echo Run failed. & pause & exit /b 1)

start http://localhost:8501
echo App launched. To stop it, double-click stop_app.bat
pause
