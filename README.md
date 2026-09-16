# LLM Change Auto

우송대학교 산학협력 과제용 **항공영상 변화탐지 학습데이터 검수 + OpenAI GPT 자동화 통합 도구**입니다.

```text
OpenAI GPT 자동판정
→ 기존 JSON 비교
→ 검수 후보 추출
→ 사람 최종 검수
→ 데이터 품질검사
→ 정제 Snapshot
→ 변화탐지 모델 재학습
→ Before / After F2 비교
```

GPT는 최종 정답이 아니라 사람 검수를 줄이기 위한 보조도구입니다.

## 빠른 시작 (Windows)
```powershell
git clone https://github.com/kosmos-s/llm-change-auto.git
cd llm-change-auto
```
최초 1회 `setup.bat`, 이후 `run.bat`을 실행합니다. Python 3.11과 `requirements-lock.txt`를 기준으로 설치합니다.

`.env`:
```text
OPENAI_API_KEY=your_real_api_key
DATASET_ROOT=D:/.../dataset_sample
REVIEWER_NAME=김건보
OPENAI_TARGET_TOTAL=3000
OPENAI_COST_LIMIT_USD=5
BACKUP_KEEP_COUNT=10
```
실제 API Key와 데이터/실행결과는 GitHub에 올리지 않습니다.

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

## 3,000건 본작업
본작업 시작 전에 1번에서 `dataset_index.csv`를 생성한 뒤 **8번 화면에서 `work_plan_3000.csv`를 한 번 생성**합니다.

```text
errors/train  1,000
errors/val    1,000
errors/test   1,000
--------------------
OpenAI 성공 목표 3,000
```

`work_plan_3000.csv`는 정확히 어떤 샘플을 처리할지 고정합니다. 본작업이 끝날 때까지 다시 만들지 않는 것을 권장합니다. 본작업 OpenAI 실행은 이 plan을 입력으로 사용하므로 dataset index가 이후 바뀌더라도 대상 3,000건은 유지됩니다.

진행률은 결과 행 수가 아니라 **API 오류가 없는 성공 고유 샘플 수**로 계산합니다. 실패 샘플은 3,000건에 포함하지 않습니다.

각 split:
```text
OpenAI 실행 / Resume
→ 비교 실행
→ 검수 목록 생성
→ 후보만 사람 검수
→ 검수 이력 갱신
→ 작업 통계 / 백업
```

배치 실행 시 `outputs/run_manifests/<batch>.json`에 Git commit, 프롬프트 SHA256, dataset_index SHA256, work-plan SHA256, 모델과 실행 설정을 기록합니다.

## 사람 검수 안전장치
- 원본 JSON 직접 덮어쓰기를 UI에서 제거하고 `outputs/reviewed_json/`만 사용
- 세부 인공물 라벨이 하나라도 켜지면 저장 시 `Artifact`도 자동 활성화
- `REVIEWER_NAME`을 review event에 기록
- 가장 최근 review-list CSV를 기본으로 자동 선택
- `DATASET_ROOT`를 모든 주요 화면의 기본 경로로 사용
- 보류는 완료가 아니며 Final Gate에서 미해결로 계산

## 팀원 여러 PC 검수
8번 **본작업 관리**에서 검수 결과 ZIP을 생성/가져오기 할 수 있습니다. reviewed JSON은 해시로 비교하며 같은 샘플의 내용이 다르면 conflict로 표시합니다. 사용자가 `내 PC 결과 유지` 또는 `들어온 결과 사용`을 선택합니다. 들어온 review event도 병합합니다.

병합 후 3번 화면에서 `검수 이력 갱신`을 다시 실행합니다.

## Final Gate
`final*` Snapshot은 다음을 모두 만족해야 합니다.
```text
work_plan_3000.csv 존재
OpenAI 성공 = plan 전체 완료
미해결 API 오류 = 0
미검수/보류 후보 = 0
데이터 품질 Error = 0
```
품질검사는 split leakage, 파일 누락, invalid JSON, Artifact 논리, orphan 등을 검사합니다. 원본을 자동 삭제하지 않습니다.

## 주요 outputs
```text
outputs/
├─ dataset_index.csv
├─ work_plan_3000.csv
├─ llm_results/
├─ run_manifests/
├─ compare_results/
├─ review_lists/
├─ reviewed_json/
├─ review_events/
├─ review_history/
├─ review_packages/
├─ quality/
├─ clean_datasets/
├─ model_eval/
└─ backups/
```
5번 화면의 ZIP 백업에는 `work_plan_3000.csv`와 run manifests도 포함됩니다.

## 분석과 최종 모델
6번은 GPT↔기존 JSON 및 GPT↔사람 확정 라벨 비교용입니다. 여기의 F2는 GPT 분석 지표입니다. 7번은 재학습한 변화탐지 모델의 Precision / Recall / F1 / F2를 기존 모델과 비교하며, 산학과제 목표 F2는 이 화면에서 확인합니다.

## 팀원 가이드 / 보안
- 자세한 설치·본작업 절차: [`TEAM_QUICKSTART.md`](TEAM_QUICKSTART.md)
- 보안 원칙: [`SECURITY.md`](SECURITY.md)
- CI: secret scan → compile → unit tests
