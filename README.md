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

## 본작업 실제 순서
```text
1. OpenAI 자동판정에서 dataset_index.csv 생성
→ 8. 본작업 관리에서 품질검사(Error 0)
→ 8. 본작업 관리에서 work_plan_3000.csv 고정
→ 1. OpenAI 자동판정에서 errors/train·val·test 각 1,000건 처리
→ 각 배치마다 Compare + 검수 목록 생성
→ 2. 사람 검수 → 3. 검수 이력
→ 8. 본작업 관리에서 Final Gate 확인
→ 4. final_3000 품질검사 및 Snapshot 생성
→ 5~7 통계·LLM 분석·모델 성능 비교
```

## 3,000건 본작업
```text
errors/train  1,000
errors/val    1,000
errors/test   1,000
--------------------
OpenAI 성공 목표 3,000
```

`work_plan_3000.csv`는 정확한 작업 대상을 고정합니다. 생성 시 `work_plan_3000.meta.json`에 `dataset_index.csv`와 work plan의 SHA256도 함께 기록합니다. 이후 index 또는 plan이 변경되면 **STALE / BLOCK**으로 처리하고 본작업 실행과 Final Gate를 막습니다.

진행률은 결과 행 수가 아니라 **API 오류가 없는 성공 고유 샘플 수**로 계산합니다. 실패 샘플은 3,000건에 포함하지 않습니다.

배치 실행 시 `outputs/run_manifests/<batch>.json`에 Git commit, 프롬프트 SHA256, dataset_index SHA256, work-plan SHA256, 모델과 실행 설정을 기록합니다. 기존 CSV를 Resume/Retry할 때 모델·프롬프트·work plan·index·source·split·start·limit·selection mode·confidence가 기존 manifest와 다르면 실행을 차단합니다. 따라서 하나의 결과 CSV에 서로 다른 실행 조건이 섞이지 않습니다.

## 사람 검수 안전장치
- 원본 JSON 직접 덮어쓰기를 UI에서 제거하고 `outputs/reviewed_json/`만 사용
- 세부 인공물 라벨이 하나라도 켜지면 저장 시 `Artifact`도 자동 활성화
- `REVIEWER_NAME`을 review event에 기록
- 가장 최근 review-list CSV를 기본으로 자동 선택
- `DATASET_ROOT`를 주요 화면의 기본 경로로 사용
- 보류는 완료가 아니며 Final Gate에서 미해결로 계산

## 팀원 여러 PC 검수
8번 **본작업 관리**에서 검수 결과 ZIP을 생성/가져오기 할 수 있습니다. 패키지에는 reviewed JSON 해시뿐 아니라 **dataset_index SHA256 + work-plan SHA256**도 기록합니다. 현재 PC와 다른 본작업 패키지는 병합 자체가 차단됩니다. ZIP 내부 JSON도 manifest SHA256과 다시 대조한 뒤에만 병합합니다.

팀원 PC도 같은 본작업을 사용하려면 `dataset_index.csv`, `work_plan_3000.csv`, `work_plan_3000.meta.json`이 동일해야 합니다. 가장 안전한 방법은 한 PC에서 계획을 고정한 뒤 5번 백업 또는 별도 안전한 전달 방식으로 이 세 파일을 팀원에게 동일하게 배포하는 것입니다.

같은 샘플의 JSON이 서로 다르면 conflict로 표시하며 사용자가 `내 PC 결과 유지` 또는 `들어온 결과 사용`을 선택합니다. 병합 후 3번 화면에서 `검수 이력 갱신`을 다시 실행합니다.

## Final Gate
`final*` Snapshot은 다음을 모두 만족해야 합니다.
```text
work_plan_3000.csv 존재
Index ↔ Work plan hash binding 정상
OpenAI 성공 = plan 전체 완료
미해결 API 오류 = 0
Compare coverage = 100%
Review 판정 coverage = 100%
미검수/보류 후보 = 0
원본 구조 품질 Error = 0
Effective JSON Error = 0
```

Compare/Review coverage는 **production 결과만 인정**하므로 과거 test/pilot Compare CSV가 Final 진행률을 채울 수 없습니다.

4번 화면의 Final 품질검사는 원본 JSON만 보는 것이 아니라, 실제 Snapshot에서 선택될 `reviewed_json → original fallback` 결과를 다시 읽어 검사합니다. Snapshot 버튼을 누르는 순간에도 Effective JSON을 재검사하므로 품질검사 후 reviewed JSON이 변경된 경우를 다시 잡습니다.

## 주요 outputs
```text
outputs/
├─ dataset_index.csv
├─ work_plan_3000.csv
├─ work_plan_3000.meta.json
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

## 분석과 최종 모델
6번은 GPT↔기존 JSON 및 GPT↔사람 확정 라벨 비교용입니다. 여기의 F2는 GPT 분석 지표입니다. 7번은 재학습한 변화탐지 모델의 Precision / Recall / F1 / F2를 기존 모델과 비교하며, 산학과제 목표 F2는 이 화면에서 확인합니다.

## 팀원 가이드 / 보안
- 자세한 설치·본작업 절차: [`TEAM_QUICKSTART.md`](TEAM_QUICKSTART.md)
- 보안 원칙: [`SECURITY.md`](SECURITY.md)
- CI: secret scan → compile → unit tests
