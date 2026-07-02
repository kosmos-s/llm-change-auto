# Gemini 설정 및 실행 방법

OpenAI API 대신 Gemini API를 사용하도록 프로젝트를 수정했습니다.

## 1. 최신 코드 받기

```powershell
cd "C:\Users\rlarj\Desktop\산학과제\llm-change-auto"
git pull
```

## 2. 패키지 설치

`google-genai`가 추가되었으므로 가상환경을 켠 뒤 패키지를 다시 설치합니다.

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. .env 설정

프로젝트 루트의 `.env` 파일에 Gemini 키를 넣습니다.

```text
GEMINI_API_KEY=your_gemini_key_here
```

OpenAI 키는 없어도 Gemini 실행에는 필요하지 않습니다.

## 4. 통합 UI 실행

```powershell
python -m streamlit run app\main_app.py
```

또는 VS Code에서 아래 파일을 열고 `Ctrl + F5`를 누릅니다.

```text
app/run_app.py
```

## 5. 사용 순서

왼쪽 Pages에서 `LLM 자동화 UI`를 선택합니다. 이제 이 페이지는 Gemini 우선 실행 UI입니다.

추천 설정:

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 10
Gemini 모델: gemini-2.5-flash
프롬프트: prompts/prompt_v3_json_strict.txt
출력 파일 접두어: gemini_dataset_test_10
```

그 다음 순서대로 실행합니다.

```text
dataset_index.csv 생성
→ Gemini 실행
→ 비교 실행
→ 검수 목록 생성
```

## 6. 생성 파일 예시

```text
outputs/llm_results/gemini_dataset_test_10.csv
outputs/compare_results/gemini_dataset_test_10_compare.csv
outputs/review_lists/gemini_dataset_test_10_review.csv
```

생성 후 검수 UI에서 `LLM 검수 대상 CSV` 모드로 아래 파일을 불러오면 됩니다.

```text
outputs/review_lists/gemini_dataset_test_10_review.csv
```
