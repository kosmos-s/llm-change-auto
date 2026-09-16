"""Unified Streamlit entrypoint.

OpenAI 자동판정 → 사람 검수 → 검수 이력 → 정제 데이터 생성 → 작업 통계 → LLM 결과 분석 → 모델 성능 비교
순서로 전체 작업 흐름을 안내한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from project_paths import dataset_root_default, ensure_output_dirs, openai_target_total

load_dotenv(PROJECT_ROOT / ".env")
OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)

st.set_page_config(page_title="LLM Change Auto", layout="wide", initial_sidebar_state="expanded")

st.title("LLM Change Auto")
st.caption("항공영상 학습데이터 검수 + OpenAI GPT 자동화 통합 UI")

expected_dataset = dataset_root_default(PROJECT_ROOT)
api_key = str(os.getenv("OPENAI_API_KEY", "")).strip()
api_ready = bool(api_key and api_key != "your_openai_api_key_here")
dataset_ready = expected_dataset.exists()
index_ready = (OUTPUTS_DIR / "dataset_index.csv").exists()

st.markdown("## 실행 환경 확인")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Python 환경", "실행됨")
c2.metric("OpenAI API Key", "확인됨" if api_ready else "설정 필요")
c3.metric("데이터 경로", "확인됨" if dataset_ready else "확인 필요")
c4.metric("dataset_index", "있음" if index_ready else "생성 필요")

st.caption(f"데이터 경로: {expected_dataset}")
st.caption(f"OpenAI 본작업 목표: {openai_target_total():,}건")

if not api_ready or not dataset_ready:
    st.warning(
        "처음 실행한 PC라면 저장소 루트의 `setup.bat`을 먼저 실행하세요. "
        "`.env`에 API Key를 넣고, dataset_sample이 다른 위치에 있으면 `.env`의 DATASET_ROOT 또는 1번 화면에서 실제 경로를 지정하세요."
    )
else:
    st.success("기본 실행 환경이 준비되어 있습니다. 왼쪽 메뉴에서 1번부터 진행하세요.")

with st.expander("팀원용 빠른 실행 순서", expanded=False):
    st.code(
        "git clone https://github.com/kosmos-s/llm-change-auto.git\n"
        "cd llm-change-auto\n"
        "setup.bat   # 최초 1회\n"
        "run.bat     # 이후 실행",
        language="text",
    )
    st.caption("자세한 내용은 저장소 루트의 TEAM_QUICKSTART.md를 참고하세요.")

st.markdown(
    """
## 사용 순서

왼쪽 사이드바의 페이지를 **1 → 7 순서로** 따라가면 됩니다.

1. **OpenAI 자동판정**: 데이터 인덱스 생성, GPT 자동판별, 기존 라벨 비교, 검수 대상 CSV 생성
2. **사람 검수**: 검수 대상 이미지를 확인하고 최종 라벨을 `reviewed_json`으로 저장
3. **검수 이력**: 원본 라벨, OpenAI GPT 결과, 사람 확정 라벨을 연결
4. **정제 데이터 생성**: 품질검사 후 사람이 검수한 JSON을 우선 적용한 Snapshot 생성
5. **작업 통계**: OpenAI 3,000건 진행률, 사람 검수, 수정률, 백업 상태 확인
6. **LLM 결과 분석**: 중복 제거 후 GPT↔원본 / GPT↔사람 확정본을 구분해 분석
7. **모델 성능 비교**: 기존 모델과 정제 데이터 재학습 모델의 Precision / Recall / F1 / F2 비교

모든 화면은 하나의 Streamlit 앱에서 동작합니다.
"""
)

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("1. OpenAI 자동판정")
    st.write("데이터 인덱스 생성부터 검수 대상 CSV 생성까지 처리합니다.")
    st.page_link("pages/1_OpenAI_자동판정.py", label="OpenAI 자동판정 열기", icon="🤖")
with col2:
    st.subheader("2. 사람 검수")
    st.write("검수 대상 이미지를 직접 보고 최종 라벨을 확정합니다.")
    st.page_link("pages/2_사람_검수.py", label="사람 검수 열기", icon="✅")
with col3:
    st.subheader("3. 검수 이력")
    st.write("원본·OpenAI GPT·사람 최종 라벨과 수정 항목을 연결합니다.")
    st.page_link("pages/3_검수_이력.py", label="검수 이력 열기", icon="📝")

col4, col5, col6 = st.columns(3)
with col4:
    st.subheader("4. 정제 데이터 생성")
    st.write("품질검사 후 clean dataset manifest와 JSON snapshot을 만듭니다.")
    st.page_link("pages/4_정제_데이터_생성.py", label="정제 데이터 생성", icon="📦")
with col5:
    st.subheader("5. 작업 통계")
    st.write("3,000건 본작업 진행률과 사람 검수 및 백업 현황을 확인합니다.")
    st.page_link("pages/5_작업_통계.py", label="작업 통계 열기", icon="📊")
with col6:
    st.subheader("6. LLM 결과 분석")
    st.write("GPT와 기존/사람 확정 라벨의 차이를 분석합니다.")
    st.page_link("pages/6_LLM_결과_분석.py", label="LLM 결과 분석 열기", icon="🔎")

st.subheader("7. 모델 성능 비교")
st.write("최종 재학습 후 기존 모델과 정제 모델의 F2를 비교합니다.")
st.page_link("pages/7_모델_성능_비교.py", label="모델 성능 비교 열기", icon="📈")

st.divider()
st.info("Windows 팀원은 최초 1회 `setup.bat`, 이후에는 `run.bat`만 실행하면 됩니다. 본작업 중에는 5번 화면의 ZIP 백업도 주기적으로 생성하세요.")
