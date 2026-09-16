@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 가상환경이 없습니다. 먼저 setup.bat을 실행하세요.
  pause
  exit /b 1
)

if not exist ".env" (
  echo [ERROR] .env 파일이 없습니다. 먼저 setup.bat을 실행하세요.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo LLM Change Auto를 시작합니다.
echo 브라우저가 자동으로 열리지 않으면 http://localhost:8501 로 접속하세요.
echo 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.

python -m streamlit run app\main_app.py

if %errorlevel% neq 0 (
  echo.
  echo [ERROR] 앱 실행 중 오류가 발생했습니다.
  pause
)
