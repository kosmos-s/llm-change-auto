# 팀원용 빠른 시작 가이드

이 문서는 **Windows 기준**으로 GitHub에서 저장소를 받은 뒤 가능한 한 적은 설정으로 `LLM Change Auto`를 실행하는 방법입니다.

## 준비물

- Windows 10/11
- **Python 3.11**
- Git
- OpenAI API Key
- `dataset_sample` 데이터 폴더

> `setup.bat`과 `requirements-lock.txt`는 재현 가능한 팀 환경을 위해 Python 3.11을 기준으로 고정되어 있습니다.

기본 데이터 구조:

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

## 1. 저장소 받기

```powershell
git clone https://github.com/kosmos-s/llm-change-auto.git
cd llm-change-auto
```

ZIP 다운로드 후 압축을 풀어도 됩니다.

## 2. 최초 1회: `setup.bat`

저장소 루트에서 `setup.bat`을 더블클릭합니다.

자동으로:

1. Python 3.11 확인
2. `.venv` 생성
3. `requirements-lock.txt` 고정 버전 설치
4. `.env.example` → 로컬 `.env` 생성
5. 필요한 `outputs` 폴더 생성
6. 기본 데이터 경로 확인
7. 다른 위치의 데이터면 Junction 연결 시도
8. 마지막에 `.env`를 메모장으로 열기

기본 데이터 위치:

```text
%USERPROFILE%\Desktop\산학과제\dataset_sample
```

다른 위치를 그대로 사용하려면 `.env`에 직접 적어도 됩니다.

```text
DATASET_ROOT=D:/실제/경로/dataset_sample
```

## 3. OpenAI API Key 입력

`.env`에서 아래 값을 수정합니다.

```text
OPENAI_API_KEY=여기에_본인_API_KEY
OPENAI_TIMEOUT=60
DATASET_ROOT=
OPENAI_TARGET_TOTAL=3000
OPENAI_COST_LIMIT_USD=5
BACKUP_KEEP_COUNT=10
```

토큰 단가는 변경될 수 있으므로 앱에서 현재 값을 입력합니다.

`.env`는 GitHub에 업로드되지 않습니다.

## 4. 실행: `run.bat`

이후부터는 저장소 루트의 `run.bat`만 더블클릭하면 됩니다.

브라우저가 자동으로 열리지 않으면:

```text
http://localhost:8501
```

종료는 콘솔 창에서 `Ctrl + C`입니다.

## 5. 최초 실행 후 확인

첫 화면에서 다음을 확인합니다.

- OpenAI API Key `확인됨`
- 데이터 경로 `확인됨`
- dataset_index가 없으면 `생성 필요`

1번 화면에서 먼저:

```text
dataset_index.csv 생성
→ 데이터 무결성 검사
```

를 진행합니다.

## 6. 본작업 순서

화면은 1 → 7 순서입니다.

```text
1. OpenAI 자동판정
2. 사람 검수
3. 검수 이력
4. 정제 데이터 생성
5. 작업 통계 / 백업
6. LLM 결과 분석
7. 모델 성능 비교
```

3,000건 기본 계획:

```text
errors/train 1,000
errors/val   1,000
errors/test  1,000
```

**사람이 3,000건을 전부 검수하는 것이 아닙니다.** OpenAI가 3,000건을 처리하고 프로그램이 추린 후보만 사람이 확인합니다.

각 batch 종료 후:

```text
비교 실행
→ 검수 목록 생성
→ 사람 검수
→ 검수 이력 갱신
→ 5. 작업 통계 확인
→ outputs ZIP 백업
```

## 7. 품질검사

3,000건 검수가 끝나면 4번 화면에서 품질검사를 합니다.

- split leakage
- Artifact 세부라벨 논리
- 파일 누락
- invalid JSON
- orphan 파일

`artifact_logic` 같은 경고는 **품질 검수 목록 생성**으로 사람 검수 화면에 넘길 수 있습니다.

`final*` Snapshot은 Error가 1건이라도 있으면 생성되지 않습니다.

## 8. 모델 재학습 후

재학습 결과의 `precision / recall / f1 / f2`를 7번 화면에 넣어 기존 모델과 비교합니다.

산학과제 목표 `F2 0.85`는 여기서 확인합니다. 6번 화면의 GPT 비교용 F2와는 다른 값입니다.

## 다른 컴퓨터에서 업데이트

이미 설치된 PC:

```powershell
git pull
```

`requirements-lock.txt`가 바뀌었으면 `setup.bat`을 한 번 더 실행합니다. 기존 `.env`는 유지됩니다.

## 주의사항

- `.env`와 API Key를 GitHub에 올리지 않습니다.
- 원본 `dataset_sample`을 직접 덮어쓰지 않습니다.
- 본작업 검수 결과는 `outputs/reviewed_json`에 저장합니다.
- 본작업 결과 폴더를 임의 삭제하지 않습니다.
- 5번 화면에서 주기적으로 ZIP 백업을 생성합니다.
- GPT 결과는 최종 정답이 아니며 사람 확정 라벨을 최종본으로 사용합니다.

## 문제가 생겼을 때

### Python 3.11을 찾을 수 없음
Python **3.11** 설치 시 **Add Python to PATH**를 체크하고 다시 `setup.bat`을 실행합니다.

### 기존 `.venv`가 Python 3.11이 아님
`.venv` 폴더만 삭제하고 `setup.bat`을 다시 실행합니다. 원본 데이터와 `outputs`는 삭제하지 않습니다.

### `OPENAI_API_KEY가 없습니다`
`.env`의 `OPENAI_API_KEY=` 뒤에 실제 키가 들어 있는지 확인하고 앱을 재시작합니다.

### 데이터 경로가 없음
`.env`의 `DATASET_ROOT` 또는 1번 화면의 데이터 루트 경로를 확인합니다.

### 설치가 꼬였을 때
`.venv` 폴더만 삭제하고 `setup.bat`을 다시 실행합니다. 원본 데이터와 `outputs`는 삭제하지 않습니다.

### GitHub CI가 실패함
`Actions`에서 실패 원인을 확인합니다. 보통 unit test 또는 secret scan 문제입니다. API Key가 코드에 들어갔다면 즉시 제거하고 해당 키를 폐기하세요.
