@echo off
setlocal

REM Root of the Cloud_Computing project (this .bat lives here)
set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

REM Optional: activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM Start XML-RPC chat server in its own window (history persisted in chat_history.jsonl)
start "Chat RPC Server" /D "%PROJECT_DIR%cloud_rpc_chat" cmd /k python server.py --host 0.0.0.0 --port 9000 --history-file chat_history.jsonl

REM Start Flask web UI in its own window
start "Chat Flask GUI" /D "%PROJECT_DIR%cloud_rpc_chat" cmd /k python flask_app.py --server_host 127.0.0.1 --server_port 9000 --flask_host 127.0.0.1 --flask_port 5000

REM Give the Flask app a moment to start
timeout /t 5 /nobreak > nul

REM Open the default browser pointing at the Flask UI
start "" "http://127.0.0.1:5000/"

endlocal

