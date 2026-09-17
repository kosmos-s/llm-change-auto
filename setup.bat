@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo LLM Change Auto - Windows Setup
echo ================================================
echo.

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.11 -c "import sys; assert sys.version_info[:2] == (3, 11)" >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)
if not defined PY_CMD (
  echo [ERROR] Python 3.11을 찾지 못했습니다.
  echo Python 3.11 설치 시 Add Python to PATH를 체크한 뒤 다시 실행하세요.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Python 3.11 가상환경 생성 중...
  !PY_CMD! -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/5] 기존 가상환경 확인...
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] 기존 .venv가 Python 3.11 환경이 아닙니다.
    echo .venv 폴더만 삭제한 뒤 setup.bat을 다시 실행하세요.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"

echo [2/5] pip 업데이트...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [3/5] Python 패키지 설치...
if exist "requirements-lock.txt" (
  pip install -r requirements-lock.txt
) else (
  pip install -r requirements.txt
)
if errorlevel 1 goto :fail

if not exist ".env" (
  echo [4/5] .env 생성...
  copy /Y ".env.example" ".env" >nul
) else (
  echo [4/5] 기존 .env 유지
)

for %%D in (
  "outputs\llm_results"
  "outputs\compare_results"
  "outputs\review_lists"
  "outputs\reviewed_json"
  "outputs\review_events"
  "outputs\review_history"
  "outputs\backups\reviewed_json"
  "outputs\backups\project_outputs"
  "outputs\backups\reviewed_json_merge"
  "outputs\quality"
  "outputs\clean_datasets"
  "outputs\model_eval"
  "outputs\review_packages"
  "outputs\run_manifests"
  "logs"
) do (
  if not exist "%%~D" mkdir "%%~D" >nul 2>nul
)

echo [5/5] 데이터 경로 / 검수자 설정...
set "DEFAULT_DATASET=%USERPROFILE%\Desktop\산학과제\dataset_sample"
set "DATASET_PATH="
if exist "!DEFAULT_DATASET!" (
  set "DATASET_PATH=!DEFAULT_DATASET!"
  echo [OK] 기본 데이터 경로 확인: !DATASET_PATH!
) else (
  echo 기본 데이터 경로가 없습니다:
  echo   !DEFAULT_DATASET!
  set /p "DATASET_PATH=dataset_sample 실제 경로 입력 ^(건너뛰려면 Enter^): "
)

set /p "REVIEWER_NAME_INPUT=검수자 이름 입력 ^(건너뛰려면 Enter^): "
if defined DATASET_PATH (
  if exist "!DATASET_PATH!" (
    python scripts\configure_env.py --env .env --dataset-root "!DATASET_PATH!" --reviewer-name "!REVIEWER_NAME_INPUT!"
    if errorlevel 1 echo [WARN] .env 자동 설정 실패. 직접 확인하세요.
  ) else (
    echo [WARN] 입력한 데이터 경로가 존재하지 않습니다.
  )
) else if defined REVIEWER_NAME_INPUT (
  python scripts\configure_env.py --env .env --reviewer-name "!REVIEWER_NAME_INPUT!"
)

echo.
echo ================================================
echo 설치 완료
echo 1. 메모장에서 .env를 열어 OPENAI_API_KEY를 입력하세요.
echo 2. DATASET_ROOT / REVIEWER_NAME을 확인하세요.
echo 3. 이후 run.bat을 실행하세요.
echo ================================================
echo.
start "" notepad "%~dp0.env"
pause
exit /b 0

:fail
echo.
echo [ERROR] 설치 중 오류가 발생했습니다.
pause
exit /b 1
