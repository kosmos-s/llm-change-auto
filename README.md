# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + LLM 자동화 통합 도구**입니다.

이 프로젝트는 `dataset_sample` 또는 NAS 데이터에 포함된 2시점 항공영상 쌍을 대상으로 다음 작업을 수행합니다.

- `*_combined.jpg`, `*_left.jpg`, `*_right.jpg`, `*_combined.json` 파일 구조 읽기
- `dataset` 일반 학습데이터와 `errors` 오탐/미탐 검수데이터 구분
- 기존 JSON 라벨 확인 및 수정
- LLM/VLM 자동 변화유무 판단
- 기존 JSON 라벨과 LLM 결과 비교
- 육안검수 대상 CSV 생성
- Streamlit 통합 UI 제공

---

## 1. 현재 데이터 구조

권장 로컬 구조는 아래와 같습니다.

```text
산학과제/
├─ dataset_sample/
│  ├─ dataset/
│  │  ├─ train/
│  │  ├─ val/
│  │  └─ test/
│  │
│  └─ errors/
│     ├─ train/
│     ├─ val/
│     └─ test/
│
└─ llm-change-auto/
   ├─ app/
   ├─ src/
   ├─ prompts/
   ├─ config/
   ├─ outputs/
   └─ docs/
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
errors/
└─ test/
   ├─ artifact_fn_00/
   ├─ artifact_fp_00/
   └─ ...
```

NAS 전체 데이터처럼 아래 구조도 지원합니다.

```text
2026/
└─ dataset/
   ├─ train/
   ├─ val/
   ├─ test/
   └─ errors/
      ├─ train/
      ├─ val/
      └─ test/
```

---

## 2. 중요 원칙

원본 이미지 데이터는 GitHub에 업로드하지 않습니다.

- 원본 데이터는 NAS 또는 로컬 데이터 폴더에서만 읽습니다.
- GitHub에는 코드, 프롬프트, 설정 파일, 문서만 저장합니다.
- `.env` 파일과 API Key는 절대 커밋하지 않습니다.
- 처음 검수할 때는 원본 JSON 덮어쓰기보다 `reviewed_json 폴더에 저장` 방식을 권장합니다.

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

이미 가상환경을 만든 적이 있으면 아래만 다시 실행하면 됩니다.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 4. 통합 UI 실행

이제 검수 UI와 LLM 자동화 UI를 하나의 Streamlit 앱에서 사용합니다.

### VS Code 실행

```text
app/run_app.py 열기 → Ctrl + F5
```

### 터미널 실행

```powershell
python -m streamlit run app\main_app.py
```

브라우저 주소는 하나만 사용합니다.

```text
http://localhost:8501
```

왼쪽 사이드바의 **Pages**에서 아래 페이지를 선택합니다.

| 페이지 | 역할 |
|---|---|
| `검수 UI` | 이미지 확인, JSON 라벨 수정, reason 입력 |
| `LLM 자동화 UI` | 데이터 인덱스 생성, LLM 실행, 라벨 비교, 검수 목록 생성 |

---

## 5. 검수 UI 기능

검수 UI에서는 아래 작업을 할 수 있습니다.

- `dataset / errors / both` 선택
- `test / train / val / all` 선택
- `combined / left / right` 이미지 전환
- 현재 파일이 `dataset`인지 `errors`인지 표시
- `errors` 하위 오류 유형 폴더명 표시
- 체크박스로 라벨 수정
- `reason`, `reason (KO)` 수정
- `Previous File`, `Next File`, `Jump` 이동
- `Save Changes` 저장
- `Save & Next` 저장 후 다음 파일 이동

저장 방식은 두 가지입니다.

| 저장 방식 | 설명 |
|---|---|
| `reviewed_json 폴더에 저장` | 원본 JSON은 그대로 두고 `outputs/reviewed_json/{source}/{split}`에 저장 |
| `원본 JSON 덮어쓰기` | 기존 `*_combined.json` 파일을 바로 수정 |

처음에는 안전하게 `reviewed_json 폴더에 저장`을 사용하세요.

---

## 6. LLM 자동화 UI 기능

LLM 자동화 UI에서는 터미널 명령어로 하던 아래 과정을 버튼으로 실행합니다.

```text
데이터 인덱스 생성
→ LLM 자동판별
→ 기존 JSON 라벨과 비교
→ 검수 대상 CSV 생성
```

처음 테스트 권장 설정입니다.

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 10
모델: gpt-4o-mini
프롬프트: prompts/prompt_v3_json_strict.txt
출력 파일 접두어: dataset_test_10
```

생성되는 주요 파일은 아래와 같습니다.

```text
outputs/dataset_index.csv
outputs/llm_results/dataset_test_10.csv
outputs/compare_results/dataset_test_10_compare.csv
outputs/review_lists/dataset_test_10_review.csv
```

---

## 7. API Key 설정

LLM 자동화 실행 전 `.env.example`을 복사해서 `.env`를 만들고 API Key를 입력합니다.

```powershell
copy .env.example .env
```

`.env` 예시:

```text
OPENAI_API_KEY=your_api_key_here
```

`.env`는 `.gitignore`에 의해 GitHub에 올라가지 않습니다.

---

## 8. 현재 프로젝트 구조

```text
llm-change-auto/
├─ app/
│  ├─ main_app.py                 # 통합 UI 메인
│  ├─ run_app.py                  # Ctrl+F5 실행용
│  ├─ reviewer_app.py             # 검수 UI 본체
│  ├─ llm_pipeline_app.py         # LLM 자동화 UI 본체
│  ├─ run_reviewer.py             # 통합 UI 호환 실행 파일
│  ├─ run_llm_pipeline.py         # 통합 UI 호환 실행 파일
│  └─ pages/
│     ├─ 1_검수_UI.py
│     └─ 2_LLM_자동화_UI.py
│
├─ src/
│  ├─ dataset_loader.py           # 검수 UI용 dataset/errors 로더
│  ├─ json_io.py                  # JSON 라벨 읽기/저장
│  ├─ scan_dataset.py             # 전체 데이터 CSV 인덱스 생성
│  ├─ llm_client.py               # OpenAI Vision 호출
│  ├─ run_llm_labeling.py         # LLM 자동 라벨링 실행
│  ├─ compare_labels.py           # 기존 라벨과 LLM 결과 비교
│  ├─ make_review_list.py         # 검수 대상 CSV 생성
│  ├─ summarize_results.py        # CSV 요약 출력
│  ├─ image_utils.py
│  ├─ prompt_builder.py
│  ├─ parse_llm_result.py
│  └─ metrics.py
│
├─ prompts/
│  ├─ prompt_v1_basic.txt
│  ├─ prompt_v2_guideline.txt
│  └─ prompt_v3_json_strict.txt
│
├─ config/
│  ├─ labels.yaml
│  ├─ paths.yaml
│  └─ model_config.yaml
│
├─ outputs/
│  ├─ llm_results/
│  ├─ compare_results/
│  ├─ review_lists/
│  └─ reviewed_json/
│
├─ docs/
├─ logs/
├─ .vscode/
│  ├─ launch.json
│  └─ settings.json
├─ .env.example
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## 9. 자주 생기는 문제

### PowerShell에서 가상환경 실행 오류

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### streamlit 명령어를 찾을 수 없음

가상환경을 켠 뒤 아래 명령어를 실행합니다.

```powershell
pip install -r requirements.txt
```

그래도 안 되면 아래처럼 실행합니다.

```powershell
python -m streamlit run app\main_app.py
```

### Load를 눌렀는데 파일이 안 나옴

경로가 데이터 루트까지 맞는지 확인하세요.

```text
올바른 예: C:\Users\rlarj\Desktop\산학과제\dataset_sample
잘못된 예: C:\Users\rlarj\Desktop\산학과제\dataset_sample\dataset\test
```

앱에서 `dataset/errors`와 `test/train/val`은 사이드바에서 선택합니다.

---

## 10. 현재 구현 상태

- [x] 통합 Streamlit UI
- [x] 검수 UI
- [x] LLM 자동화 UI
- [x] Ctrl+F5 통합 실행
- [x] dataset/errors 구분 로드
- [x] errors 하위 오류 유형 폴더 표시
- [x] combined/left/right 이미지 연결
- [x] JSON 라벨 읽기
- [x] 수정 라벨 저장
- [x] 데이터셋 CSV 스캔
- [x] LLM 결과 CSV 저장
- [x] 기존 라벨과 LLM 결과 비교
- [x] 검수 대상 CSV 생성
- [ ] 검수 UI에서 review_list.csv만 불러오기
- [ ] LLM 결과와 원본 라벨을 검수 UI에서 동시에 비교 표시
- [ ] 검수 결과 통계 화면 추가
