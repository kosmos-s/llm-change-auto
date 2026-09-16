@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo LLM Change Auto - Windows Setup
echo ================================================
echo.

where py >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python 3을 찾지 못했습니다.
    echo Python 3.11 이상 설치 후 다시 실행하세요.
    pause
    exit /b 1
  )
  set "PY_CMD=python"
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] 가상환경 생성 중...
  !PY_CMD! -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/5] 기존 가상환경 사용
)

call ".venv\Scripts\activate.bat"

echo [2/5] pip 업데이트...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo [3/5] Python 패키지 설치...
if exist "requirements-lock.txt" (
  echo 재현 가능한 고정 버전 requirements-lock.txt 사용
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
  "outputs\quality"
  "outputs\clean_datasets"
  "outputs\model_eval"
  "logs"
) do (
  if not exist "%%~D" mkdir "%%~D" >nul 2>nul
)

echo [5/5] 데이터 경로 확인...
set "DEFAULT_PROJECT=%USERPROFILE%\Desktop\산학과제"
set "DEFAULT_DATASET=!DEFAULT_PROJECT!\dataset_sample"

if exist "!DEFAULT_DATASET!" (
  echo [OK] 기본 데이터 경로 확인: !DEFAULT_DATASET!
) else (
  echo.
  echo 기본 데이터 경로가 없습니다:
  echo   !DEFAULT_DATASET!
  echo.
  echo 데이터가 다른 위치에 있다면 그 폴더를 연결할 수 있습니다.
  set /p "DATASET_PATH=dataset_sample 실제 경로 입력 ^(건너뛰려면 Enter^): "
  if defined DATASET_PATH (
    if not exist "!DATASET_PATH!" (
      echo [WARN] 입력한 경로가 존재하지 않습니다. UI에서 직접 지정하세요.
    ) else (
      if not exist "!DEFAULT_PROJECT!" mkdir "!DEFAULT_PROJECT!" >nul 2>nul
      mklink /J "!DEFAULT_DATASET!" "!DATASET_PATH!" >nul 2>nul
      if exist "!DEFAULT_DATASET!" (
        echo [OK] 데이터 폴더 연결 완료
      ) else (
        echo [WARN] 폴더 연결에 실패했습니다.
        echo .env의 DATASET_ROOT 또는 UI에서 실제 경로를 지정하세요.
      )
    )
  ) else (
    echo [INFO] 데이터 경로 설정을 건너뜁니다. .env 또는 UI에서 직접 지정할 수 있습니다.
  )
)

echo.
echo ================================================
echo 설치 완료
echo 1. 메모장에서 .env를 열어 OPENAI_API_KEY를 입력하세요.
echo 2. 데이터가 기본 경로가 아니면 DATASET_ROOT도 입력할 수 있습니다.
echo 3. 이후 run.bat을 실행하세요.
echo ================================================
echo.

start "" notepad "%~dp0.env"
pause
exit /b 0

:fail
echo.
echo [ERROR] 설치 중 오류가 발생했습니다.
echo 위 오류 메시지를 확인하세요.
pause
exit /b 1
