# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + OpenAI GPT 자동화 통합 도구**입니다.

GPT가 최종 변화탐지 모델을 대신하는 것이 아니라, 기존 학습데이터와 비교해 오류 후보를 찾고 사람이 빠르게 검수한 뒤 정제 데이터를 재학습에 사용할 수 있도록 만드는 도구입니다.

```text
OpenAI GPT 자동판정
→ 기존 JSON 라벨과 비교
→ 우선순위 검수 대상 추출
→ 사람 최종 검수
→ reviewed_json / 이벤트 이력 축적
→ 버전별 정제 데이터 Snapshot
→ 변화탐지 모델 재학습·평가
```

산학과제 최종 목표인 **F2-Score 0.85**는 GPT 일치율이 아니라, 정제된 데이터로 재학습한 변화탐지 모델의 성능 목표입니다.

---

## 팀원 빠른 시작 (Windows)

처음 받는 PC에서는 저장소 루트의 파일 두 개만 기억하면 됩니다.

```text
setup.bat   ← 최초 1회
run.bat     ← 이후 실행
```

### 1. 저장소 받기

```powershell
git clone https://github.com/kosmos-s/llm-change-auto.git
cd llm-change-auto
```

ZIP 다운로드 후 압축을 풀어도 됩니다.

### 2. `setup.bat` 실행

자동으로 다음 작업을 수행합니다.

- `.venv` 생성
- `requirements.txt` 설치
- `.env` 생성
- 필요한 `outputs` 폴더 생성
- 기본 `dataset_sample` 경로 확인
- 데이터가 다른 위치에 있으면 Windows 폴더 연결(Junction) 시도
- 마지막에 `.env`를 메모장으로 열기

`.env`에서 본인의 OpenAI API Key를 입력합니다.

```text
OPENAI_API_KEY=your_real_api_key
OPENAI_TIMEOUT=60
```

### 3. `run.bat` 실행

이후에는 `run.bat`을 더블클릭하면 됩니다.

브라우저가 자동으로 열리지 않으면:

```text
http://localhost:8501
```

자세한 설치 문제 해결은 [`TEAM_QUICKSTART.md`](TEAM_QUICKSTART.md)를 참고하세요.

---

## 기본 데이터 위치

프로그램에서 가장 편하게 사용할 수 있는 기본 위치는 다음입니다.

```text
%USERPROFILE%\Desktop\산학과제\dataset_sample
```

권장 구조:

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

샘플 1건의 기본 구조:

```text
00_xxxx_combined.jpg
00_xxxx_combined.json
00_xxxx_left.jpg
00_xxxx_right.jpg
```

`errors`에는 오류유형 폴더가 추가될 수 있습니다.

```text
errors/train/artifact_fn_00/
errors/train/artifact_fp_00/
errors/train/farmland_fp_00/
```

데이터가 다른 위치에 있어도 `setup.bat`에서 연결하거나, 앱의 **1. OpenAI 자동판정** 화면에서 직접 경로를 입력할 수 있습니다.

---

## 화면 사용 순서

```text
1. OpenAI 자동판정
2. 사람 검수
3. 검수 이력
4. 정제 데이터 생성
5. 작업 통계
6. LLM 결과 분석
```

### 1. OpenAI 자동판정

- `dataset / errors`, `train / val / test` 구분
- 데이터 인덱스 생성
- 데이터 무결성 검사
- OpenAI Structured Output 판정
- 매 이미지 처리 후 CSV 즉시 저장
- 중단 후 Resume
- 성공 항목 자동 Skip
- 실패 항목 Retry
- checkpoint 저장
- token / 비용 추정
- 순차 / 균형 / 랜덤 선택

작업 순서:

```text
dataset_index.csv 생성
→ 데이터 무결성 검사
→ OpenAI 실행 / 이어서 처리
→ 비교 실행
→ 검수 목록 생성
```

### 2. 사람 검수

`LLM 검수 대상 CSV` 모드에서 `outputs/review_lists/*_review.csv`를 불러옵니다.

본작업 저장 위치:

```text
reviewed_json 폴더에 저장
```

원본 JSON 직접 덮어쓰기는 권장하지 않습니다.

### 3. 검수 이력

```text
검수 이력 갱신
```

주요 결과:

```text
outputs/review_history/review_history.csv
outputs/review_events/review_events.csv
outputs/backups/reviewed_json/
```

### 4. 정제 데이터 생성

먼저 `Export 전 품질검사`를 실행한 뒤 snapshot을 생성합니다.

```text
clean_v1
clean_v2
final
```

예시:

```text
outputs/clean_datasets/clean_v1/
├─ clean_dataset_manifest.csv
├─ quality_report.csv
├─ snapshot_summary.json
└─ json/
```

### 5. 작업 통계

- OpenAI 고유 처리 건수
- 사람 검수 완료 수
- split / 오류유형별 검수량
- 원본 라벨 수정률
- 클래스별 수정률
- GPT-사람 일치 특성

### 6. LLM 결과 분석

GPT와 현재 JSON 라벨의 비교 지표를 확인합니다.

여기의 F2는 **GPT 비교용 F2**이고, 최종 변화탐지 모델 F2와는 별도입니다.

---

## 3,000건 본작업 기본 계획

```text
errors / train : 1,000건
errors / val   : 1,000건
errors / test  : 1,000건
------------------------
총 OpenAI 판정 : 3,000건
```

각 split마다:

```text
OpenAI 실행
→ 기존 JSON 비교
→ 검수 목록 생성
→ 후보만 사람 검수
→ 검수 이력 갱신
```

3,000건 전체 작업이 끝난 뒤:

```text
품질검사
→ Error 0 확인
→ 최종 Snapshot 생성
→ 변화탐지 모델 재학습
→ Before / After F2 비교
```

---

## 주요 outputs

```text
outputs/
├─ dataset_index.csv
├─ llm_results/
│  ├─ *.csv
│  └─ *.checkpoint.json
├─ compare_results/
├─ review_lists/
├─ reviewed_json/
├─ review_events/
│  └─ review_events.csv
├─ review_history/
│  └─ review_history.csv
├─ backups/
│  └─ reviewed_json/
├─ quality/
│  └─ dataset_quality.csv
└─ clean_datasets/
```

본작업이 시작된 뒤 `llm_results`, `review_lists`, `reviewed_json`, `review_events`, `review_history`는 임의 삭제하지 않는 것을 권장합니다.

---

## API Key / 보안

실제 API Key는 프로젝트 루트의 로컬 `.env`에만 둡니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

`.env`, 원본 이미지, 실행 결과 CSV/JSON은 GitHub에 올리지 않도록 `.gitignore` 처리되어 있습니다.

모델 가격은 변경될 수 있으므로 비용 추정 단가는 UI에서 현재 가격을 직접 입력하는 것을 권장합니다.

---

## 수동 설치가 필요한 경우

`setup.bat`을 사용할 수 없다면:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m streamlit run app\main_app.py
```

---

## 중요 원칙

```text
GPT 결과 ≠ 최종 정답
```

GPT와 기존 JSON이 다르다는 이유만으로 기존 라벨을 자동 수정하지 않습니다.

```text
GPT 자동판정
→ 오류 후보 선정
→ 사람 검수
→ reviewed_json 확정
```

순서를 유지합니다.
