"""Unified Streamlit entrypoint.

본작업 준비 → OpenAI 자동판정 → 사람 검수 → 검수 이력 → 정제 데이터 생성 → 작업 통계 → LLM 결과 분석 → 모델 성능 비교
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

from production_integrity import validate_plan_binding
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
index_path = OUTPUTS_DIR / "dataset_index.csv"
plan_path = OUTPUTS_DIR / "work_plan_3000.csv"
index_ready = index_path.exists()
plan_ready = plan_path.exists()
plan_binding = validate_plan_binding(index_path, plan_path) if plan_ready else {"ready": False}

st.markdown("## 실행 환경 확인")
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Python 환경", "실행됨")
c2.metric("OpenAI API Key", "확인됨" if api_ready else "설정 필요")
c3.metric("데이터 경로", "확인됨" if dataset_ready else "확인 필요")
c4.metric("dataset_index", "있음" if index_ready else "생성 필요")
c5.metric("3,000 작업계획", "고정됨" if plan_ready else "생성 필요")
c6.metric("Plan Binding", "정상" if plan_binding.get("ready") else ("BLOCK" if plan_ready else "대기"))

st.caption(f"데이터 경로: {expected_dataset}")
st.caption(f"OpenAI 본작업 목표: {openai_target_total():,}건")

if not api_ready or not dataset_ready:
    st.warning("처음 실행한 PC라면 `setup.bat`을 먼저 실행하고 `.env`의 API Key와 DATASET_ROOT를 확인하세요.")
elif not index_ready:
    st.info("먼저 1. OpenAI 자동판정에서 dataset_index.csv를 생성하세요.")
elif not plan_ready:
    st.info("dataset_index 생성 후 8. 본작업 관리에서 품질 Error=0을 확인하고 work_plan_3000.csv를 고정하세요.")
elif not plan_binding.get("ready"):
    st.error("dataset_index 또는 work plan이 고정 이후 변경된 STALE 상태입니다. 본작업 실행을 중지하고 8번에서 원인을 확인하세요.")
else:
    st.success("기본 실행 환경과 고정된 3,000건 작업계획이 정상입니다.")

with st.expander("팀원용 빠른 실행 순서", expanded=False):
    st.code(
        "git clone https://github.com/kosmos-s/llm-change-auto.git\n"
        "cd llm-change-auto\n"
        "setup.bat   # 최초 1회\n"
        "run.bat     # 이후 실행",
        language="text",
    )

st.markdown("## 본작업 실제 순서")
st.code(
    "1. OpenAI 자동판정에서 dataset_index.csv 생성\n"
    "→ 8. 본작업 관리에서 품질검사(Error 0)\n"
    "→ 8. 본작업 관리에서 work_plan_3000.csv + hash binding 고정\n"
    "→ 1. OpenAI 자동판정에서 train/val/test 각 1,000건 처리\n"
    "→ 각 배치마다 Compare + 검수 목록 생성\n"
    "→ 2. 사람 검수 → 3. 검수 이력\n"
    "→ 8. 본작업 관리에서 OpenAI/Compare/Review coverage 100% 확인\n"
    "→ 4. final_3000에서 구조 품질 + Effective JSON Error 0 확인 후 Snapshot\n"
    "→ 5~7 분석/평가",
    language="text",
)

cards = [
    ("1. OpenAI 자동판정", "dataset_index 생성과 OpenAI 판정, Compare, 검수 대상 CSV 생성을 처리합니다.", "pages/1_OpenAI_자동판정.py", "🤖"),
    ("8. 본작업 관리", "본작업 전 품질검사, 작업계획·해시 고정, Final coverage, 팀원 결과 병합을 관리합니다.", "pages/8_본작업_관리.py", "🧭"),
    ("2. 사람 검수", "검수 대상 이미지를 직접 보고 최종 라벨을 확정합니다.", "pages/2_사람_검수.py", "✅"),
    ("3. 검수 이력", "원본·GPT·사람 최종 라벨과 수정 항목을 연결합니다.", "pages/3_검수_이력.py", "📝"),
    ("4. 정제 데이터 생성", "Final Gate와 실제 선택 JSON 품질검사 통과 후 clean dataset snapshot을 만듭니다.", "pages/4_정제_데이터_생성.py", "📦"),
    ("5. 작업 통계", "3,000건 진행률, 사람 검수, 백업 현황을 확인합니다.", "pages/5_작업_통계.py", "📊"),
    ("6. LLM 결과 분석", "GPT와 기존/사람 확정 라벨 차이를 분석합니다.", "pages/6_LLM_결과_분석.py", "🔎"),
    ("7. 모델 성능 비교", "기존 모델과 정제 모델의 F2를 비교합니다.", "pages/7_모델_성능_비교.py", "📈"),
]

for start in range(0, len(cards), 3):
    columns = st.columns(3)
    for col, card in zip(columns, cards[start:start + 3]):
        title, desc, page, icon = card
        with col:
            st.subheader(title)
            st.write(desc)
            st.page_link(page, label=f"{title} 열기", icon=icon)

st.divider()
st.info("핵심: work plan 고정 후 dataset_index/work_plan을 바꾸지 말고, Final은 Compare/Review coverage와 Effective JSON 검사까지 모두 통과해야 합니다.")
