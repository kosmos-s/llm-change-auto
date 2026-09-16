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
from make_quality_review_list import make_quality_review_list
from production_gate import final_gate_summary
from project_paths import dataset_root_default, ensure_output_dirs, openai_target_total
from quality_actions import build_quality_action_plan, build_split_leakage_details

OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)

st.title("4. 정제 데이터 생성")
st.caption("Export 전에 데이터 무결성, OpenAI 성공 목표, 미검수/보류 상태를 확인하고 버전 snapshot을 생성합니다.")

index_csv = Path(st.text_input("dataset_index.csv", value=str(OUTPUTS_DIR / "dataset_index.csv")))
reviewed_root = Path(st.text_input("reviewed_json 폴더", value=str(OUTPUTS_DIR / "reviewed_json")))
dataset_root_text = st.text_input("원본 데이터 루트(무결성 검사 보강용, 선택)", value=str(dataset_root_default(PROJECT_ROOT)))
version = st.text_input("정제 데이터 버전", value="clean_v1_3000").strip() or "clean_v1_3000"
version_root = OUTPUTS_DIR / "clean_datasets" / version
output_csv = version_root / "clean_dataset_manifest.csv"
clean_root = version_root / "json"
quality_csv = version_root / "quality_report.csv"
action_csv = version_root / "quality_action_plan.csv"
summary_json = version_root / "snapshot_summary.json"

copy_json = st.checkbox("선택된 JSON을 version snapshot에 실제 복사", value=True, help="이미지는 복사하지 않고 manifest가 원본 이미지 경로를 유지합니다.")
block_on_errors = st.checkbox("무결성 error가 있으면 Export 차단", value=True)
final_version = version.strip().lower() in {"final", "final_3000"} or version.strip().lower().startswith("final_")
production_gate = final_gate_summary(OUTPUTS_DIR, openai_target_total())

if final_version:
    st.info("final 버전은 무결성 Error=0, OpenAI 성공 목표 달성, API 오류=0, 미검수/보류=0을 모두 만족해야 생성됩니다.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OpenAI 성공", f"{production_gate['success_count']}/{production_gate['target_total']}")
    c2.metric("API 오류", production_gate["failed_count"])
    c3.metric("미검수/보류", production_gate["pending_review_count"])
    c4.metric("Production Gate", "READY" if production_gate["ready"] else "BLOCK")

st.info("reviewed_json이 있으면 사람 확정본을 사용하고, 없으면 원본 JSON을 사용합니다. 단 final 버전에서는 미검수 후보가 남아 있으면 Export를 막습니다.")

quality_report: pd.DataFrame | None = None
if st.button("1) Export 전 품질검사", type="primary", use_container_width=True):
    try:
        root = Path(dataset_root_text) if dataset_root_text.strip() else None
        quality_report = validate_index(index_csv, root)
        quality_csv.parent.mkdir(parents=True, exist_ok=True)
        quality_report.to_csv(quality_csv, index=False, encoding="utf-8-sig")
        action_plan = build_quality_action_plan(quality_report)
        action_plan.to_csv(action_csv, index=False, encoding="utf-8-sig")
        summary = summarize_quality(quality_report)
        c1, c2, c3 = st.columns(3)
        c1.metric("Error", summary["errors"])
        c2.metric("Warning", summary["warnings"])
        c3.metric("Total", summary["total"])
        if summary["errors"]:
            st.error("무결성 error가 있습니다. final Export 전에는 반드시 0으로 만들어야 합니다.")
        elif summary["warnings"]:
            st.warning("Error는 없지만 warning이 있습니다. 아래 조치 계획을 확인하세요.")
        else:
            st.success("품질검사 통과")
        if not quality_report.empty:
            st.markdown("### 품질 이슈")
            st.dataframe(quality_report.head(300), use_container_width=True)
            st.markdown("### 안전 조치 계획")
            st.dataframe(action_plan.head(300), use_container_width=True, hide_index=True)
            st.download_button(
                "품질 조치 계획 CSV 다운로드",
                data=action_plan.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=f"{version}_quality_action_plan.csv",
                mime="text/csv",
            )
    except Exception as exc:
        st.error(str(exc))

quality_errors = None
saved_quality: pd.DataFrame | None = None
if quality_csv.exists():
    try:
        saved_quality = pd.read_csv(quality_csv)
        saved_summary = summarize_quality(saved_quality)
        quality_errors = saved_summary["errors"]
        st.caption(f"현재 버전 저장 품질검사: error={saved_summary['errors']}, warning={saved_summary['warnings']}")
        if not saved_quality.empty and "code" in saved_quality.columns:
            st.markdown("### 이슈 유형별 개수")
            st.dataframe(saved_quality.groupby(["severity", "code"], dropna=False).size().reset_index(name="count"), use_container_width=True, hide_index=True)
    except Exception:
        quality_errors = None

if saved_quality is not None and not saved_quality.empty and "code" in saved_quality.columns:
    if (saved_quality["code"].astype(str) == "split_leakage").any() and index_csv.exists():
        try:
            index_df = pd.read_csv(index_csv)
            leakage_details = build_split_leakage_details(index_df, saved_quality)
        except Exception:
            leakage_details = pd.DataFrame()
        if not leakage_details.empty:
            st.markdown("### split leakage 실제 경로")
            st.error("같은 group 내부에서 여러 split에 존재합니다. 자동 삭제하지 말고 유지할 split을 결정해 원본 분할을 정리하세요.")
            st.dataframe(leakage_details, use_container_width=True, hide_index=True)
            st.download_button(
                "split leakage 상세 CSV 다운로드",
                data=leakage_details.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
                file_name=f"{version}_split_leakage_details.csv",
                mime="text/csv",
            )

    st.markdown("### 품질 이슈를 사람 검수로 보내기")
    code_options = sorted(saved_quality["code"].dropna().astype(str).unique().tolist())
    default_codes = [code for code in ["artifact_logic"] if code in code_options]
    selected_codes = st.multiselect("검수 목록으로 만들 품질 코드", code_options, default=default_codes)
    quality_review_path = OUTPUTS_DIR / "review_lists" / f"quality_{version}_review.csv"
    if st.button("품질 검수 목록 생성", use_container_width=True, disabled=not selected_codes):
        try:
            review_df = make_quality_review_list(index_csv, quality_csv, quality_review_path, selected_codes)
            st.success(f"품질 검수 목록 생성 완료: {len(review_df)}건 → {quality_review_path.name}")
            st.info("2. 사람 검수에서 이 CSV를 불러와 처리하세요.")
        except Exception as exc:
            st.error(str(exc))

quality_blocked = bool((block_on_errors or final_version) and quality_errors is not None and quality_errors > 0)
production_blocked = bool(final_version and not production_gate["ready"])
export_blocked = quality_blocked or production_blocked

if production_blocked:
    st.error("Final Production Gate가 BLOCK 상태입니다. 8. 본작업 관리에서 미완료 항목을 확인하세요.")

if st.button("2) 버전 Snapshot 생성", type="primary", use_container_width=True, disabled=export_blocked):
    try:
        if (block_on_errors or final_version) and not quality_csv.exists():
            st.warning("먼저 품질검사를 실행하세요.")
            st.stop()
        if final_version and not production_gate["ready"]:
            st.error("Final Production Gate 조건을 만족하지 않습니다.")
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
            "production_gate": production_gate,
            "quality_report": str(quality_csv),
            "quality_action_plan": str(action_csv),
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
            summary = result.groupby(["source", "split", "label_source"], dropna=False).size().reset_index(name="count")
            st.dataframe(summary, use_container_width=True, hide_index=True)
            st.dataframe(result.head(100), use_container_width=True)
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.markdown("## 생성된 Snapshot")
root = OUTPUTS_DIR / "clean_datasets"
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
