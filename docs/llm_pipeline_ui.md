# LLM 자동화 UI 실행 방법

이 UI는 터미널 명령어로 하던 아래 과정을 웹 화면에서 버튼으로 실행합니다.

```text
데이터 인덱스 생성 → LLM 자동판별 → 기존 JSON 라벨과 비교 → 검수 대상 CSV 생성
```

## 1. 실행

```powershell
streamlit run app\llm_pipeline_app.py
```

또는 VS Code에서 `app/llm_pipeline_app.py`를 열고 `Ctrl + F5`를 누른 뒤 `LLM 자동화 UI 실행 (Streamlit)`을 선택합니다.

## 2. 사전 준비

`.env` 파일에 OpenAI API Key가 있어야 합니다.

```text
OPENAI_API_KEY=your_api_key_here
```

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

그 다음 `dataset_index.csv 생성` 버튼을 누릅니다.

생성 파일:

```text
outputs/dataset_index.csv
```

### 2단계: LLM 자동판별

왼쪽에서 아래 값을 선택합니다.

```text
데이터 종류: dataset / errors / all
분할: test / train / val / all
개수: 10
모델: gpt-4o-mini
프롬프트: prompts/prompt_v3_json_strict.txt
```

`LLM 실행` 버튼을 누릅니다.

생성 파일 예시:

```text
outputs/llm_results/dataset_test_10.csv
```

### 3단계: 기존 라벨과 비교

`비교 실행` 버튼을 누릅니다.

생성 파일 예시:

```text
outputs/compare_results/dataset_test_10_compare.csv
```

### 4단계: 검수 대상 목록 생성

`검수 목록 생성` 버튼을 누릅니다.

생성 파일 예시:

```text
outputs/review_lists/dataset_test_10_review.csv
```

## 4. 주요 컬럼

| 컬럼 | 의미 |
|---|---|
| `llm_change` | LLM이 판단한 변화유무 |
| `confidence` | LLM 판단 신뢰도 |
| `label_mismatch` | 기존 변화유무 라벨과 LLM 변화유무가 다름 |
| `detail_mismatch` | 기존 세부 라벨과 LLM 세부 라벨이 다름 |
| `review_reasons` | 검수 대상으로 선정된 이유 |
| `review_required_final` | 최종 육안검수 필요 여부 |

## 5. 권장 실험 순서

처음에는 아래 조건으로 작게 테스트합니다.

```text
source = dataset
split = test
limit = 10
```

정상 동작을 확인한 뒤 `errors/test`, `dataset/train`, `dataset/all`로 확장합니다.
