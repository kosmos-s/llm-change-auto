"""Analyze OpenAI labeling results against current dataset labels."""

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


st.title("LLM 결과 분석")
st.caption("현재 JSON 라벨과 OpenAI 결과를 비교해 검수 보조도구의 특성을 확인합니다.")
st.info(
    "이 화면의 F2는 GPT 결과와 현재 JSON 라벨의 비교 지표입니다. "
    "산학과제 최종 목표인 변화탐지 모델 F2-Score 0.85와는 별도입니다."
)

results_dir = PROJECT_ROOT / "outputs" / "llm_results"
csv_files = sorted(results_dir.glob("*.csv")) if results_dir.exists() else []

if not csv_files:
    st.info("먼저 LLM 자동화 UI에서 OpenAI 결과 CSV를 생성하세요.")
    st.stop()

selected = st.selectbox(
    "분석할 CSV",
    csv_files,
    format_func=lambda path: path.name,
)

df = pd.read_csv(selected)
result = evaluate_dataframe(df)

c1, c2, c3, c4 = st.columns(4)
c1.metric("전체", result["total_rows"])
c2.metric("정상 응답", result["valid_rows"])
c3.metric("API 오류", result["api_errors"])
c4.metric("변화유무 정확도", f"{result['change_accuracy']:.3f}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Precision", f"{result['precision']:.3f}")
c2.metric("Recall", f"{result['recall']:.3f}")
c3.metric("F1", f"{result['f1']:.3f}")
c4.metric("LLM 비교용 F2", f"{result['f2']:.3f}")

c1, c2 = st.columns(2)
c1.metric("세부 라벨 평균 정확도", f"{result['detail_macro_accuracy']:.3f}")
c2.metric("세부 라벨 완전 일치율", f"{result['detail_exact_match']:.3f}")

st.markdown("### 변화유무 혼동행렬")
confusion = pd.DataFrame(
    [
        {"구분": "TP", "개수": result["tp"]},
        {"구분": "TN", "개수": result["tn"]},
        {"구분": "FP", "개수": result["fp"]},
        {"구분": "FN", "개수": result["fn"]},
    ]
)
st.dataframe(confusion, use_container_width=True, hide_index=True)

per_label = pd.DataFrame(
    [
        {"label": key, "accuracy": accuracy}
        for key, accuracy in result["per_label_accuracy"].items()
    ]
)
if not per_label.empty:
    st.markdown("### 세부 라벨별 일치율")
    st.dataframe(per_label, use_container_width=True, hide_index=True)

with st.expander("분석 CSV 미리보기", expanded=False):
    st.dataframe(df.head(100), use_container_width=True)

st.warning(
    "GPT 결과를 현재 JSON과 다르다는 이유만으로 오답으로 확정하면 안 됩니다. "
    "불일치 항목은 검수 UI에서 사람이 확인해 최종 라벨을 확정해야 합니다."
)
