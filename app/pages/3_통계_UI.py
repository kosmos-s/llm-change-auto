"""Statistics dashboard for LLM Change Auto."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

CSV_GROUPS = {
    "dataset_index": OUTPUTS_DIR / "dataset_index.csv",
    "llm_results": OUTPUTS_DIR / "llm_results",
    "compare_results": OUTPUTS_DIR / "compare_results",
    "review_lists": OUTPUTS_DIR / "review_lists",
}

TRUE_VALUES = {"true", "1", "yes", "y", "o"}
LABEL_KEYS = [
    "arti",
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
    "tree",
    "fore",
    "farm",
    "water",
]


st.title("검수 결과 통계")
st.caption("outputs 폴더의 CSV와 reviewed_json 저장 결과를 요약합니다.")


def list_csv_files(kind: str) -> list[Path]:
    target = CSV_GROUPS[kind]
    if target.is_file():
        return [target]
    if target.is_dir():
        return sorted(target.glob("*.csv"))
    return []


def read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.error(f"CSV를 읽을 수 없습니다: {path}\n{exc}")
        return None


def is_true_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower().isin(TRUE_VALUES)


def metric_row(metrics: list[tuple[str, Any]]) -> None:
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value)


def show_basic_metrics(df: pd.DataFrame) -> None:
    metrics: list[tuple[str, Any]] = [("전체 행", len(df)), ("컬럼 수", len(df.columns))]

    if "error" in df.columns:
        error_count = df["error"].fillna("").astype(str).str.strip().ne("").sum()
        metrics.append(("LLM 오류", int(error_count)))

    if "review_required_final" in df.columns:
        review_count = is_true_series(df["review_required_final"]).sum()
        metrics.append(("검수 필요", int(review_count)))

    if "label_mismatch" in df.columns:
        mismatch_count = is_true_series(df["label_mismatch"]).sum()
        metrics.append(("변화유무 불일치", int(mismatch_count)))

    if "detail_mismatch" in df.columns:
        detail_count = is_true_series(df["detail_mismatch"]).sum()
        metrics.append(("세부라벨 불일치", int(detail_count)))

    if "confidence" in df.columns:
        confidence = pd.to_numeric(df["confidence"], errors="coerce")
        mean_value = confidence.mean()
        metrics.append(("평균 confidence", "-" if pd.isna(mean_value) else f"{mean_value:.3f}"))

    for start in range(0, len(metrics), 4):
        metric_row(metrics[start : start + 4])


def show_group_counts(df: pd.DataFrame) -> None:
    st.markdown("### 분포")

    if "group" in df.columns and "split" in df.columns:
        st.markdown("**dataset/errors · split 개수**")
        table = df.groupby(["group", "split"], dropna=False).size().reset_index(name="count")
        st.dataframe(table, use_container_width=True, hide_index=True)

    if "source" in df.columns and "split" in df.columns:
        st.markdown("**source · split 개수**")
        table = df.groupby(["source", "split"], dropna=False).size().reset_index(name="count")
        st.dataframe(table, use_container_width=True, hide_index=True)

    if "review_reasons" in df.columns:
        st.markdown("**검수 사유별 개수**")
        reason_rows = []
        for value in df["review_reasons"].fillna("").astype(str):
            reasons = [reason.strip() for reason in value.split(",") if reason.strip()]
            for reason in reasons or ["-"]:
                reason_rows.append(reason)
        reason_df = pd.DataFrame({"review_reason": reason_rows})
        table = reason_df.groupby("review_reason").size().reset_index(name="count").sort_values("count", ascending=False)
        st.dataframe(table, use_container_width=True, hide_index=True)

    if "llm_class" in df.columns:
        st.markdown("**LLM class별 개수**")
        table = df.groupby("llm_class", dropna=False).size().reset_index(name="count").sort_values("count", ascending=False)
        st.dataframe(table, use_container_width=True, hide_index=True)


def show_label_counts(df: pd.DataFrame) -> None:
    available_original = [f"original_{key}" for key in LABEL_KEYS if f"original_{key}" in df.columns]
    available_llm = [key for key in LABEL_KEYS if key in df.columns]

    if not available_original and not available_llm:
        return

    st.markdown("### 라벨별 개수")
    rows = []
    for key in LABEL_KEYS:
        original_col = f"original_{key}"
        llm_col = key
        row = {"label": key}
        if original_col in df.columns:
            row["original"] = int(pd.to_numeric(df[original_col], errors="coerce").fillna(0).sum())
        if llm_col in df.columns:
            row["llm"] = int(pd.to_numeric(df[llm_col], errors="coerce").fillna(0).sum())
        rows.append(row)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_confidence_stats(df: pd.DataFrame) -> None:
    if "confidence" not in df.columns:
        return

    confidence = pd.to_numeric(df["confidence"], errors="coerce").dropna()
    if confidence.empty:
        return

    st.markdown("### Confidence 통계")
    desc = confidence.describe().reset_index()
    desc.columns = ["stat", "value"]
    st.dataframe(desc, use_container_width=True, hide_index=True)

    threshold = st.slider("low confidence 기준", 0.0, 1.0, 0.70, 0.05)
    low_count = int((confidence < threshold).sum())
    st.info(f"confidence < {threshold:.2f}: {low_count}개")


def show_reviewed_json_stats() -> None:
    st.markdown("## reviewed_json 저장 현황")
    reviewed_root = OUTPUTS_DIR / "reviewed_json"
    json_files = sorted(reviewed_root.rglob("*.json")) if reviewed_root.exists() else []

    metric_row([("저장된 reviewed_json", len(json_files))])

    if not json_files:
        st.info("아직 outputs/reviewed_json에 저장된 JSON이 없습니다.")
        return

    rows = []
    for path in json_files:
        try:
            rel = path.relative_to(reviewed_root)
        except ValueError:
            rel = path
        parts = rel.parts
        source = parts[0] if len(parts) >= 1 else "unknown"
        split = parts[1] if len(parts) >= 2 else "unknown"
        folder = "/".join(parts[2:-1]) if len(parts) > 3 else "."
        rows.append(
            {
                "source": source,
                "split": split,
                "folder": folder,
                "filename": path.name,
                "path": str(path),
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(df.groupby(["source", "split"], dropna=False).size().reset_index(name="count"), use_container_width=True, hide_index=True)
    with st.expander("저장 파일 목록", expanded=False):
        st.dataframe(df, use_container_width=True, hide_index=True)


def show_csv_section() -> None:
    st.markdown("## CSV 결과 통계")

    kind = st.selectbox(
        "CSV 종류",
        ["dataset_index", "llm_results", "compare_results", "review_lists"],
        format_func=lambda value: {
            "dataset_index": "dataset_index.csv",
            "llm_results": "LLM 결과 CSV",
            "compare_results": "비교 결과 CSV",
            "review_lists": "검수 대상 CSV",
        }[value],
    )

    files = list_csv_files(kind)
    if not files:
        st.info("해당 CSV 파일이 아직 없습니다.")
        return

    selected = st.selectbox("파일 선택", files, format_func=lambda path: str(path.relative_to(PROJECT_ROOT)))
    df = read_csv(selected)
    if df is None:
        return

    st.caption(str(selected))
    show_basic_metrics(df)
    show_group_counts(df)
    show_label_counts(df)
    show_confidence_stats(df)

    with st.expander("CSV 미리보기", expanded=False):
        st.dataframe(df.head(100), use_container_width=True)

    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button("현재 CSV 다운로드", csv_bytes, file_name=selected.name, mime="text/csv")


show_csv_section()
st.divider()
show_reviewed_json_stats()
