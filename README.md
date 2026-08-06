# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + OpenAI GPT 자동화 통합 도구**입니다.

이 프로젝트는 `dataset_sample` 또는 NAS 데이터에 포함된 2시점 항공영상 쌍을 대상으로 다음 작업을 수행합니다.

- `*_combined.jpg`, `*_left.jpg`, `*_right.jpg`, `*_combined.json` 파일 구조 읽기
- `dataset` 일반 학습데이터와 `errors` 오탐/미탐 검수데이터 구분
- 기존 JSON 라벨 확인 및 수정
- OpenAI GPT 기반 변화유무 및 세부 라벨 자동판단
- 기존 JSON 라벨과 GPT 결과 비교
- 육안검수 대상 CSV 생성
- `review_list.csv` 기반 검수 대상만 보기
- 결과 CSV와 `reviewed_json` 저장 현황 통계 확인
- Streamlit 통합 UI 제공

과제 자료의 수행 흐름인 **자동라벨링 → 기존 라벨 비교 → Human-in-the-loop 검수 → 정제 결과 축적**에 맞춰 구성했습니다.

---

## 1. 데이터 구조

권장 로컬 구조는 아래와 같습니다.

```text
산학과제/
├─ dataset_sample/
│  ├─ dataset/
│  │  ├─ train/
│  │  ├─ val/
│  │  └─ test/
│  └─ errors/
│     ├─ train/
│     ├─ val/
│     └─ test/
└─ llm-change-auto/
```

각 `train / val / test` 폴더 안에는 보통 아래 파일들이 들어 있습니다.

```text
00_xxxx_combined.jpg
00_xxxx_combined.json
00_xxxx_left.jpg
00_xxxx_right.jpg
```

`errors` 폴더는 오류 유형별 하위 폴더가 있을 수도 있습니다.

```text
errors/test/artifact_fn_00/
errors/test/artifact_fp_00/
```

NAS 전체 데이터처럼 아래 구조도 지원합니다.

```text
2026/dataset/train
2026/dataset/val
2026/dataset/test
2026/dataset/errors/train
2026/dataset/errors/val
2026/dataset/errors/test
```

---

## 2. API Key 보안 원칙

- 실제 API 키는 프로젝트 루트의 로컬 `.env` 파일에만 저장합니다.
- API 키를 Streamlit 화면에 입력하지 않습니다.
- API 키를 Python 코드, CSV, JSON, 로그에 저장하지 않습니다.
- `.env`와 `.env.*`는 `.gitignore`에서 제외되며 `.env.example`만 공유합니다.
- OpenAI SDK가 `OPENAI_API_KEY` 환경변수를 직접 읽도록 구성했습니다.
- API 오류 메시지에 `sk_...`, `key_...` 같은 키 형태 문자열이 포함되면 `[REDACTED_API_KEY]`로 가린 뒤 결과 CSV에 저장합니다.
- 원본 이미지 데이터와 실행 결과 CSV는 GitHub에 업로드하지 않습니다.

현재 저장소 이력에는 `.env` 파일 커밋 기록이 없습니다. 그래도 실제 키를 화면 캡처, 채팅, 문서 또는 커밋에 붙여넣지 마세요.

---

## 3. 설치 방법

VS Code에서 `llm-change-auto` 폴더를 엽니다.

```powershell
cd "C:\Users\rlarj\Desktop\산학과제\llm-change-auto"
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

이미 가상환경을 만든 적이 있으면 아래만 실행합니다.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Gemini 관련 SDK와 REST 호출 코드는 제거했으며 자동라벨링 경로는 OpenAI 전용입니다.

---

## 4. OpenAI API 설정

`.env.example`을 복사하여 `.env`를 만듭니다.

```powershell
copy .env.example .env
```

`.env` 파일에는 아래처럼 입력합니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

OpenAI SDK는 환경변수에서 키를 자동으로 읽습니다. 코드나 UI에는 키 값을 전달하지 않습니다.

---

## 5. 통합 UI 실행

검수 UI, OpenAI 자동화 UI, 통계 UI를 하나의 Streamlit 앱에서 사용합니다.

### VS Code 실행

```text
app/run_app.py 열기 → Ctrl + F5
```

### 터미널 실행

```powershell
python -m streamlit run app\main_app.py
```

브라우저 주소:

```text
http://localhost:8501
```

왼쪽 사이드바의 **Pages**에서 아래 페이지를 선택합니다.

| 페이지 | 역할 |
|---|---|
| `검수 UI` | 이미지 확인, JSON 라벨 수정, GPT 검수 대상 CSV 확인 |
| `LLM 자동화 UI` | 데이터 인덱스 생성, OpenAI 실행, 라벨 비교, 검수 목록 생성 |
| `통계 UI` | CSV 결과와 `reviewed_json` 저장 현황 요약 |

---

## 6. 검수 UI 기능

검수 UI에는 두 가지 모드가 있습니다.

### 폴더 전체 검수

- `dataset / errors / both` 선택
- `test / train / val / all` 선택
- `combined / left / right` 이미지 전환
- 현재 파일이 `dataset`인지 `errors`인지 표시
- `errors` 하위 오류 유형 폴더명 표시

### GPT 검수 대상 CSV

OpenAI 자동화 UI에서 생성한 검수 대상 CSV만 불러옵니다.

예시:

```text
outputs/review_lists/openai_dataset_test_1_review.csv
```

표시 정보:

- GPT 변화유무 판단
- confidence
- label_mismatch
- detail_mismatch
- detail_mismatch_keys
- review_reasons
- 기존 라벨과 GPT 라벨 비교표
- GPT 판단 근거

### 공통 검수 기능

- 체크박스로 라벨 수정
- `reason`, `reason (KO)` 수정
- `Previous File`, `Next File`, `Jump` 이동
- `Save Changes` 저장
- `Save & Next` 저장 후 다음 파일 이동

저장 방식:

| 저장 방식 | 설명 |
|---|---|
| `reviewed_json 폴더에 저장` | 원본 JSON은 그대로 두고 `outputs/reviewed_json/{source}/{split}`에 저장 |
| `원본 JSON 덮어쓰기` | 기존 `*_combined.json` 파일을 바로 수정 |

처음에는 `reviewed_json 폴더에 저장`을 사용하세요.

---

## 7. OpenAI 자동화 UI 기능

아래 과정을 버튼으로 실행합니다.

```text
데이터 인덱스 생성
→ OpenAI GPT 자동판별
→ 기존 JSON 라벨과 비교
→ 검수 대상 CSV 생성
```

첫 테스트 권장 설정:

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 1
OpenAI 모델: gpt-4o-mini
프롬프트: prompts/prompt_v3_json_strict.txt
출력 파일 접두어: openai_dataset_test_1
```

생성 파일:

```text
outputs/dataset_index.csv
outputs/llm_results/openai_dataset_test_1.csv
outputs/compare_results/openai_dataset_test_1_compare.csv
outputs/review_lists/openai_dataset_test_1_review.csv
```

1장이 정상 처리되고 `error` 컬럼이 비어 있는 것을 확인한 뒤 `3장 → 10장 → 50장` 순서로 확대합니다.

터미널 실행 예시:

```powershell
python src\run_llm_labeling.py --model gpt-4o-mini --input outputs\dataset_index.csv --source dataset --split test --limit 1 --output outputs\llm_results\openai_dataset_test_1.csv
```

---

## 8. OpenAI 호출 구조

`src/llm_client.py`는 OpenAI 공식 Python SDK의 Responses API를 사용합니다.

- 이미지: base64 data URL 형식의 `input_image`
- 프롬프트: `input_text`
- 출력: JSON Schema 기반 Structured Output
- 응답 저장: `store=False`
- timeout: `OPENAI_TIMEOUT`, 기본 60초
- 재시도: 최대 2회
- 키 전달: `OpenAI()`가 환경변수에서 자동 로드

자동판별 결과에는 아래 필드가 반드시 포함됩니다.

```text
change, class,
arti, arti_bu, arti_bu_t, arti_binil, arti_road, arti_roa_m, arti_other,
tree, fore, farm, water,
reason_ko, reason_en, confidence, review_required
```

---

## 9. 통계 UI 기능

통계 UI에서는 `outputs` 폴더의 결과를 요약합니다.

- `dataset_index.csv` 개수
- OpenAI 결과 CSV 요약
- 비교 결과 CSV 요약
- 검수 대상 CSV 요약
- review_reasons별 개수
- label_mismatch / detail_mismatch 개수
- confidence 평균 및 low confidence 개수
- 라벨별 original / GPT 개수 비교
- `outputs/reviewed_json` 저장 현황

---

## 10. 현재 프로젝트 구조

```text
llm-change-auto/
├─ app/
│  ├─ main_app.py
│  ├─ run_app.py
│  ├─ reviewer_app.py
│  ├─ llm_pipeline_app.py
│  ├─ run_reviewer.py
│  ├─ run_llm_pipeline.py
│  └─ pages/
│     ├─ 1_검수_UI.py
│     ├─ 2_LLM_자동화_UI.py
│     └─ 3_통계_UI.py
│
├─ src/
│  ├─ dataset_loader.py
│  ├─ json_io.py
│  ├─ scan_dataset.py
│  ├─ llm_client.py              # OpenAI Responses API 전용
│  ├─ run_llm_labeling.py        # OpenAI 자동 라벨링 실행
│  ├─ compare_labels.py
│  ├─ make_review_list.py
│  ├─ summarize_results.py
│  ├─ image_utils.py
│  ├─ prompt_builder.py
│  ├─ parse_llm_result.py
│  └─ metrics.py
│
├─ prompts/
├─ config/
├─ outputs/
├─ docs/
│  ├─ openai_setup.md
│  └─ llm_pipeline_ui.md
├─ logs/
├─ .vscode/
├─ .env.example
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## 11. 자주 생기는 문제

### PowerShell에서 가상환경 실행 오류

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### `streamlit` 명령어를 찾을 수 없음

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app\main_app.py
```

### `OPENAI_API_KEY가 없습니다`

프로젝트 루트에 `.env`가 있는지 확인하고 Streamlit을 완전히 종료한 뒤 다시 실행합니다.

```text
Ctrl + C
app/run_app.py 열기 → Ctrl + F5
```

### `invalid_api_key`

키를 다시 확인합니다. 오류 결과 CSV에는 키 형태 문자열이 가려져 저장되지만, 잘못된 실행 결과는 삭제하거나 새로운 출력 접두어로 다시 실행하세요.

### Load를 눌렀는데 파일이 안 나옴

```text
올바른 예: C:\Users\rlarj\Desktop\산학과제\dataset_sample
잘못된 예: C:\Users\rlarj\Desktop\산학과제\dataset_sample\dataset\test
```

---

## 12. 현재 구현 상태

- [x] 통합 Streamlit UI
- [x] 검수 UI
- [x] OpenAI GPT 자동화 UI
- [x] 통계 UI
- [x] Ctrl+F5 통합 실행
- [x] dataset/errors 구분 로드
- [x] errors 하위 오류 유형 폴더 표시
- [x] combined/left/right 이미지 연결
- [x] JSON 라벨 읽기 및 수정 저장
- [x] 데이터셋 CSV 스캔
- [x] OpenAI Structured Output 기반 결과 CSV 저장
- [x] 기존 라벨과 GPT 결과 비교
- [x] 검수 대상 CSV 생성
- [x] 검수 UI에서 review_list.csv만 불러오기
- [x] GPT 결과와 원본 라벨 동시 비교 표시
- [x] 검수 결과 통계 화면
- [x] API 키 오류 메시지 마스킹
- [ ] reviewed_json 저장 결과를 원본/GPT 결과와 통계 비교
- [ ] 프롬프트 성능 개선
