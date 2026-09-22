@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] 启动 Neo4j ...
docker compose up -d neo4j
if errorlevel 1 (
  echo Docker 没起来。先打开 Docker Desktop，等鲸鱼图标不再转圈，再双击本文件。
  pause
  exit /b 1
)

echo [2/3] 启动后端 8000 ...
start "知识库-后端" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

echo [3/3] 启动前端 5173 ...
start "知识库-前端" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo 等十几秒后浏览器会打开。两个黑窗口不要关。
timeout /t 8 /nobreak >nul
start http://127.0.0.1:5173
echo 可以点：产品 / SLA / 转人工
pause
