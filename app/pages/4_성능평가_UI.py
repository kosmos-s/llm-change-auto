"""Evaluate OpenAI labeling accuracy against the current JSON labels."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evaluate_results import evaluate_dataframe


st.title("0.85 목표 성능평가")
st.caption("현재 JSON 라벨을 정답으로 사용해 OpenAI 결과의 변화유무 정확도를 측정합니다.")

results_dir = PROJECT_ROOT / "outputs" / "llm_results"
csv_files = sorted(results_dir.glob("*.csv")) if results_dir.exists() else []

if not csv_files:
    st.info("먼저 LLM 자동화 UI에서 OpenAI 결과 CSV를 생성하세요.")
    st.stop()

selected = st.selectbox(
    "평가할 CSV",
    csv_files,
    format_func=lambda path: path.name,
)
target = st.number_input(
    "목표 정확도",
    min_value=0.0,
    max_value=1.0,
    value=0.85,
    step=0.01,
)

df = pd.read_csv(selected)
result = evaluate_dataframe(df, target=float(target))

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체", result["total_rows"])
c2.metric("정상 응답", result["valid_rows"])
c3.metric("API 오류", result["api_errors"])
c4.metric("변화유무 정확도", f"{result['change_accuracy']:.3f}")

c1, c2 = st.columns(2)
c1.metric("세부 라벨 평균 정확도", f"{result['detail_macro_accuracy']:.3f}")
c2.metric("세부 라벨 완전 일치율", f"{result['detail_exact_match']:.3f}")

if result["target_met"]:
    st.success(f"목표 달성: 변화유무 정확도 {result['change_accuracy']:.3f} ≥ {target:.2f}")
else:
    st.warning(f"목표 미달: 변화유무 정확도 {result['change_accuracy']:.3f} < {target:.2f}")

per_label = pd.DataFrame(
    [
        {"label": key, "accuracy": accuracy}
        for key, accuracy in result["per_label_accuracy"].items()
    ]
)
if not per_label.empty:
    st.markdown("### 세부 라벨별 정확도")
    st.dataframe(per_label, use_container_width=True, hide_index=True)

with st.expander("평가 CSV 미리보기", expanded=False):
    st.dataframe(df.head(100), use_container_width=True)

st.info(
    "1장 결과는 정확도 판단에 부족합니다. 10장으로 기능을 확인한 뒤, "
    "서로 겹치지 않는 최소 100장 평가셋으로 0.85 달성 여부를 판단하세요."
)
