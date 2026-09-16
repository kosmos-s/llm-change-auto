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
2. 8. 본작업 관리에서 품질검사
3. Error=0 확인
4. 8. 본작업 관리에서 work_plan_3000.csv 생성
5. work plan을 다시 만들지 않고 3,000건 작업 진행
```

`work_plan_3000.csv`는 아래 정확한 작업 대상을 고정합니다.
```text
errors/train 1,000
errors/val   1,000
errors/test  1,000
```
생성 시 `work_plan_3000.meta.json`에 dataset index/work plan SHA256이 같이 저장됩니다. 이후 해당 PC에서 두 파일 중 하나라도 바뀌면 `STALE / BLOCK` 상태가 되며 본작업 실행과 Final이 차단됩니다.

### OpenAI 처리
진행률은 **성공한 고유 샘플만** 3,000건에 포함합니다. API 오류는 성공 건수에 포함하지 않으며 Retry로 0건까지 처리합니다.

배치마다 `outputs/run_manifests/`에 코드/프롬프트/index/work plan 해시와 실행 설정이 기록됩니다. Resume/Retry할 때 기존 manifest와 현재 모델, 프롬프트, source/split, start/limit, confidence 등이 다르면 실행할 수 없습니다. 설정을 바꾸고 싶으면 새 출력 접두어로 새 배치를 시작하세요.

각 split마다:
```text
OpenAI 실행 / Resume
→ 비교 실행
→ 검수 목록 생성
→ 후보만 사람 검수
→ 검수 이력 갱신
```

### 사람 검수
사람이 3,000건 전부를 보는 것이 아니라 자동 선별 후보만 검수합니다. 원본 JSON 덮어쓰기는 사용하지 않고 `outputs/reviewed_json/`에만 저장합니다. 인공물 세부 라벨을 선택하면 상위 `Artifact`가 저장 시 자동 활성화됩니다.

보류 항목은 최종 완료가 아닙니다. `final*` Snapshot 전에 미검수/보류가 0이어야 합니다.

### 팀원이 여러 PC에서 검수할 때
각 PC의 `.env`에 서로 다른 `REVIEWER_NAME`을 설정합니다. 데이터셋의 **논리적 내용과 3,000건 대상은 동일**해야 하지만 로컬 경로는 달라도 됩니다. 예를 들어 한 PC는 `C:/Users/A/...`, 다른 PC는 `D:/team/...`여도 괜찮습니다.

각 PC에서 같은 데이터셋을 스캔하고 동일한 방식으로 work plan을 고정하면, 팀원 검수 ZIP은 절대경로를 제외한 portable SHA256으로 같은 작업인지 확인합니다. 따라서 사용자명/드라이브가 달라도 병합할 수 있습니다.

8번 화면에서 **내 검수 결과 ZIP 만들기**로 전달하고, 받는 PC에서 ZIP을 업로드해 미리보기 후 병합합니다. 논리 데이터/work plan이 다르면 병합 버튼이 차단됩니다. ZIP 내부 JSON도 SHA256을 재검사합니다. 같은 JSON이 서로 다르면 `conflict`로 표시됩니다. 병합 후 3번의 `검수 이력 갱신`을 다시 실행합니다.

### Final 조건
8번에서 아래 상태를 모두 확인합니다.
```text
Index ↔ Work plan binding 정상
OpenAI 성공 3,000건
미해결 API 오류 0건
Compare coverage 3,000/3,000
Review 판정 coverage 3,000/3,000
미검수/보류 후보 0건
```

그다음 4번에서 `final_3000`을 사용해 품질검사를 실행합니다.
```text
원본 구조 품질 Error 0
Effective JSON Error 0
```
Effective JSON은 실제 Snapshot에서 선택될 `reviewed_json → original fallback` 파일입니다. Snapshot 생성 직전에도 한 번 더 검사합니다.

## 업데이트
```powershell
git pull
```
`requirements-lock.txt`나 설치 스크립트가 변경되면 `setup.bat`을 다시 실행해도 기존 `.env`는 유지됩니다.

## 주의
- `.env`/API Key를 GitHub에 올리지 않기
- 원본 `dataset_sample` 수정하지 않기
- 본작업 시작 후 `dataset_index.csv` 또는 `work_plan_3000.csv` 임의 수정/재생성하지 않기
- 본작업 결과 CSV의 출력 접두어를 바꿔가며 Resume하지 않기
- 5번 화면에서 주기적으로 ZIP 백업 생성
- GPT 결과는 최종 정답이 아니며 사람 확정 라벨이 최종본
