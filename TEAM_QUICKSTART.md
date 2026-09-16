# 팀원용 빠른 시작 가이드

이 문서는 **Windows 기준**으로 GitHub에서 저장소를 받은 뒤 가능한 한 적은 설정으로 `LLM Change Auto`를 실행하는 방법입니다.

## 준비물

- Windows 10/11
- Python 3.11 이상 권장
- Git
- OpenAI API Key
- `dataset_sample` 데이터 폴더

`dataset_sample`의 기본 구조는 다음과 같습니다.

```text
dataset_sample/
├─ dataset/
│  ├─ train/
│  ├─ val/
│  └─ test/
└─ errors/
   ├─ train/
   ├─ val/
   └─ test/
```

각 샘플은 기본적으로 다음 파일을 사용합니다.

```text
*_combined.jpg
*_combined.json
*_left.jpg
*_right.jpg
```

## 1. 저장소 받기

```powershell
git clone https://github.com/kosmos-s/llm-change-auto.git
cd llm-change-auto
```

ZIP으로 내려받아 압축을 풀어도 됩니다.

## 2. 최초 1회: `setup.bat`

저장소 루트에서 `setup.bat`을 더블클릭합니다.

자동으로 다음 작업을 수행합니다.

1. `.venv` 가상환경 생성
2. `requirements.txt` 설치
3. `.env.example`을 이용해 로컬 `.env` 생성
4. 필요한 `outputs` 폴더 생성
5. 기본 데이터 경로 확인
6. 데이터가 다른 위치에 있으면 기본 위치로 폴더 연결 시도
7. 마지막에 `.env`를 메모장으로 열기

### 데이터 경로

프로그램의 기본 데이터 위치는 다음입니다.

```text
%USERPROFILE%\Desktop\산학과제\dataset_sample
```

`setup.bat` 실행 중 실제 `dataset_sample` 위치를 입력하면 위 기본 위치에 Windows 디렉터리 연결(Junction)을 만들려고 시도합니다.

연결에 실패해도 프로그램 사용은 가능하며, **1. OpenAI 자동판정 화면에서 데이터 루트 경로를 직접 입력**하면 됩니다.

## 3. OpenAI API Key 입력

`setup.bat`이 열어 준 `.env`에서 아래 값을 수정합니다.

```text
OPENAI_API_KEY=여기에_본인_API_KEY
OPENAI_TIMEOUT=60
```

`.env`는 GitHub에 업로드되지 않습니다.

## 4. 실행: `run.bat`

이후부터는 저장소 루트의 `run.bat`만 더블클릭하면 됩니다.

브라우저가 자동으로 열리지 않으면 다음 주소로 접속합니다.

```text
http://localhost:8501
```

앱 종료는 `run.bat` 콘솔 창에서 `Ctrl + C`입니다.

## 5. 최초 실행 후 확인

앱의 **1. OpenAI 자동판정** 화면에서 다음을 확인합니다.

- 데이터 루트 경로가 실제 `dataset_sample`을 가리키는지
- `OPENAI_API_KEY 확인됨` 표시가 나오는지
- `dataset_index.csv 생성`이 정상 동작하는지

그다음 작업 순서는 다음과 같습니다.

```text
1. OpenAI 자동판정
→ 2. 사람 검수
→ 3. 검수 이력
→ 4. 정제 데이터 생성
→ 5. 작업 통계
→ 6. LLM 결과 분석
```

## 다른 컴퓨터에서 업데이트

이미 설치가 끝난 PC에서는 보통 다음만 하면 됩니다.

```powershell
git pull
```

`requirements.txt`가 변경된 경우에만 `setup.bat`을 다시 실행하면 됩니다. 기존 `.env`는 덮어쓰지 않습니다.

## 주의사항

- `.env`와 API Key를 GitHub에 올리지 않습니다.
- 원본 `dataset_sample`은 직접 덮어쓰지 않습니다.
- 본작업에서는 사람 검수 결과를 `outputs/reviewed_json`에 저장합니다.
- 본작업이 시작된 뒤 `outputs/llm_results`, `review_lists`, `reviewed_json`, `review_events`, `review_history`를 임의 삭제하지 않습니다.
- GPT 결과는 최종 정답이 아니며 사람이 검수한 라벨을 최종 확정본으로 사용합니다.

## 문제가 생겼을 때

### `python`을 찾을 수 없음
Python 3 설치 시 **Add Python to PATH**를 체크하고 다시 `setup.bat`을 실행합니다.

### `OPENAI_API_KEY가 없습니다`
`.env` 파일의 `OPENAI_API_KEY=` 뒤에 실제 키가 들어 있는지 확인하고 앱을 재시작합니다.

### 데이터 경로가 없음
1. `dataset_sample`이 실제로 존재하는지 확인
2. `setup.bat`을 다시 실행해 데이터 경로를 연결하거나
3. 앱에서 데이터 루트 경로를 직접 입력

### 설치가 꼬였을 때
`.venv` 폴더만 삭제하고 `setup.bat`을 다시 실행합니다. 원본 데이터와 `outputs`는 삭제하지 않습니다.
