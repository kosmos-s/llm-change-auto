# Streamlit 검수 UI 실행 방법

## 1. VS Code에서 열 폴더

`llm-change-auto` 폴더를 VS Code로 엽니다.

데이터 폴더는 코드 폴더와 같은 상위 폴더에 두는 것을 권장합니다.

```text
산학과제/
├─ dataset_sample
└─ llm-change-auto
```

지원하는 데이터 구조는 아래와 같습니다.

```text
dataset_sample/
├─ dataset/
│  ├─ test/
│  ├─ train/
│  └─ val/
└─ errors/
   ├─ test/
   ├─ train/
   └─ val/
```

`errors` 안에는 오류 유형별 하위 폴더가 있어도 됩니다.

```text
errors/test/artifact_fn_00
errors/test/artifact_fp_00
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

또는 VS Code에서 `app/reviewer_app.py`를 열고 `Ctrl + F5`를 누릅니다.

브라우저가 열리면 왼쪽 사이드바에 `dataset_sample` 경로를 입력하고 `Load` 버튼을 누릅니다.

## 4. 데이터 선택 방법

### 데이터 종류

- `dataset - 일반 학습데이터`: `dataset/test`, `dataset/train`, `dataset/val` 사용
- `errors - 오탐/미탐 검수데이터`: `errors/test`, `errors/train`, `errors/val` 사용
- `both - dataset + errors`: dataset과 errors를 같이 사용

### 분할 선택

- `test`: test만 보기
- `train`: train만 보기
- `val`: val만 보기
- `all`: test + train + val 전체 보기

예시:

```text
데이터 종류 = errors
분할 선택 = test
```

이렇게 선택하면 아래 폴더를 불러옵니다.

```text
dataset_sample/errors/test
```

## 5. 사용 방법

- `combined`: LLM 입력용 합쳐진 이미지 보기
- `left`: 왼쪽 이미지 보기
- `right`: 오른쪽 이미지 보기
- 현재 파일이 `dataset`인지 `errors`인지 화면에 표시
- `errors` 하위 오류 유형 폴더명을 화면에 표시
- 오른쪽 체크박스에서 라벨 수정
- `reason`, `reason (KO)` 입력
- `Save Changes` 또는 `Save & Next` 클릭

## 6. 저장 방식

### 원본 JSON 덮어쓰기

기존 `*_combined.json` 파일을 바로 수정합니다.

### reviewed_json 폴더에 저장

원본 데이터는 그대로 두고 아래 위치에 수정본을 저장합니다.

```text
outputs/reviewed_json/{source}/{split}/파일명_combined.json
```

오류 유형 하위 폴더가 있으면 그 구조도 유지됩니다.

```text
outputs/reviewed_json/errors/test/artifact_fn_00/파일명_combined.json
```

처음에는 안전하게 `reviewed_json 폴더에 저장` 방식을 추천합니다.
