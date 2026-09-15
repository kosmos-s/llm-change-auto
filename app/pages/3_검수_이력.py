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
st.caption("reviewed_json의 사람 확정 라벨을 원본 라벨과 OpenAI GPT 결과에 연결합니다.")
st.info("과거 Gemini 결과는 자동 제외하고 OpenAI 결과만 사용합니다.")

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
        "OpenAI 결과 폴더",
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
        with st.spinner("원본·OpenAI·사람 검수 결과를 연결하는 중..."):
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
llm_available = (
    df["llm_change"].notna() & df["llm_change"].astype(str).str.strip().ne("")
    if "llm_change" in df.columns
    else pd.Series(False, index=df.index)
)
matched_count = int((match & llm_available).sum())
mismatch_count = int((~match & llm_available).sum())
modified_count = int(modified.sum())
unchanged_count = int((~modified).sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("검수 완료", len(df))
c2.metric("원본 라벨 수정", modified_count)
c3.metric("원본 라벨 유지", unchanged_count)
c4.metric("OpenAI 결과 연결", int(llm_available.sum()))

c1, c2, c3, c4 = st.columns(4)
c1.metric("GPT-사람 일치", matched_count)
c2.metric("GPT-사람 불일치", mismatch_count)
c3.metric("원본 수정률", f"{modified_count / len(df):.1%}" if len(df) else "0.0%")
c4.metric(
    "GPT-사람 일치율",
    f"{matched_count / int(llm_available.sum()):.1%}" if int(llm_available.sum()) else "-",
)

st.markdown("### 검수 결과 해석")
st.caption(
    "원본 라벨 수정 = 사람이 기존 JSON을 잘못되었다고 보고 실제 라벨을 변경한 건수입니다. "
    "GPT-사람 불일치 = GPT 판단과 사람의 최종 판단이 달랐던 건수이며, 이것만으로 원본 라벨 오류를 뜻하지는 않습니다."
)

summary_rows = [
    {"항목": "검수 완료", "개수": len(df)},
    {"항목": "원본 라벨 수정", "개수": modified_count},
    {"항목": "원본 라벨 유지", "개수": unchanged_count},
    {"항목": "GPT-사람 변화유무 일치", "개수": matched_count},
    {"항목": "GPT-사람 변화유무 불일치", "개수": mismatch_count},
]
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

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

if "review_status" in df.columns:
    st.markdown("### 검수 결과별 파일")
    status_filter = st.radio("표시", ["전체", "수정됨", "유지됨"], horizontal=True)
    if status_filter == "수정됨":
        view_df = df[modified].copy()
    elif status_filter == "유지됨":
        view_df = df[~modified].copy()
    else:
        view_df = df
else:
    view_df = df

st.markdown("### 검수 이력 목록")
st.dataframe(view_df, use_container_width=True, height=520)

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
    "검수 결과는 원본·OpenAI·사람 최종 라벨을 한 행에서 비교할 수 있습니다."
)
