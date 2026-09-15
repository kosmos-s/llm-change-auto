"""Streamlit page for safe, versioned cleaned-dataset snapshots."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from data_quality import summarize_quality, validate_index
from export_clean_dataset import build_clean_manifest

st.title("4. 정제 데이터 생성")
st.caption("Export 전에 데이터 무결성을 검사하고 clean_v1 / clean_v2 / final 같은 버전으로 snapshot을 생성합니다.")

index_csv = Path(st.text_input("dataset_index.csv", value=str(PROJECT_ROOT / "outputs" / "dataset_index.csv")))
reviewed_root = Path(st.text_input("reviewed_json 폴더", value=str(PROJECT_ROOT / "outputs" / "reviewed_json")))
dataset_root_text = st.text_input("원본 데이터 루트(무결성 검사 보강용, 선택)", value=str(Path.home() / "Desktop" / "산학과제" / "dataset_sample"))
version = st.text_input("정제 데이터 버전", value="clean_v1").strip() or "clean_v1"
version_root = PROJECT_ROOT / "outputs" / "clean_datasets" / version
output_csv = version_root / "clean_dataset_manifest.csv"
clean_root = version_root / "json"
quality_csv = version_root / "quality_report.csv"
summary_json = version_root / "snapshot_summary.json"

copy_json = st.checkbox("선택된 JSON을 version snapshot에 실제 복사", value=True, help="이미지는 복사하지 않고 manifest가 원본 이미지 경로를 유지합니다.")
block_on_errors = st.checkbox("무결성 error가 있으면 Export 차단", value=True)

st.info("reviewed_json이 있으면 사람 확정본을 사용하고, 없으면 원본 JSON을 사용합니다. 버전별 폴더를 따로 만들어 이전 결과를 덮어쓰지 않습니다.")

quality_report: pd.DataFrame | None = None
if st.button("1) Export 전 품질검사", type="primary", use_container_width=True):
    try:
        root = Path(dataset_root_text) if dataset_root_text.strip() else None
        quality_report = validate_index(index_csv, root)
        quality_csv.parent.mkdir(parents=True, exist_ok=True)
        quality_report.to_csv(quality_csv, index=False, encoding="utf-8-sig")
        summary = summarize_quality(quality_report)
        c1, c2, c3 = st.columns(3)
        c1.metric("Error", summary["errors"])
        c2.metric("Warning", summary["warnings"])
        c3.metric("Total", summary["total"])
        if summary["errors"]:
            st.error("무결성 error가 있습니다. 원인을 확인한 뒤 Export하는 것을 권장합니다.")
        elif summary["warnings"]:
            st.warning("Error는 없지만 warning이 있습니다.")
        else:
            st.success("품질검사 통과")
        if not quality_report.empty:
            st.dataframe(quality_report.head(300), use_container_width=True)
    except Exception as exc:
        st.error(str(exc))

quality_errors = None
if quality_csv.exists():
    try:
        saved_quality = pd.read_csv(quality_csv)
        quality_errors = summarize_quality(saved_quality)["errors"]
        st.caption(f"현재 버전 저장 품질검사: error={quality_errors}, warning={summarize_quality(saved_quality)['warnings']}")
    except Exception:
        quality_errors = None

export_blocked = bool(block_on_errors and quality_errors is not None and quality_errors > 0)
if st.button("2) 버전 Snapshot 생성", type="primary", use_container_width=True, disabled=export_blocked):
    try:
        if block_on_errors and not quality_csv.exists():
            st.warning("먼저 품질검사를 실행하세요. 현재 설정은 품질검사 결과가 있어야 안전하게 Export합니다.")
            st.stop()
        with st.spinner("정제 데이터 snapshot 생성 중..."):
            result = build_clean_manifest(
                index_csv=index_csv,
                reviewed_root=reviewed_root,
                output_csv=output_csv,
                clean_root=clean_root,
                copy_selected_json=copy_json,
            )
        reviewed_count = int(result["reviewed"].sum()) if not result.empty else 0
        original_count = len(result) - reviewed_count
        snapshot = {
            "version": version,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "manifest": str(output_csv),
            "total_samples": len(result),
            "reviewed_samples": reviewed_count,
            "original_samples": original_count,
            "reviewed_ratio": reviewed_count / len(result) if len(result) else 0.0,
            "quality_errors": int(quality_errors or 0),
            "copy_selected_json": bool(copy_json),
        }
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        st.success(f"Snapshot 생성 완료: {version_root}")
        c1, c2, c3 = st.columns(3)
        c1.metric("전체 샘플", len(result))
        c2.metric("사람 검수본", reviewed_count)
        c3.metric("원본 사용", original_count)
        if not result.empty:
            st.markdown("### source / split / label_source")
            summary = result.groupby(["source", "split", "label_source"], dropna=False).size().reset_index(name="count")
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.markdown("### manifest 미리보기")
            st.dataframe(result.head(100), use_container_width=True)
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.markdown("## 생성된 Snapshot")
root = PROJECT_ROOT / "outputs" / "clean_datasets"
versions = sorted([p for p in root.iterdir() if p.is_dir()]) if root.exists() else []
if not versions:
    st.info("아직 생성된 버전 snapshot이 없습니다.")
else:
    rows = []
    for path in versions:
        summary_path = path / "snapshot_summary.json"
        if summary_path.exists():
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                data = {"version": path.name}
        else:
            data = {"version": path.name}
        rows.append(data)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
