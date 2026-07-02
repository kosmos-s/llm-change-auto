# LLM Change Auto

우송대학교 산학협력 과제용 **LLM/VLM 기반 항공영상 변경·변화탐지 학습데이터 자동 정제 도구**입니다.

이 프로젝트는 `dataset_sample` 또는 NAS 데이터에 포함된 2시점 항공영상 쌍을 대상으로 다음 작업을 수행합니다.

- `*_combined.jpg`, `*_left.jpg`, `*_right.jpg`, `*_combined.json` 파일 구조 읽기
- `dataset` 일반 학습데이터와 `errors` 오탐/미탐 검수데이터 구분
- 기존 JSON 라벨 확인 및 수정
- Streamlit 기반 육안검수 UI 제공
- LLM/VLM 자동 판단 결과 생성
- 기존 라벨과 LLM 결과 비교
- 육안검수 대상 CSV 생성

---

## 1. 현재 데이터 구조

현재 데이터는 아래 형태를 기준으로 사용합니다.

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

LLM 입력과 검수 UI의 기본 이미지는 `*_combined.jpg`입니다.  
`*_combined.json`은 기존 정답 라벨이며, UI에서 읽고 수정할 수 있습니다.

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

## 4. Streamlit 검수 UI 실행

```powershell
streamlit run app\reviewer_app.py
```

또는 VS Code에서 `app/reviewer_app.py` 파일을 열고 `Ctrl + F5`를 누릅니다.

브라우저가 열리면 왼쪽 사이드바에 데이터 루트 경로를 입력합니다.

```text
C:\Users\rlarj\Desktop\산학과제\dataset_sample
```

그 다음 아래 항목을 선택하고 `Load` 버튼을 누릅니다.

### 데이터 종류 선택

| 선택값 | 의미 |
|---|---|
| `dataset - 일반 학습데이터` | `dataset/test`, `dataset/train`, `dataset/val`에서 불러오기 |
| `errors - 오탐/미탐 검수데이터` | `errors/test`, `errors/train`, `errors/val`에서 불러오기 |
| `both - dataset + errors` | dataset과 errors를 함께 불러오기 |

### 분할 선택

| 선택값 | 의미 |
|---|---|
| `test` | 선택한 데이터 종류의 test만 불러오기 |
| `train` | 선택한 데이터 종류의 train만 불러오기 |
| `val` | 선택한 데이터 종류의 val만 불러오기 |
| `all` | 선택한 데이터 종류의 test + train + val 합치기 |

예를 들어 `errors` + `test`를 선택하면 아래 폴더만 읽습니다.

```text
dataset_sample/errors/test
```

`dataset` + `all`을 선택하면 아래 세 폴더만 읽습니다.

```text
dataset_sample/dataset/test
dataset_sample/dataset/train
dataset_sample/dataset/val
```

### UI 기능

- `dataset / errors / both` 선택
- `test / train / val / all` 선택
- `combined / left / right` 이미지 전환
- 현재 파일이 `dataset`인지 `errors`인지 화면에 표시
- `errors` 하위 오류 유형 폴더명 표시
- 체크박스로 라벨 수정
- `reason`, `reason (KO)` 수정
- `Previous File`, `Next File`, `Jump` 이동
- `Save Changes` 저장
- `Save & Next` 저장 후 다음 파일 이동

### 저장 방식

| 저장 방식 | 설명 |
|---|---|
| `reviewed_json 폴더에 저장` | 원본 JSON은 그대로 두고 `outputs/reviewed_json/{source}/{split}`에 저장 |
| `원본 JSON 덮어쓰기` | 기존 `*_combined.json` 파일을 바로 수정 |

처음에는 안전하게 `reviewed_json 폴더에 저장`을 사용하세요.

---

## 5. 데이터 인덱스 생성

검수 UI와 별도로 전체 데이터 목록 CSV를 만들 수 있습니다.

```powershell
python src\scan_dataset.py --root "C:\Users\rlarj\Desktop\산학과제\dataset_sample"
```

성공하면 아래 파일이 생성됩니다.

```text
outputs/dataset_index.csv
```

이 CSV에는 다음 정보가 저장됩니다.

- image_id
- combined 이미지 경로
- left/right 이미지 경로
- json 경로
- train/val/test 구분
- dataset/errors 구분
- 기존 JSON 라벨
- 기존 reason

---

## 6. LLM 자동 라벨링 실행

`.env.example`을 복사해서 `.env`를 만들고 API Key를 입력합니다.

```powershell
copy .env.example .env
```

`.env` 예시:

```text
OPENAI_API_KEY=your_api_key_here
```

10장만 테스트하려면 아래처럼 실행합니다.

```powershell
python src\run_llm_labeling.py --input outputs\dataset_index.csv --limit 10
```

결과 파일:

```text
outputs/llm_results/llm_results.csv
```

---

## 7. 기존 라벨과 LLM 결과 비교

```powershell
python src\compare_labels.py --llm outputs\llm_results\llm_results.csv
```

결과 파일:

```text
outputs/compare_results/compare_results.csv
```

육안검수 대상만 따로 만들려면:

```powershell
python src\make_review_list.py --compare outputs\compare_results\compare_results.csv
```

결과 파일:

```text
outputs/review_lists/review_required.csv
```

---

## 8. 폴더 구조

```text
llm-change-auto/
├─ app/
│  └─ reviewer_app.py
│
├─ config/
│  ├─ labels.yaml
│  ├─ paths.yaml
│  └─ model_config.yaml
│
├─ prompts/
│  ├─ prompt_v1_basic.txt
│  ├─ prompt_v2_guideline.txt
│  └─ prompt_v3_json_strict.txt
│
├─ src/
│  ├─ dataset_loader.py
│  ├─ json_io.py
│  ├─ scan_dataset.py
│  ├─ image_utils.py
│  ├─ llm_client.py
│  ├─ prompt_builder.py
│  ├─ parse_llm_result.py
│  ├─ run_llm_labeling.py
│  ├─ compare_labels.py
│  ├─ make_review_list.py
│  └─ metrics.py
│
├─ outputs/
│  ├─ llm_results/
│  ├─ compare_results/
│  ├─ review_lists/
│  └─ reviewed_json/
│
├─ logs/
├─ docs/
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

```powershell
pip install -r requirements.txt
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

- [x] dataset_sample 구조 인식
- [x] dataset/errors 구분 로드
- [x] errors 하위 오류 유형 폴더 표시
- [x] combined/left/right 이미지 연결
- [x] JSON 라벨 읽기
- [x] Streamlit 검수 UI
- [x] 수정 라벨 저장
- [x] 데이터셋 CSV 스캔
- [x] LLM 결과 CSV 저장 구조
- [x] 기존 라벨과 LLM 결과 비교 구조
- [ ] LLM 프롬프트 성능 개선
- [ ] 검수 결과 통계 화면 추가
- [ ] LLM 결과와 원본 라벨을 UI에서 동시에 비교하는 기능 추가
