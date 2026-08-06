# OpenAI 자동화 UI 실행 방법

이 UI는 아래 과정을 웹 화면에서 버튼으로 실행합니다.

```text
데이터 인덱스 생성 → OpenAI GPT 자동판별 → 기존 JSON 라벨과 비교 → 검수 대상 CSV 생성
```

## 1. 실행

```powershell
python -m streamlit run app\main_app.py
```

또는 VS Code에서 `app/run_app.py`를 열고 `Ctrl + F5`를 누릅니다.

## 2. API Key 보안

`.env` 파일에만 OpenAI API Key를 저장합니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

API 키는 Streamlit 입력창, Python 코드, CSV, JSON, 로그에 넣지 않습니다. `.env`는 `.gitignore`에 의해 GitHub에서 제외됩니다. API 오류 메시지에 키 형태 문자열이 포함되면 결과 파일에 저장하기 전에 가립니다.

필요 패키지는 아래 명령어로 설치합니다.

```powershell
pip install -r requirements.txt
```

## 3. 사용 순서

### 1단계: 데이터 인덱스 생성

왼쪽에서 데이터 루트 경로를 입력합니다.

```text
C:\Users\rlarj\Desktop\산학과제\dataset_sample
```

`dataset_index.csv 생성` 버튼을 누릅니다.

```text
outputs/dataset_index.csv
```

### 2단계: OpenAI 자동판별

처음에는 1장만 실행합니다.

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 1
OpenAI 모델: gpt-4o-mini
프롬프트: prompts/prompt_v3_json_strict.txt
출력 파일 접두어: openai_dataset_test_1
```

`OpenAI 실행` 버튼을 누릅니다.

```text
outputs/llm_results/openai_dataset_test_1.csv
```

### 3단계: 기존 라벨과 비교

`비교 실행` 버튼을 누릅니다.

```text
outputs/compare_results/openai_dataset_test_1_compare.csv
```

### 4단계: 검수 대상 목록 생성

`검수 목록 생성` 버튼을 누릅니다.

```text
outputs/review_lists/openai_dataset_test_1_review.csv
```

## 4. 주요 컬럼

| 컬럼 | 의미 |
|---|---|
| `llm_provider` | 항상 `openai` |
| `llm_model` | 실행한 OpenAI 모델 |
| `llm_change` | GPT가 판단한 변화유무 |
| `confidence` | GPT 판단 신뢰도 |
| `label_mismatch` | 기존 변화유무 라벨과 GPT 판단이 다름 |
| `detail_mismatch` | 기존 세부 라벨과 GPT 세부 라벨이 다름 |
| `review_reasons` | 검수 대상으로 선정된 이유 |
| `review_required_final` | 최종 육안검수 필요 여부 |
| `error` | 키 문자열을 가린 실행 오류 |

## 5. 권장 실험 순서

```text
1장 → 3장 → 10장 → 50장
```

각 단계에서 `error` 컬럼이 비어 있는지 확인한 뒤 다음 규모로 늘립니다.
