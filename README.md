# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + OpenAI GPT 자동화 통합 도구**입니다.

GPT가 최종 변화탐지 모델을 대신하는 것이 아니라, 기존 학습데이터와 비교해 오류 후보를 찾고 사람이 빠르게 검수한 뒤 정제 데이터를 재학습에 사용할 수 있도록 만드는 도구입니다.

```text
OpenAI GPT 자동판정
→ 기존 JSON 라벨과 비교
→ 우선순위 검수 대상 추출
→ 사람 최종 검수
→ reviewed_json / 이벤트 이력 축적
→ 데이터 품질검사 / 품질 이슈 재검수
→ 버전별 정제 데이터 Snapshot
→ 변화탐지 모델 재학습
→ 기존 모델 vs 정제 모델 F2 비교
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
- `requirements-lock.txt`가 있으면 고정 버전으로 설치
- `.env` 생성
- 필요한 `outputs` 폴더 생성
- 기본 `dataset_sample` 경로 확인
- 데이터가 다른 위치에 있으면 Windows 폴더 연결(Junction) 시도
- 마지막에 `.env`를 메모장으로 열기

`.env`에서 본인의 OpenAI API Key를 입력합니다.

```text
OPENAI_API_KEY=your_real_api_key
OPENAI_TIMEOUT=60
DATASET_ROOT=
OPENAI_TARGET_TOTAL=3000
OPENAI_COST_LIMIT_USD=5
BACKUP_KEEP_COUNT=10
```

`DATASET_ROOT`를 비워두면 기본 위치를 사용합니다.

### 3. `run.bat` 실행

이후에는 `run.bat`을 더블클릭하면 됩니다.

브라우저가 자동으로 열리지 않으면:

```text
http://localhost:8501
```

자세한 설치 문제 해결은 [`TEAM_QUICKSTART.md`](TEAM_QUICKSTART.md)를 참고하세요.

---

## 기본 데이터 위치

기본 위치:

```text
%USERPROFILE%\Desktop\산학과제\dataset_sample
```

다른 위치를 사용하려면 `.env`에 입력할 수 있습니다.

```text
DATASET_ROOT=D:/ECTNFS_WSU/2026/dataset_sample
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

샘플 1건:

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

---

## 화면 사용 순서

```text
1. OpenAI 자동판정
2. 사람 검수
3. 검수 이력
4. 정제 데이터 생성
5. 작업 통계
6. LLM 결과 분석
7. 모델 성능 비교
```

### 1. OpenAI 자동판정

- `dataset / errors`, `train / val / test` 구분
- 데이터 인덱스 생성
- 데이터 무결성 검사
- OpenAI Structured Output 판정
- 매 이미지 처리 후 CSV 즉시 저장
- 중단 후 Resume / 성공 항목 Skip
- 실패 항목 Retry / checkpoint
- token / 비용 추정
- 순차 / 균형 / 랜덤 선택
- **3,000건 목표는 사람 검수 수가 아니라 OpenAI 본작업 고유 처리 수 기준**
- 본작업 기본 배치 1,000건
- 1,000건 초과 실행 확인 안전장치
- 토큰 단가가 0인 본작업은 명시적으로 허용해야 실행 가능
- 기본 비용 상한은 `.env`의 `OPENAI_COST_LIMIT_USD`

작업 순서:

```text
dataset_index.csv 생성
→ 데이터 무결성 검사
→ OpenAI 실행 / 이어서 처리
→ 비교 실행
→ 검수 목록 생성
```

### 2. 사람 검수

`LLM 검수 대상 CSV` 모드에서 가장 최근 `outputs/review_lists/*_review.csv`를 불러옵니다.

본작업 저장 위치:

```text
outputs/reviewed_json/
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

### 4. 정제 데이터 생성 / 품질관리

먼저 `Export 전 품질검사`를 실행합니다.

검사 항목:

- 필수 파일 누락
- 잘못된 JSON
- 중복 key
- 같은 group 내부 split leakage
- Artifact와 세부 인공물 라벨 논리
- orphan 파일 세트

품질검사 후 자동으로 `quality_action_plan.csv`가 생성됩니다. 원본 데이터를 자동 삭제하지 않으며, `artifact_logic` 같은 경고는 **품질 검수 목록 생성** 버튼으로 2번 사람 검수 화면에 전달할 수 있습니다.

`final*` 버전은 품질 Error가 1건이라도 있으면 Export가 강제로 차단됩니다.

Snapshot 예시:

```text
outputs/clean_datasets/clean_v1_3000/
├─ clean_dataset_manifest.csv
├─ quality_report.csv
├─ quality_action_plan.csv
├─ snapshot_summary.json
└─ json/
```

### 5. 작업 통계 / 백업

- OpenAI 고유 본작업 처리 건수 / 3,000 진행률
- 사람 검수 완료 수와 OpenAI 대비 검수율
- split / 오류유형별 현황
- 원본 라벨 수정률
- 클래스별 수정률
- GPT-사람 일치 특성
- `outputs` 중요 결과 ZIP 백업

백업은 다음 폴더에 저장됩니다.

```text
outputs/backups/project_outputs/
```

원본 항공영상은 백업 ZIP에 포함하지 않습니다. 기본 최근 10개를 유지합니다.

### 6. LLM 결과 분석

- Resume 등으로 CSV에 중복 행이 있어도 논리 샘플 키 기준 최신 1건만 분석
- `GPT ↔ 기존 JSON` 지표
- `GPT ↔ 사람 최종 라벨` 지표(검수 완료 항목만)

여기의 F2는 **GPT 비교용 F2**이며, 최종 변화탐지 모델 F2와 별도입니다.

### 7. 모델 성능 비교

재학습이 끝난 뒤 기존 모델과 정제 데이터 모델의 평가 결과를 비교합니다.

지원 입력:

- JSON: `precision`, `recall`, `f1`, `f2`
- CSV 1행 컬럼형
- CSV `metric,value` 형식
- UI 직접 입력

최종적으로 Before / After와 F2 0.85 목표를 한 화면에서 확인합니다.

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
→ 작업 통계 확인
→ outputs 백업
```

3,000건 전체 작업이 끝난 뒤:

```text
품질검사
→ split leakage / artifact_logic / orphan 확인
→ Error 0
→ final Snapshot 생성
→ 변화탐지 모델 재학습
→ 7. 모델 성능 비교
```

---

## 주요 outputs

```text
outputs/
├─ dataset_index.csv
├─ llm_results/
├─ compare_results/
├─ review_lists/
├─ reviewed_json/
├─ review_events/
├─ review_history/
├─ quality/
├─ clean_datasets/
├─ model_eval/
└─ backups/
   ├─ reviewed_json/
   └─ project_outputs/
```

본작업이 시작된 뒤 결과 폴더는 임의 삭제하지 않고 5번 화면에서 주기적으로 백업하는 것을 권장합니다.

---

## API Key / 보안

실제 API Key는 로컬 `.env`에만 둡니다.

`.env`, 원본 이미지, 실행 결과 CSV/JSON/ZIP은 `.gitignore` 대상입니다.

CI에서는:

```text
scripts/check_secrets.py
python -m unittest discover -s tests -v
```

를 실행해 대표적인 API Key 패턴과 회귀 테스트를 검사합니다. 자세한 내용은 [`SECURITY.md`](SECURITY.md)를 참고하세요.

---

## 수동 설치

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-lock.txt
copy .env.example .env
python -m streamlit run app\main_app.py
```

개발 중 최신 허용 범위로 설치하려면 `requirements.txt`를 사용할 수 있습니다.

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
→ 품질검사
→ 정제 Snapshot
```

순서를 유지합니다.
