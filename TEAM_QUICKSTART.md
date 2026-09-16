# 팀원용 빠른 시작 가이드

Windows 기준입니다.

## 준비물
- Windows 10/11
- Python 3.11
- Git
- OpenAI API Key
- `dataset_sample`

## 최초 설치
```powershell
git clone https://github.com/kosmos-s/llm-change-auto.git
cd llm-change-auto
```
저장소 루트에서 `setup.bat` 실행 → 데이터 경로와 검수자 이름 입력 → 열린 `.env`에 API Key 입력 → `run.bat` 실행.

`.env` 핵심값:
```text
OPENAI_API_KEY=실제키
DATASET_ROOT=D:/.../dataset_sample
REVIEWER_NAME=검수자이름
OPENAI_TARGET_TOTAL=3000
OPENAI_COST_LIMIT_USD=5
BACKUP_KEEP_COUNT=10
```

## 본작업 시작 순서
```text
1. OpenAI 자동판정에서 dataset_index.csv 생성
2. 데이터 무결성 검사
3. 8. 본작업 관리에서 work_plan_3000.csv 생성
4. work_plan을 다시 만들지 않고 3,000건 작업 진행
```

`work_plan_3000.csv`는 아래 정확한 작업 대상을 고정합니다.
```text
errors/train 1,000
errors/val   1,000
errors/test  1,000
```
본작업 OpenAI 실행은 이 plan 안의 샘플만 사용합니다.

## 화면 순서
```text
1. OpenAI 자동판정
2. 사람 검수
3. 검수 이력
4. 정제 데이터 생성
5. 작업 통계 / 백업
6. LLM 결과 분석
7. 모델 성능 비교
8. 본작업 관리
```

### OpenAI 처리
진행률은 **성공한 고유 샘플만** 3,000건에 포함합니다. API 오류는 성공 건수에 포함하지 않으며 Retry로 0건까지 처리합니다. 배치마다 `outputs/run_manifests/`에 코드/프롬프트/인덱스/work plan 해시와 실행 설정이 기록됩니다.

### 사람 검수
사람이 3,000건 전부를 보는 것이 아니라 자동 선별 후보만 검수합니다. 원본 JSON 덮어쓰기는 사용하지 않고 `outputs/reviewed_json/`에만 저장합니다. 인공물 세부 라벨을 선택하면 상위 `Artifact`가 저장 시 자동 활성화됩니다.

보류 항목은 최종 완료가 아닙니다. `final*` Snapshot 전에 미검수/보류가 0이어야 합니다.

### 팀원이 여러 PC에서 검수할 때
각 PC의 `.env`에 서로 다른 `REVIEWER_NAME`을 설정합니다. 8번 화면에서 **내 검수 결과 ZIP 만들기**로 전달하고, 받는 PC에서 ZIP을 업로드해 미리보기 후 병합합니다. 같은 JSON이 서로 다르면 `conflict`로 표시되며 자동으로 조용히 덮어쓰지 않습니다. 병합 후 3번의 `검수 이력 갱신`을 다시 실행합니다.

### Final 조건
4번/8번 화면에서 아래가 모두 충족되어야 최종 Snapshot을 만듭니다.
```text
work_plan_3000.csv 존재
OpenAI 성공 3,000건
미해결 API 오류 0건
미검수/보류 후보 0건
품질검사 Error 0건
```

## 업데이트
```powershell
git pull
```
`requirements-lock.txt`나 설치 스크립트가 변경되면 `setup.bat`을 다시 실행해도 기존 `.env`는 유지됩니다.

## 주의
- `.env`/API Key를 GitHub에 올리지 않기
- 원본 `dataset_sample` 수정하지 않기
- 본작업 시작 후 `work_plan_3000.csv` 재생성하지 않기
- 5번 화면에서 주기적으로 ZIP 백업 생성
- GPT 결과는 최종 정답이 아니며 사람 확정 라벨이 최종본
