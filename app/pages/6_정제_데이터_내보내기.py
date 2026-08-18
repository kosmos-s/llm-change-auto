"""Streamlit page for exporting a cleaned dataset manifest and JSON snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from export_clean_dataset import build_clean_manifest

st.title("정제 데이터 내보내기")
st.caption("원본 데이터 구조는 유지하고, 사람이 검수한 JSON이 있으면 그 값을 우선 사용합니다.")

index_csv = Path(st.text_input(
    "dataset_index.csv",
    value=str(PROJECT_ROOT / "outputs" / "dataset_index.csv"),
))
reviewed_root = Path(st.text_input(
    "reviewed_json 폴더",
    value=str(PROJECT_ROOT / "outputs" / "reviewed_json"),
))
output_csv = Path(st.text_input(
    "clean dataset manifest",
    value=str(PROJECT_ROOT / "outputs" / "clean_dataset" / "clean_dataset_manifest.csv"),
))
clean_root = Path(st.text_input(
    "정제 JSON 출력 폴더",
    value=str(PROJECT_ROOT / "outputs" / "clean_dataset"),
))

copy_json = st.checkbox(
    "선택된 JSON을 clean_dataset 폴더에 실제 복사",
    value=True,
    help="이미지는 복사하지 않습니다. 대용량 이미지 중복 저장을 피하고, manifest가 원본 이미지 경로를 유지합니다.",
)

st.info(
    "규칙: reviewed_json이 있으면 사람 확정본을 사용하고, 없으면 원본 JSON을 사용합니다. "
    "train/val/test와 errors 하위 폴더 구조는 그대로 유지합니다."
)

if st.button("정제 데이터 manifest 생성", type="primary", use_container_width=True):
    try:
        with st.spinner("정제 데이터 manifest 생성 중..."):
            result = build_clean_manifest(
                index_csv=index_csv,
                reviewed_root=reviewed_root,
                output_csv=output_csv,
                clean_root=clean_root,
                copy_selected_json=copy_json,
            )
        reviewed_count = int(result["reviewed"].sum()) if not result.empty else 0
        original_count = len(result) - reviewed_count
        st.success(f"생성 완료: {output_csv}")

        c1, c2, c3 = st.columns(3)
        c1.metric("전체 샘플", len(result))
        c2.metric("사람 검수본 사용", reviewed_count)
        c3.metric("원본 JSON 사용", original_count)

        if not result.empty:
            st.markdown("### source / split 현황")
            summary = (
                result.groupby(["source", "split", "label_source"], dropna=False)
                .size()
                .reset_index(name="count")
            )
            st.dataframe(summary, use_container_width=True, hide_index=True)

            st.markdown("### manifest 미리보기")
            st.dataframe(result.head(100), use_container_width=True)
    except Exception as exc:
        st.error(str(exc))

if output_csv.exists():
    try:
        current = pd.read_csv(output_csv)
        st.divider()
        st.markdown("## 현재 manifest")
        reviewed_count = int(current["reviewed"].astype(str).str.lower().isin(["true", "1"]).sum()) if "reviewed" in current.columns else 0
        c1, c2 = st.columns(2)
        c1.metric("전체", len(current))
        c2.metric("reviewed", reviewed_count)
        st.dataframe(current.head(100), use_container_width=True)
    except Exception as exc:
        st.warning(f"기존 manifest를 읽지 못했습니다: {exc}")
