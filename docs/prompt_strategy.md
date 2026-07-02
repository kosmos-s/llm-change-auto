# LLM 프롬프트 전략

## 목표

LLM/VLM이 두 시점 항공영상의 의미 있는 변화를 판단하고, 기존 라벨과 비교할 수 있는 JSON 결과를 생성하도록 한다.

## 단계별 프롬프트

1. `prompt_v1_basic.txt`
   - 기본 변화유무 판단
   - 빠른 샘플 테스트용

2. `prompt_v2_guideline.txt`
   - 구축 가이드라인 기준 반영
   - 라벨별 판단 기준 포함

3. `prompt_v3_json_strict.txt`
   - 반드시 JSON만 출력
   - 자동 파싱 및 CSV 저장용

## 검수 대상 선정 기준

- 기존 라벨과 LLM 결과가 다름
- confidence가 0.70 미만
- LLM이 변화 있음이라고 했지만 세부 라벨이 모두 0
- 설명에 애매함, 그림자, 밝기, 촬영각, 계절 등 불확실 키워드 포함

## 권장 실험 순서

```text
1. dataset_sample/dataset/test에서 10장 테스트
2. 프롬프트 v1 결과 확인
3. 프롬프트 v2로 기준 강화
4. 프롬프트 v3로 JSON 파싱 안정화
5. review_required 목록 생성
6. errors/test로 확장
```
