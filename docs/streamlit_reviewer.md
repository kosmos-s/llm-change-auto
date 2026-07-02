# Streamlit 검수 UI 실행 방법

## 1. VS Code에서 열 폴더

`llm-change-auto` 폴더를 VS Code로 엽니다.

데이터 폴더는 코드 폴더와 같은 상위 폴더에 두는 것을 권장합니다.

```text
산학과제/
├─ dataset_sample
└─ llm-change-auto
```

## 2. 가상환경 생성 및 실행

```powershell
cd "산학과제\llm-change-auto"
py -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 3. 검수 UI 실행

```powershell
streamlit run app\reviewer_app.py
```

브라우저가 열리면 왼쪽 사이드바에 `dataset_sample` 경로를 입력하고 `Load Directory` 버튼을 누릅니다.

## 4. 사용 방법

- `combined`: LLM 입력용 합쳐진 이미지 보기
- `left`: 왼쪽 이미지 보기
- `right`: 오른쪽 이미지 보기
- 오른쪽 체크박스에서 라벨 수정
- `reason`, `reason (KO)` 입력
- `Save Changes` 클릭

## 5. 저장 방식

### 원본 JSON 덮어쓰기

기존 `*_combined.json` 파일을 바로 수정합니다.

### reviewed_json 폴더에 저장

원본 데이터는 그대로 두고 아래 위치에 수정본을 저장합니다.

```text
outputs/reviewed_json/{split}/파일명_combined.json
```

처음에는 안전하게 `reviewed_json 폴더에 저장` 방식을 추천합니다.
