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

산학과제의 최종 목표인 **F2-Score 0.85**는 GPT 일치율이 아니라, 정제된 데이터로 재학습한 변화탐지 모델의 성능 목표입니다.

---

## 1. 현재 주요 기능

### OpenAI 자동판정

- `dataset / errors`, `train / val / test` 구분
- `*_combined.jpg`, `*_left.jpg`, `*_right.jpg`, `*_combined.json` 매칭
- OpenAI Structured Output 기반 변화유무·세부라벨 판정
- 처리 진행률, 현재 image_id, 성공/오류 수, 경과시간, ETA 표시
- **이미지 1건 처리할 때마다 결과 CSV 즉시 저장**
- 중단 후 같은 결과 파일로 **Resume**
- 성공한 항목 자동 Skip
- 실패 항목만 재시도
- API 오류 자동 Retry + exponential backoff
- run_id / batch_id / 처리시각 / 모델 / prompt 경로 기록
- checkpoint JSON 자동 저장
- 입력·출력 token 사용량 기록
- 사용자가 입력한 현재 API 단가 기준 비용 추정 및 비용 상한
- 순차 / 랜덤 / 오류유형 균형 선택
- 이미 사람 검수한 항목 자동 제외 옵션
- 테스트/본작업 파일 prefix 분리

### 검수 대상 선정

- 기존 JSON ↔ GPT 변화유무 비교
- 세부라벨 불일치 비교
- Low confidence
- API 오류
- GPT 자체 review_required
- 변화인데 세부 class가 비어 있는 경우
- 위 조건을 조합한 `priority_score` 생성
- API 오류 / 라벨 불일치 / 낮은 confidence 순으로 우선 검수

### 사람 검수

- LLM 검수 대상 CSV 로드
- 미검수만 보기
- 보류 항목 제외
- 라벨 불일치 / Low confidence / API 오류 필터
- errors 유형 / GPT class 필터
- 검수 목록 진행률
- 원본 ↔ GPT 비교표
- 기존 reviewed_json이 있으면 그 값을 다시 불러오기
- `저장`, `저장 + 다음`, `보류 + 다음`
- reviewed_json 재저장 전 이전 버전 자동 백업
- 검수 메모 저장

### 검수 이력

- `review_history.csv`: 원본·GPT·사람 최종 라벨 연결
- `review_events.csv`: 저장/보류 이벤트 append-only 기록
- 수정 전·후 상태와 변경된 key 기록
- batch / run / 모델 / prompt 메타데이터 연결

### 데이터 품질 / Export

- missing combined / left / right / JSON 검사
- 잘못된 JSON 검사
- 중복 key 검사
- 동일 image_id의 split 누수 검사
- Artifact와 세부 인공물 라벨 논리 검사
- 고아 파일 세트 검사
- Export 전 품질검사
- 무결성 error가 있으면 Export 차단 옵션
- `clean_v1`, `clean_v2`, `final` 같은 버전별 Snapshot
- reviewed_json 우선, 미검수는 원본 JSON 사용
- source / split / label_source 통계 자동 생성

### 작업 통계

- 3,000건 목표 진행률
- OpenAI 고유 처리 건수
- 사람 검수 완료 / 남은 수량
- train / val / test별 검수 수
- errors 유형별 검수 완료 수
- 원본 라벨 수정률
- 오류유형별 수정률
- 클래스별 수정률
- confidence 구간별 GPT-사람 일치율
- 검수 대상 선정 이유 통계

---

## 2. 데이터 구조

권장 로컬 구조:

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

`errors`에는 다음처럼 오류유형 폴더가 추가될 수 있습니다.

```text
errors/train/artifact_fn_00/
errors/train/artifact_fp_00/
errors/train/farmland_fp_00/
```

---

## 3. 설치 / 실행

```powershell
cd "C:\Users\rlarj\Desktop\산학과제\llm-change-auto"
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app\main_app.py
```

브라우저:

```text
http://localhost:8501
```

GitHub 최신 버전을 받을 때:

```powershell
git pull
```

---

## 4. API Key

실제 API 키는 프로젝트 루트의 로컬 `.env`에만 저장합니다.

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TIMEOUT=60
```

선택적으로 비용 계산 기본 단가를 환경변수로 둘 수 있습니다.

```text
OPENAI_INPUT_PRICE_PER_1M=0
OPENAI_OUTPUT_PRICE_PER_1M=0
```

모델 가격은 변경될 수 있으므로 **현재 OpenAI 가격을 확인한 뒤 UI에서 직접 입력**하는 것을 권장합니다.

`.env`, 이미지, 실행 결과 CSV/JSON은 `.gitignore` 대상입니다.

---

## 5. 화면 사용 순서

```text
1. OpenAI 자동판정
2. 사람 검수
3. 검수 이력
4. 정제 데이터 생성
5. 작업 통계
6. LLM 결과 분석
```

### 1. OpenAI 자동판정

본작업 예시:

```text
작업 모드 : 본작업
데이터 종류 : errors
분할 : train
시작 번호 : 0
개수 : 500
선택 방식 : 순차 또는 오류유형 균형
이미 사람 검수한 항목 제외 : ON
중단된 결과 이어서 처리 : ON
기존 실패 항목 자동 재시도 : ON
항목당 최대 API 시도 : 3
프롬프트 : prompt_v4_quality.txt
```

작업 순서:

```text
dataset_index.csv 생성
→ 데이터 무결성 검사
→ OpenAI 실행 / 이어서 처리
→ 비교 실행
→ 검수 목록 생성
```

같은 Batch가 중간에 끊기면 **동일한 출력 접두어를 유지한 상태에서 다시 `OpenAI 실행 / 이어서 처리`**를 누릅니다.

새 버전은 성공한 행을 다시 호출하지 않고 미처리/실패 항목만 이어서 처리합니다.

### 2. 사람 검수

`LLM 검수 대상 CSV` 모드에서 방금 생성한 `outputs/review_lists/*_review.csv`를 불러옵니다.

본작업에서는 저장 위치를 다음으로 유지합니다.

```text
reviewed_json 폴더에 저장
```

원본 JSON 덮어쓰기는 권장하지 않습니다.

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

먼저 `Export 전 품질검사`를 실행합니다.

그다음 버전 이름을 지정합니다.

```text
clean_v1
clean_v2
final
```

Snapshot 결과 예시:

```text
outputs/clean_datasets/clean_v1/
├─ clean_dataset_manifest.csv
├─ quality_report.csv
├─ snapshot_summary.json
└─ json/
```

---

## 6. 주요 outputs

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
   ├─ clean_v1/
   ├─ clean_v2/
   └─ final/
```

본작업이 시작된 뒤의 `llm_results`, `review_lists`, `reviewed_json`, `review_events`, `review_history`는 임의 삭제하지 않는 것을 권장합니다.

---

## 7. 현재 구현 상태

- [x] 통합 Streamlit UI
- [x] OpenAI 자동판정
- [x] 실시간 진행률 / ETA / 처리속도
- [x] 매 이미지 즉시 저장
- [x] 중단 후 Resume / 성공 항목 Skip
- [x] 실패 항목 재시도 / exponential backoff
- [x] checkpoint
- [x] token 사용량 / 설정 단가 기반 비용 추적
- [x] Batch / Run 메타데이터
- [x] 균형/랜덤/순차 대상 선택
- [x] 우선순위 검수 목록
- [x] 사람 검수 필터 및 진행률
- [x] 검수 저장 이벤트 이력
- [x] reviewed_json 자동 백업
- [x] 데이터 무결성 검사
- [x] 버전별 정제 데이터 Snapshot
- [x] 3,000건 작업 진행 통계
- [x] LLM 결과 분석
- [ ] 엘컴텍 변화탐지 모델 재학습 전·후 F2 비교 화면

---

## 8. 중요 원칙

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

의 순서를 유지합니다.

또한 `LLM 결과 분석`에서 표시되는 F2는 **GPT와 현재 JSON의 비교 지표**이고, 산학과제 최종 목표 F2 0.85는 **정제 데이터로 재학습한 변화탐지 모델의 성능**입니다.
