# 추천 폴더 구조

```text
llm-change-auto/
├─ README.md
├─ requirements.txt
├─ .env.example
├─ .gitignore
├─ config/
│  ├─ paths.yaml
│  ├─ labels.yaml
│  └─ model_config.yaml
├─ prompts/
│  ├─ prompt_v1_basic.txt
│  ├─ prompt_v2_guideline.txt
│  └─ prompt_v3_json_strict.txt
├─ notebooks/
├─ src/
├─ data/
├─ outputs/
├─ logs/
└─ docs/
```

## 운영 원칙

- NAS 원본 데이터는 GitHub에 올리지 않는다.
- `data/`에는 원본 이미지가 아니라 경로 목록, 샘플 목록, 라벨 스키마만 둔다.
- `outputs/`에는 실행 결과 CSV/JSONL을 저장하되, 대용량 결과는 GitHub에 올리지 않는다.
- `prompts/`는 프롬프트 버전 관리를 위해 사용한다.
- `src/`는 실제 자동화 코드만 둔다.
