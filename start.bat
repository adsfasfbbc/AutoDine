@echo off
setlocal
cd /d "%~dp0"

set "PY=py -3.11"
set "DB_URL=sqlite+pysqlite:///autodine.db"

echo.
echo ==============================================
echo   AutoDine launcher  (Core + Agent Hub)
echo ==============================================
echo.

%PY% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 not found. Install Python 3.11, or edit PY in this script.
    pause
    exit /b 1
)

echo [1/3] Seeding database ...
%PY% scripts\seed_data.py --database-url "%DB_URL%"
if errorlevel 1 (
    echo [ERROR] Seeding failed. Make sure dependencies are installed.
    pause
    exit /b 1
)

echo [2/3] Starting Core on http://127.0.0.1:8000 ...
start "AutoDine Core (8000)" cmd /k "set AUTODINE_CORE_DATABASE_URL=%DB_URL% && %PY% -m uvicorn autodine_core.main:create_app --factory --host 127.0.0.1 --port 8000"

echo [3/3] Starting Agent Hub on http://127.0.0.1:8100 ...
rem --- LLM driver: Qwen (DashScope, OpenAI-compatible tool-calling). Key below. ---
set "AGENT_HUB_LLM_DRIVER=openai"
set "AGENT_HUB_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1"
set "AGENT_HUB_LLM_API_KEY=sk-ws-H.EYLPLMY.8R4v.MEQCIHonpSg0wqMosClLIO-lM1jzODTeNyFZ-itwMgB5aLHSAiAUZ_74pm_ujKAuEve1jB5WMsv_TJloBm5sbzEFMUTBMw"
set "AGENT_HUB_LLM_MODEL=qwen-plus"
start "AutoDine Agent Hub (8100)" cmd /k "set AGENT_HUB_CORE_BASE_URL=http://127.0.0.1:8000 && %PY% -m uvicorn agent_hub.service:create_app --factory --host 127.0.0.1 --port 8100"

echo.
echo Launching browser in 5 seconds ...
timeout /t 5 /nobreak >nul
start "" http://localhost:8100/

echo.
echo Pages:
echo   Home     : http://localhost:8100/
echo   Consumer : http://localhost:8100/consumer
echo   Kitchen  : http://localhost:8100/kitchen
echo   Manager  : http://localhost:8100/manager
echo.
echo Keep the two new windows open. Closing them stops the services.
echo.
pause
endlocal
