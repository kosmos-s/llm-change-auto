# Security

## API Key

- 실제 `OPENAI_API_KEY`는 로컬 `.env`에만 저장합니다.
- `.env`는 Git에 커밋하지 않습니다.
- 팀원끼리 API Key를 메신저/문서에 평문으로 공유하지 않는 것을 권장합니다.
- 키가 GitHub에 노출되었다면 즉시 폐기하고 새 키를 발급하세요.

## Dataset

원본 항공영상과 실행 결과는 저장소에 커밋하지 않습니다. 데이터셋은 각 작업 PC/NAS에서 별도로 관리합니다.

## CI Guard

GitHub Actions는 다음을 확인합니다.

1. `scripts/check_secrets.py`로 대표적인 API Key 패턴 검사
2. 전체 unit test 실행

이 검사는 보조 안전장치이며 GitHub의 Secret Scanning 기능을 사용할 수 있는 저장소라면 함께 활성화하는 것을 권장합니다.
