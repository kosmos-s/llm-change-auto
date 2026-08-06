# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + OpenAI GPT 자동화 통합 도구**입니다.

프로젝트의 역할은 GPT가 최종 변화탐지 모델을 대신하는 것이 아니라, 학습데이터의 오류 후보를 찾고 사람이 빠르게 검수할 수 있도록 돕는 것입니다.

```text
GPT 자동판별
→ 기존 JSON 라벨과 비교
→ 검수 대상 추출
→ 사람이 최종 라벨 확정
→ 검수 이력 및 정제 데이터 축적
→ 변화탐지 모델 재학습·평가
```

산학과제의 최종 목표인 **F2-Score 0.85**는 GPT 일치율이 아니라, 정제된 데이터로 재학습한 변화탐지 모델의 성능 목표입니다.

---

## 1. 주요 기능

- `*_combined.jpg`, `*_left.jpg`, `*_right.jpg`, `*_combined.json` 구조 읽기
- `dataset` 일반 데이터와 `errors` 오탐·미탐 데이터 구분
- 기존 JSON 라벨 확인 및 수정
- OpenAI GPT 기반 변화유무·세부 라벨 자동판단
- 기존 JSON 라벨과 GPT 결과 비교
- 검수 대상 CSV 생성
- 검수 대상만 검수 UI에서 순서대로 확인
- 사람 확정 라벨을 `reviewed_json`으로 별도 저장
- 원본·GPT·사람 라벨을 `review_history.csv`로 연결
- LLM 결과 분석과 최종 변화탐지 모델 F2 평가를 분리

---

## 2. 데이터 구조

권장 로컬 구조:

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

각 데이터 폴더 안에는 보통 아래 파일이 있습니다.

```text
00_xxxx_combined.jpg
00_xxxx_combined.json
00_xxxx_left.jpg
00_xxxx_right.jpg
```

`errors` 폴더에는 오류 유형별 하위 폴더가 있을 수 있습니다.

```text
errors/test/artifact_fn_00/
errors/test/artifact_fp_00/
```

---

## 3. API Key 보안 원칙

- 실제 API 키는 프로젝트 루트의 로컬 `.env`에만 저장합니다.
- API 키를 Streamlit 화면, Python 코드, CSV, JSON, 로그에 넣지 않습니다.
- `.env`와 `.env.*`는 `.gitignore`에서 제외됩니다.
- `.env.example`에는 예시 값만 둡니다.
- OpenAI SDK가 `OPENAI_API_KEY` 환경변수를 직접 읽습니다.
- 오류 메시지에 키 형태 문자열이 포함되면 `[REDACTED_API_KEY]`로 가립니다.
- 원본 이미지와 실행 결과 CSV는 GitHub에 업로드하지 않습니다.

`.env` 예시:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

---

## 4. 설치

```powershell
cd "C:\Users\rlarj\Desktop\산학과제\llm-change-auto"
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

이미 가상환경이 있으면:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 5. 통합 UI 실행

VS Code에서:

```text
app/run_app.py 열기 → Ctrl + F5
```

터미널에서:

```powershell
python -m streamlit run app\main_app.py
```

브라우저 주소:

```text
http://localhost:8501
```

통합 UI 페이지:

| 페이지 | 역할 |
|---|---|
| `검수 UI` | 이미지 확인, JSON 라벨 수정, GPT 검수 대상 확인 |
| `LLM 자동화 UI` | 데이터 인덱스 생성, GPT 실행, 비교, 검수 목록 생성 |
| `통계 UI` | CSV 결과와 reviewed_json 저장 현황 요약 |
| `LLM 결과 분석` | GPT와 현재 JSON 라벨의 일치·불일치 특성 분석 |
| `검수 이력` | 원본·GPT·사람 확정 라벨을 하나의 CSV로 연결 |

---

## 6. OpenAI 자동화 순서

첫 테스트 권장 설정:

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 1
OpenAI 모델: gpt-4o-mini
프롬프트: prompts/prompt_v4_quality.txt
출력 파일 접두어: openai_dataset_test_1
```

버튼 실행 순서:

```text
dataset_index.csv 생성
→ OpenAI 실행
→ 비교 실행
→ 검수 목록 생성
```

생성 파일:

```text
outputs/dataset_index.csv
outputs/llm_results/openai_dataset_test_1.csv
outputs/compare_results/openai_dataset_test_1_compare.csv
outputs/review_lists/openai_dataset_test_1_review.csv
```

1장이 정상 처리되고 `error` 컬럼이 비어 있는 것을 확인한 뒤 `3장 → 10장 → 50장` 순서로 늘립니다.

---

## 7. 검수 UI 사용

검수 모드:

```text
폴더 전체 검수
LLM 검수 대상 CSV
```

검수 대상 CSV 예시:

```text
outputs/review_lists/openai_dataset_test_1_review.csv
```

검수 화면에서 확인할 정보:

- 현재 JSON 라벨
- GPT 라벨
- confidence
- 변화유무 불일치
- 세부 라벨 불일치
- 검수 대상 선정 이유
- GPT 판단 근거

저장 방식:

| 저장 방식 | 설명 |
|---|---|
| `reviewed_json 폴더에 저장` | 원본 JSON을 유지하고 사람 확정본을 별도 저장 |
| `원본 JSON 덮어쓰기` | 기존 JSON을 직접 수정 |

처음에는 반드시 `reviewed_json 폴더에 저장`을 사용합니다.

---

## 8. LLM 결과 분석

`LLM 결과 분석` 페이지는 GPT 보조도구의 특성을 확인하기 위한 화면입니다.

표시 항목:

- 변화유무 정확도
- Precision
- Recall
- F1
- GPT 비교용 F2
- TP / TN / FP / FN
- 세부 라벨 평균 일치율
- 세부 라벨 완전 일치율

주의:

```text
여기서 표시되는 F2
= GPT 결과와 현재 JSON 라벨을 비교한 값

산학과제 최종 F2 0.85
= 정제 데이터로 재학습한 변화탐지 모델의 평가값
```

두 값을 같은 성능으로 해석하면 안 됩니다.

---

## 9. 검수 이력

검수 UI에서 `reviewed_json`으로 저장한 뒤 `검수 이력` 페이지에서 다음 버튼을 누릅니다.

```text
검수 이력 갱신
```

생성 파일:

```text
outputs/review_history/review_history.csv
```

주요 컬럼:

```text
image_id
source
split
original_change
llm_change
human_change
original_* 라벨
llm_* 라벨
human_* 라벨
labels_modified
modified_keys
review_status
reviewed_at
```

현재 버전은 각 `reviewed_json` 파일의 최신 저장 상태를 기준으로 이력을 만듭니다. 같은 파일의 저장 시점별 이벤트 로그는 후속 단계에서 추가합니다.

---

## 10. 현재 프로젝트 구조

```text
llm-change-auto/
├─ app/
│  ├─ main_app.py
│  ├─ run_app.py
│  ├─ reviewer_app.py
│  ├─ llm_pipeline_app.py
│  └─ pages/
│     ├─ 1_검수_UI.py
│     ├─ 2_LLM_자동화_UI.py
│     ├─ 3_통계_UI.py
│     ├─ 4_LLM_결과_분석.py
│     └─ 5_검수_이력.py
│
├─ src/
│  ├─ dataset_loader.py
│  ├─ json_io.py
│  ├─ scan_dataset.py
│  ├─ llm_client.py
│  ├─ run_llm_labeling.py
│  ├─ compare_labels.py
│  ├─ make_review_list.py
│  ├─ evaluate_results.py
│  ├─ build_review_history.py
│  └─ ...
│
├─ prompts/
│  ├─ prompt_v1_basic.txt
│  ├─ prompt_v2_guideline.txt
│  ├─ prompt_v3_json_strict.txt
│  └─ prompt_v4_quality.txt
│
├─ outputs/
│  ├─ llm_results/
│  ├─ compare_results/
│  ├─ review_lists/
│  ├─ reviewed_json/
│  └─ review_history/
├─ config/
├─ docs/
├─ tests/
├─ .env.example
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## 11. 현재 구현 상태

- [x] 통합 Streamlit UI
- [x] 검수 UI
- [x] OpenAI GPT 자동화 UI
- [x] 통계 UI
- [x] LLM 결과 분석
- [x] 검수 이력 CSV 생성
- [x] dataset/errors 및 train/val/test 구분
- [x] combined/left/right 이미지 표시
- [x] JSON 라벨 수정 및 별도 저장
- [x] OpenAI Structured Output 결과 저장
- [x] 기존 라벨과 GPT 결과 비교
- [x] 검수 대상 CSV 생성
- [x] API 키 오류 메시지 마스킹
- [ ] 저장 버튼을 누를 때마다 이벤트 단위 검수 이력 자동 추가
- [ ] 정제 학습데이터 내보내기
- [ ] 엘컴텍 변화탐지 모델 재학습 전·후 F2 비교
