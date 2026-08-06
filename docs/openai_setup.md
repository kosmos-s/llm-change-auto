# OpenAI API 설정 및 실행 방법

이 프로젝트의 자동라벨링 경로는 OpenAI GPT 전용입니다.

## 1. 보안 원칙

- API 키를 Streamlit 화면에 입력하지 않습니다.
- API 키를 Python 코드, CSV, JSON, 로그에 저장하지 않습니다.
- 프로젝트 루트의 로컬 `.env` 파일에서만 `OPENAI_API_KEY`를 읽습니다.
- `.env`는 `.gitignore`에 의해 GitHub 커밋 대상에서 제외됩니다.
- API 오류 메시지에 키 형태 문자열이 포함되면 `[REDACTED_API_KEY]`로 가린 뒤 저장합니다.

## 2. 최신 코드 받기

```powershell
cd "C:\Users\rlarj\Desktop\산학과제\llm-change-auto"
git pull
```

## 3. 패키지 설치

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. `.env` 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 값만 입력합니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

`.env` 파일을 GitHub에 올리거나 채팅, 화면 캡처, 문서에 포함하지 마세요.

## 5. 통합 UI 실행

```powershell
python -m streamlit run app\main_app.py
```

또는 VS Code에서 아래 파일을 열고 `Ctrl + F5`를 누릅니다.

```text
app/run_app.py
```

## 6. 첫 테스트 설정

```text
데이터 종류: dataset
분할: test
시작 번호: 0
개수: 1
OpenAI 모델: gpt-4o-mini
프롬프트: prompts/prompt_v3_json_strict.txt
출력 파일 접두어: openai_dataset_test_1
```

실행 순서:

```text
dataset_index.csv 생성
→ OpenAI 실행
→ 비교 실행
→ 검수 목록 생성
```

생성 파일 예시:

```text
outputs/llm_results/openai_dataset_test_1.csv
outputs/compare_results/openai_dataset_test_1_compare.csv
outputs/review_lists/openai_dataset_test_1_review.csv
```
