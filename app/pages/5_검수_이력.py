"""Build and inspect reviewed-label history."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_review_history import build_review_history


st.title("검수 이력")
st.caption("reviewed_json에 저장된 사람 확정 라벨을 원본 라벨 및 최근 GPT 결과와 비교합니다.")

index_path = Path(
    st.text_input(
        "dataset_index.csv",
        value=str(PROJECT_ROOT / "outputs" / "dataset_index.csv"),
    )
)
reviewed_root = Path(
    st.text_input(
        "reviewed_json 폴더",
        value=str(PROJECT_ROOT / "outputs" / "reviewed_json"),
    )
)
llm_results_dir = Path(
    st.text_input(
        "LLM 결과 폴더",
        value=str(PROJECT_ROOT / "outputs" / "llm_results"),
    )
)
output_path = Path(
    st.text_input(
        "검수 이력 CSV 저장 경로",
        value=str(PROJECT_ROOT / "outputs" / "review_history" / "review_history.csv"),
    )
)

if st.button("검수 이력 갱신", type="primary", use_container_width=True):
    try:
        with st.spinner("원본·GPT·사람 검수 결과를 연결하는 중..."):
            history = build_review_history(
                index_csv=index_path,
                reviewed_root=reviewed_root,
                llm_results_dir=llm_results_dir,
                output_csv=output_path,
            )
        if history.empty:
            st.info("연결 가능한 reviewed_json이 아직 없습니다.")
        else:
            st.success(f"검수 이력 생성 완료: {output_path} / {len(history)}개")
    except Exception as exc:
        st.error(f"검수 이력을 만들지 못했습니다: {exc}")

if not output_path.exists():
    st.info("검수 UI에서 reviewed_json으로 저장한 뒤 `검수 이력 갱신`을 누르세요.")
    st.stop()

try:
    df = pd.read_csv(output_path)
except pd.errors.EmptyDataError:
    st.info("저장된 reviewed_json이 없거나 dataset_index.csv와 연결되지 않았습니다.")
    st.stop()
except Exception as exc:
    st.error(f"검수 이력 CSV를 읽을 수 없습니다: {exc}")
    st.stop()

if df.empty:
    st.info("저장된 reviewed_json이 없거나 dataset_index.csv와 연결되지 않았습니다.")
    st.stop()

modified = (
    df["labels_modified"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y", "o"])
    if "labels_modified" in df.columns
    else pd.Series(False, index=df.index)
)
match = (
    df["llm_human_change_match"].fillna("").astype(str).str.lower().isin(["true", "1", "yes", "y", "o"])
    if "llm_human_change_match" in df.columns
    else pd.Series(False, index=df.index)
)
llm_available = df["llm_change"].notna() if "llm_change" in df.columns else pd.Series(False, index=df.index)

c1, c2, c3, c4 = st.columns(4)
c1.metric("검수 완료 파일", len(df))
c2.metric("라벨 수정", int(modified.sum()))
c3.metric("라벨 유지", int((~modified).sum()))
c4.metric("GPT-사람 변화유무 일치", int((match & llm_available).sum()))

if "modified_keys" in df.columns:
    changed_labels: list[str] = []
    for value in df["modified_keys"].fillna("").astype(str):
        changed_labels.extend(key.strip() for key in value.split(",") if key.strip())
    if changed_labels:
        st.markdown("### 많이 수정된 라벨")
        changed_df = (
            pd.Series(changed_labels, name="label")
            .value_counts()
            .rename_axis("label")
            .reset_index(name="count")
        )
        st.dataframe(changed_df, use_container_width=True, hide_index=True)

if "source" in df.columns and "split" in df.columns:
    st.markdown("### 데이터 구분별 검수 수")
    group_df = df.groupby(["source", "split"], dropna=False).size().reset_index(name="count")
    st.dataframe(group_df, use_container_width=True, hide_index=True)

st.markdown("### 검수 이력 목록")
st.dataframe(df, use_container_width=True, height=520)

csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    "review_history.csv 다운로드",
    data=csv_bytes,
    file_name=output_path.name,
    mime="text/csv",
    use_container_width=True,
)

st.info(
    "현재 버전은 reviewed_json의 최신 저장 상태를 기준으로 이력을 만듭니다. "
    "같은 파일의 매 저장 시점별 이벤트 기록은 다음 단계에서 추가합니다."
)
