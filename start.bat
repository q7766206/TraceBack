@echo off
chcp 65001 >nul 2>&1
title TraceBack - One Click Start

:: Add runtime paths (stepfun node/uv)
set "PATH=C:\Users\Administrator\.stepfun\runtimes\node\install_1769620253881_9mnsukg8vl\node-v22.18.0-win-x64;C:\Users\Administrator\AppData\Local\Programs\Python\Python311;C:\Users\Administrator\AppData\Local\Programs\Python\Python311\Scripts;%PATH%"

echo.
echo  ============================================
echo       TraceBack - Multi-Agent Causal Engine
echo  ============================================
echo.

:: Check Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Node.js not found. Please install Node.js 18+
    pause
    exit /b 1
)

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python not found. Please install Python 3.11+
    pause
    exit /b 1
)

:: Check .env
if not exist "%~dp0.env" (
    echo  [ERROR] .env file not found.
    echo  Please copy .env.example to .env and fill in your API keys.
    pause
    exit /b 1
)

echo  [1/2] Starting Backend (Flask :5001) ...
start "TraceBack-Backend" cmd /k "cd /d "%~dp0backend" && uv run python run.py"

:: Wait for backend to initialize
timeout /t 3 /nobreak >nul

echo  [2/2] Starting Frontend (Vite :3000) ...
start "TraceBack-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait for frontend to initialize
timeout /t 5 /nobreak >nul

echo.
echo  ============================================
echo   All services started!
echo.
echo   Frontend : http://localhost:3000
echo   Backend  : http://localhost:5001/api/
echo  ============================================
echo.
echo  Browser will be opened by Vite automatically.
echo.
echo  Press any key to stop all services...
pause >nul

:: Cleanup: kill backend and frontend
taskkill /FI "WINDOWTITLE eq TraceBack-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq TraceBack-Frontend*" /F >nul 2>&1
echo  All services stopped.
pause
