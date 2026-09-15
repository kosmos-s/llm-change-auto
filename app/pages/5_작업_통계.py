"""Project progress and OpenAI/review statistics dashboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TRUE_VALUES = {"true", "1", "yes", "y", "o"}
LABEL_KEYS = ["arti", "arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other", "tree", "fore", "farm", "water"]

st.title("5. 작업 통계")
st.caption("3,000건 목표 진행률, OpenAI 처리, 사람 검수, 수정률과 confidence 특성을 한 화면에서 확인합니다.")


def read_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def is_true(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.lower().isin(TRUE_VALUES)


def reviewed_inventory() -> pd.DataFrame:
    root = OUTPUTS_DIR / "reviewed_json"
    rows = []
    if not root.exists():
        return pd.DataFrame()
    for path in root.rglob("*.json"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        parts = rel.parts
        source = parts[0] if len(parts) >= 1 else "unknown"
        split = parts[1] if len(parts) >= 2 else "unknown"
        folder = "/".join(parts[2:-1]) if len(parts) > 3 else "."
        rows.append({"source": source, "split": split, "relative_folder": folder, "error_type": folder.split("/")[0] if source == "errors" and folder != "." else "", "filename": path.name})
    return pd.DataFrame(rows)


def unique_openai_results() -> pd.DataFrame:
    root = OUTPUTS_DIR / "llm_results"
    frames = []
    if not root.exists():
        return pd.DataFrame()
    for path in sorted(root.glob("*.csv")):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if df.empty or "image_id" not in df.columns:
            continue
        if "llm_provider" in df.columns:
            provider = df["llm_provider"].fillna("").astype(str).str.lower()
            df = df[(provider == "openai") | (provider == "")]
        if df.empty:
            continue
        df = df.copy()
        df["_file"] = str(path)
        df["_mtime"] = path.stat().st_mtime
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    merged = pd.concat(frames, ignore_index=True, sort=False)
    for col in ["group", "split", "relative_folder", "image_id"]:
        if col not in merged.columns:
            merged[col] = ""
    return merged.sort_values("_mtime").drop_duplicates(["group", "split", "relative_folder", "image_id"], keep="last")


def show_project_progress() -> None:
    goal = int(st.number_input("프로젝트 사람 검수 목표", min_value=1, value=3000, step=100))
    reviewed = reviewed_inventory()
    llm = unique_openai_results()
    reviewed_count = len(reviewed)
    llm_count = len(llm)
    errors = 0
    if not llm.empty and "error" in llm.columns:
        errors = int(llm["error"].fillna("").astype(str).str.strip().ne("").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OpenAI 판정 완료(고유)", llm_count)
    c2.metric("사람 검수 완료", reviewed_count)
    c3.metric("목표까지 남음", max(goal - reviewed_count, 0))
    c4.metric("현재 OpenAI 오류", errors)
    ratio = min(reviewed_count / goal, 1.0)
    st.progress(ratio, text=f"사람 검수 목표 진행률 {reviewed_count:,}/{goal:,} ({ratio:.1%})")

    if not reviewed.empty:
        st.markdown("### split별 사람 검수 진행")
        split_goal = max(goal // 3, 1)
        rows = []
        for split in ["train", "val", "test"]:
            count = int((reviewed["split"].astype(str) == split).sum())
            rows.append({"split": split, "reviewed": count, "권장목표": split_goal, "진행률": min(count / split_goal, 1.0)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        errors_reviewed = reviewed[reviewed["source"].astype(str) == "errors"]
        if not errors_reviewed.empty:
            st.markdown("### errors 유형별 검수 완료")
            table = errors_reviewed.groupby("error_type", dropna=False).size().reset_index(name="reviewed").sort_values("reviewed", ascending=False)
            st.dataframe(table, use_container_width=True, hide_index=True)


def show_review_quality() -> None:
    history_path = OUTPUTS_DIR / "review_history" / "review_history.csv"
    history = read_csv(history_path)
    st.markdown("## 사람 검수 품질 통계")
    if history is None or history.empty:
        st.info("3. 검수 이력에서 `검수 이력 갱신`을 먼저 실행하세요.")
        return

    modified = is_true(history["labels_modified"]) if "labels_modified" in history.columns else pd.Series(False, index=history.index)
    llm_available = history["llm_change"].notna() & history["llm_change"].astype(str).str.strip().ne("") if "llm_change" in history.columns else pd.Series(False, index=history.index)
    match = is_true(history["llm_human_change_match"]) if "llm_human_change_match" in history.columns else pd.Series(False, index=history.index)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("검수 이력", len(history))
    c2.metric("원본 수정", int(modified.sum()))
    c3.metric("원본 수정률", f"{modified.mean():.1%}" if len(history) else "-")
    c4.metric("GPT-사람 일치율", f"{(match & llm_available).sum()/llm_available.sum():.1%}" if llm_available.sum() else "-")

    if "error_type" in history.columns:
        tmp = history.copy()
        tmp["modified"] = modified.astype(int)
        grouped = tmp.groupby("error_type", dropna=False).agg(reviewed=("image_id", "count"), modified=("modified", "sum")).reset_index()
        grouped["수정률"] = grouped["modified"] / grouped["reviewed"].clip(lower=1)
        st.markdown("### 오류유형별 원본 수정률")
        st.dataframe(grouped.sort_values("수정률", ascending=False), use_container_width=True, hide_index=True)

    label_rows = []
    for label in LABEL_KEYS:
        col = f"human_{label}"
        original_col = f"original_{label}"
        if col in history.columns and original_col in history.columns:
            h = pd.to_numeric(history[col], errors="coerce").fillna(0).astype(int)
            o = pd.to_numeric(history[original_col], errors="coerce").fillna(0).astype(int)
            label_rows.append({"label": label, "검수건수": len(history), "수정건수": int((h != o).sum()), "수정률": float((h != o).mean())})
    if label_rows:
        st.markdown("### 클래스별 수정률")
        st.dataframe(pd.DataFrame(label_rows).sort_values("수정률", ascending=False), use_container_width=True, hide_index=True)

    if "llm_confidence" in history.columns and "llm_human_change_match" in history.columns:
        conf = pd.to_numeric(history["llm_confidence"], errors="coerce")
        tmp = history[llm_available].copy()
        tmp["confidence_num"] = pd.to_numeric(tmp["llm_confidence"], errors="coerce")
        tmp["match_num"] = is_true(tmp["llm_human_change_match"]).astype(int)
        tmp["confidence_bin"] = pd.cut(tmp["confidence_num"], bins=[0, .5, .7, .85, 1.000001], include_lowest=True)
        conf_table = tmp.groupby("confidence_bin", observed=False).agg(count=("image_id", "count"), gpt_human_match=("match_num", "mean")).reset_index()
        st.markdown("### Confidence 구간별 GPT-사람 일치율")
        st.dataframe(conf_table, use_container_width=True, hide_index=True)


def show_review_reason_stats() -> None:
    st.markdown("## 검수 대상 선정 이유")
    root = OUTPUTS_DIR / "review_lists"
    frames = []
    if root.exists():
        for path in root.glob("*.csv"):
            try:
                df = pd.read_csv(path)
            except Exception:
                continue
            if not df.empty:
                frames.append(df)
    if not frames:
        st.info("검수 목록 CSV가 아직 없습니다.")
        return
    df = pd.concat(frames, ignore_index=True, sort=False)
    if "review_reasons" in df.columns:
        reasons = []
        for value in df["review_reasons"].fillna("").astype(str):
            for reason in [r.strip() for r in value.split(",") if r.strip()] or ["-"]:
                reasons.append(reason)
        table = pd.Series(reasons).value_counts().rename_axis("reason").reset_index(name="count")
        st.dataframe(table, use_container_width=True, hide_index=True)
    if "priority_score" in df.columns:
        st.caption("priority_score가 높은 항목부터 사람 검수하도록 정렬됩니다.")
        st.dataframe(df.sort_values("priority_score", ascending=False).head(30), use_container_width=True)


def show_csv_browser() -> None:
    st.markdown("## 개별 결과 CSV 보기")
    kinds = {
        "dataset_index": OUTPUTS_DIR / "dataset_index.csv",
        "llm_results": OUTPUTS_DIR / "llm_results",
        "compare_results": OUTPUTS_DIR / "compare_results",
        "review_lists": OUTPUTS_DIR / "review_lists",
    }
    kind = st.selectbox("종류", list(kinds), format_func=lambda v: {"dataset_index": "dataset_index", "llm_results": "OpenAI 결과", "compare_results": "비교 결과", "review_lists": "검수 목록"}[v])
    target = kinds[kind]
    if target.is_file():
        files = [target]
    elif target.exists():
        files = sorted(target.glob("*.csv"))
    else:
        files = []
    if not files:
        st.info("파일이 없습니다.")
        return
    selected = st.selectbox("파일", files, format_func=lambda p: p.name)
    df = read_csv(selected)
    if df is None:
        return
    c1, c2 = st.columns(2)
    c1.metric("Rows", len(df))
    if "error" in df.columns:
        c2.metric("오류", int(df["error"].fillna("").astype(str).str.strip().ne("").sum()))
    else:
        c2.metric("Columns", len(df.columns))
    st.dataframe(df.head(200), use_container_width=True)


show_project_progress()
st.divider()
show_review_quality()
st.divider()
show_review_reason_stats()
st.divider()
show_csv_browser()
