"""Build and inspect latest reviewed labels plus append-only review events."""

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

st.title("3. 검수 이력")
st.caption("최신 reviewed_json 상태와 저장/보류 이벤트를 함께 확인합니다.")

index_path = Path(st.text_input("dataset_index.csv", value=str(PROJECT_ROOT / "outputs" / "dataset_index.csv")))
reviewed_root = Path(st.text_input("reviewed_json 폴더", value=str(PROJECT_ROOT / "outputs" / "reviewed_json")))
llm_results_dir = Path(st.text_input("OpenAI 결과 폴더", value=str(PROJECT_ROOT / "outputs" / "llm_results")))
output_path = Path(st.text_input("최신 검수 이력 CSV", value=str(PROJECT_ROOT / "outputs" / "review_history" / "review_history.csv")))
event_path = PROJECT_ROOT / "outputs" / "review_events" / "review_events.csv"

if st.button("검수 이력 갱신", type="primary", use_container_width=True):
    try:
        history = build_review_history(index_csv=index_path, reviewed_root=reviewed_root, llm_results_dir=llm_results_dir, output_csv=output_path)
        if history.empty:
            st.info("연결 가능한 reviewed_json이 아직 없습니다.")
        else:
            st.success(f"최신 검수 이력 갱신 완료: {len(history)}개")
    except Exception as exc:
        st.error(f"검수 이력을 만들지 못했습니다: {exc}")

st.markdown("## 최신 사람 확정 상태")
if output_path.exists():
    try:
        df = pd.read_csv(output_path)
    except Exception as exc:
        st.error(f"검수 이력 CSV를 읽지 못했습니다: {exc}")
        df = pd.DataFrame()
else:
    df = pd.DataFrame()

if df.empty:
    st.info("reviewed_json을 저장한 뒤 `검수 이력 갱신`을 누르세요.")
else:
    modified = df["labels_modified"].fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "y", "o"]) if "labels_modified" in df.columns else pd.Series(False, index=df.index)
    match = df["llm_human_change_match"].fillna("").astype(str).str.lower().isin(["true", "1", "yes", "y", "o"]) if "llm_human_change_match" in df.columns else pd.Series(False, index=df.index)
    llm_available = df["llm_change"].notna() & df["llm_change"].astype(str).str.strip().ne("") if "llm_change" in df.columns else pd.Series(False, index=df.index)
    matched_count = int((match & llm_available).sum())
    modified_count = int(modified.sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("검수 완료", len(df))
    c2.metric("원본 수정", modified_count)
    c3.metric("원본 유지", len(df) - modified_count)
    c4.metric("GPT-사람 일치율", f"{matched_count / int(llm_available.sum()):.1%}" if int(llm_available.sum()) else "-")

    status_filter = st.radio("최신 상태 표시", ["전체", "수정됨", "유지됨"], horizontal=True)
    if status_filter == "수정됨":
        view_df = df[modified].copy()
    elif status_filter == "유지됨":
        view_df = df[~modified].copy()
    else:
        view_df = df
    st.dataframe(view_df, use_container_width=True, height=430)
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("review_history.csv 다운로드", csv_bytes, file_name="review_history.csv", mime="text/csv", use_container_width=True)

st.divider()
st.markdown("## 저장 이벤트 이력")
st.caption("사람 검수에서 저장하거나 보류할 때마다 append-only로 기록됩니다. 같은 이미지를 여러 번 수정해도 이전 이벤트가 남습니다.")
if not event_path.exists():
    st.info("아직 review_events.csv가 없습니다. 새 버전의 사람 검수 화면에서 저장/보류하면 생성됩니다.")
else:
    try:
        events = pd.read_csv(event_path)
    except Exception as exc:
        st.error(f"이벤트 이력을 읽지 못했습니다: {exc}")
        events = pd.DataFrame()
    if not events.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 이벤트", len(events))
        c2.metric("저장", int((events["status"].astype(str) == "saved").sum()) if "status" in events.columns else 0)
        c3.metric("보류", int((events["status"].astype(str) == "deferred").sum()) if "status" in events.columns else 0)
        status_options = ["전체"] + sorted(events["status"].dropna().astype(str).unique().tolist()) if "status" in events.columns else ["전체"]
        event_filter = st.selectbox("이벤트 상태", status_options)
        event_view = events if event_filter == "전체" else events[events["status"].astype(str) == event_filter]
        st.dataframe(event_view.sort_values("event_at", ascending=False) if "event_at" in event_view.columns else event_view, use_container_width=True, height=430)
        event_bytes = events.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
        st.download_button("review_events.csv 다운로드", event_bytes, file_name="review_events.csv", mime="text/csv", use_container_width=True)

st.info("reviewed_json을 다시 저장할 때 기존 파일은 outputs/backups/reviewed_json 아래에 자동 백업됩니다.")
