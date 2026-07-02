# LLM Change Auto

LLM/VLM 기반 항공영상 변경·변화탐지 학습데이터 자동 정제 도구입니다.

이 저장소는 우송대학교 산학협력 과제에서 `dataset_sample` 및 NAS 데이터의 2시점 항공영상을 대상으로 다음 작업을 수행하기 위한 코드와 문서를 관리합니다.

- 항공영상 데이터셋 폴더 스캔
- LLM/VLM 프롬프트 기반 변화유무 판단
- 기존 라벨과 LLM 결과 비교
- 육안검수 대상 자동 선정
- 결과 CSV/JSONL 저장
- 정제 결과 및 성능 분석 보고서 작성

## 중요 원칙

원본 이미지 데이터는 GitHub에 업로드하지 않습니다.

- 원본 데이터는 NAS 또는 로컬 데이터 폴더에서만 읽습니다.
- GitHub에는 코드, 프롬프트, 설정 파일, 문서, 결과 CSV 샘플만 저장합니다.
- `.env` 파일과 API Key는 절대 커밋하지 않습니다.

## 기본 작업 흐름

```text
1. dataset_sample 폴더 다운로드
2. 데이터셋 이미지 경로 목록 생성
3. 10~50개 샘플로 LLM 자동판별 테스트
4. 기존 라벨과 LLM 결과 비교
5. 불일치/저확신도 샘플을 육안검수 대상으로 저장
6. 검수 결과를 정제 데이터로 반영
7. 전체 dataset으로 확장
```

## 추천 실행 순서

```bash
pip install -r requirements.txt
python src/scan_dataset.py --root "D:/ECTNFS_WSU/2026/dataset_sample"
python src/run_llm_labeling.py --input outputs/dataset_index.csv --limit 10
python src/compare_labels.py --llm outputs/llm_results/llm_results.csv
python src/make_review_list.py --compare outputs/compare_results/compare_results.csv
```

## 폴더 구조

```text
llm-change-auto/
├─ config/
├─ prompts/
├─ notebooks/
├─ src/
├─ data/
├─ outputs/
├─ logs/
└─ docs/
```

자세한 내용은 `docs/folder_structure.md`를 참고하세요.
