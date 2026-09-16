"""Analyze OpenAI labeling results against original and human-confirmed labels."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from evaluate_results import evaluate_dataframe, evaluate_history_dataframe
from project_paths import ensure_output_dirs
from results_inventory import deduplicate_result_rows

OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)

st.title("6. LLM 결과 분석")
st.caption("GPT 결과를 원본 JSON 및 사람이 확정한 라벨과 분리해서 분석합니다.")
st.info(
    "여기 표시되는 F2는 LLM 검수 보조도구의 비교 지표입니다. "
    "산학과제 최종 목표 F2-Score 0.85는 정제 데이터로 재학습한 변화탐지 모델 성능이며 7번 화면에서 별도로 비교합니다."
)


def is_openai_csv(path: Path) -> bool:
    name = path.name.lower()
    if "gemini" in name:
        return False
    try:
        sample = pd.read_csv(path, nrows=20)
    except Exception:
        return name.startswith(("openai_", "prod_openai_", "test_openai_"))

    if "llm_provider" in sample.columns:
        providers = sample["llm_provider"].fillna("").astype(str).str.strip().str.lower()
        non_empty = providers[providers != ""]
        if not non_empty.empty:
            return bool((non_empty == "openai").all())
    return name.startswith(("openai_", "prod_openai_", "test_openai_"))


def show_metrics(result: dict[str, object], title: str) -> None:
    st.markdown(f"### {title}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("대상", int(result["total_rows"]))
    c2.metric("정상 비교", int(result["valid_rows"]))
    c3.metric("API/제외", int(result["api_errors"]))
    c4.metric("변화유무 정확도", f"{float(result['change_accuracy']):.3f}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Precision", f"{float(result['precision']):.3f}")
    c2.metric("Recall", f"{float(result['recall']):.3f}")
    c3.metric("F1", f"{float(result['f1']):.3f}")
    c4.metric("GPT 비교용 F2", f"{float(result['f2']):.3f}")

    c1, c2 = st.columns(2)
    c1.metric("세부 라벨 평균 일치율", f"{float(result['detail_macro_accuracy']):.3f}")
    c2.metric("세부 라벨 완전 일치율", f"{float(result['detail_exact_match']):.3f}")

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
        [{"label": key, "accuracy": accuracy} for key, accuracy in result["per_label_accuracy"].items()]
    )
    if not per_label.empty:
        st.dataframe(per_label, use_container_width=True, hide_index=True)


results_dir = OUTPUTS_DIR / "llm_results"
csv_files = [path for path in sorted(results_dir.glob("*.csv")) if is_openai_csv(path)] if results_dir.exists() else []

if not csv_files:
    st.info("먼저 OpenAI 자동판정에서 결과 CSV를 생성하세요.")
    st.stop()

selected = st.selectbox("분석할 OpenAI CSV", csv_files, format_func=lambda path: path.name)
raw_df = pd.read_csv(selected)
df = deduplicate_result_rows(raw_df)

c1, c2, c3 = st.columns(3)
c1.metric("CSV 원본 행", len(raw_df))
c2.metric("고유 샘플", len(df))
c3.metric("중복 제거", max(len(raw_df) - len(df), 0))
if len(raw_df) != len(df):
    st.warning("Resume/재실행 등으로 중복 행이 있었으며 논리 샘플 키 기준 최신 행만 분석합니다.")

original_result = evaluate_dataframe(df)
show_metrics(original_result, "GPT ↔ 기존 JSON")
st.caption("기존 JSON 자체에 오류가 있을 수 있으므로 이 값만으로 GPT의 실제 정확도를 단정하지 않습니다.")

st.divider()
st.markdown("## 사람이 확정한 라벨 기준")
history_path = OUTPUTS_DIR / "review_history" / "review_history.csv"
if not history_path.exists():
    st.info("3. 검수 이력에서 `검수 이력 갱신`을 실행하면 GPT ↔ 사람 확정본 비교가 표시됩니다.")
else:
    history = pd.read_csv(history_path)
    if "llm_result_csv" in history.columns:
        selected_name = selected.name
        history = history[
            history["llm_result_csv"].fillna("").astype(str).map(lambda value: Path(value).name == selected_name)
        ].copy()
    if history.empty:
        st.info("이 OpenAI CSV와 연결된 사람 검수 이력이 아직 없습니다.")
    else:
        human_result = evaluate_history_dataframe(history)
        show_metrics(human_result, "GPT ↔ 사람 최종 라벨 (검수 완료 항목만)")
        st.warning(
            "이 평가는 검수 대상으로 선별된 어려운 항목만 포함하므로 전체 데이터 3,000건에 대한 무작위 정확도로 해석하면 안 됩니다. "
            "대신 사람 검수 후보에서 GPT가 최종 판단과 얼마나 일치했는지 보여줍니다."
        )

with st.expander("분석 CSV 미리보기", expanded=False):
    st.dataframe(df.head(100), use_container_width=True)
