"""Project progress and OpenAI/review statistics dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backup_outputs import create_outputs_backup
from production_gate import successful_openai_results
from project_paths import backup_keep_count, ensure_output_dirs, openai_target_total

OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)
TRUE_VALUES = {"true", "1", "yes", "y", "o"}
LABEL_KEYS = ["arti", "arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other", "tree", "fore", "farm", "water"]

st.title("5. 작업 통계")
st.caption("3,000건 OpenAI 성공 본작업 진행률, API 실패, 사람 검수와 수정률을 확인합니다.")


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
        rows.append({
            "source": source,
            "split": split,
            "relative_folder": folder,
            "error_type": folder.split("/")[0] if source == "errors" and folder != "." else "",
            "filename": path.name,
        })
    return pd.DataFrame(rows)


def show_project_progress() -> None:
    goal = int(st.number_input("OpenAI 본작업 성공 목표", min_value=1, value=openai_target_total(), step=100))
    reviewed = reviewed_inventory()
    success, failed = successful_openai_results(OUTPUTS_DIR / "llm_results")
    success_count = len(success)
    failed_count = len(failed)
    reviewed_count = len(reviewed)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OpenAI 성공(고유)", success_count)
    c2.metric("사람 검수 완료", reviewed_count)
    c3.metric("성공 목표까지 남음", max(goal - success_count, 0))
    c4.metric("미해결 API 오류", failed_count)
    ratio = min(success_count / goal, 1.0)
    st.progress(ratio, text=f"OpenAI 성공 진행률 {success_count:,}/{goal:,} ({ratio:.1%})")
    st.caption("API 오류 행은 3,000건 성공 목표에 포함하지 않습니다. 실패 항목은 Retry로 0건까지 줄이세요.")

    st.markdown("### split별 본작업 현황")
    rows = []
    for split in ["train", "val", "test"]:
        ok = int((success["split"].astype(str) == split).sum()) if not success.empty and "split" in success.columns else 0
        fail = int((failed["split"].astype(str) == split).sum()) if not failed.empty and "split" in failed.columns else 0
        human = int((reviewed["split"].astype(str) == split).sum()) if not reviewed.empty else 0
        rows.append({"split": split, "OpenAI 성공": ok, "API 실패": fail, "사람 검수 완료": human})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    plan = OUTPUTS_DIR / "work_plan_3000.csv"
    st.caption(f"고정 작업계획: {'있음' if plan.exists() else '없음'} · 본작업 시작 전 8번 화면에서 생성 권장")


def show_review_quality() -> None:
    history = read_csv(OUTPUTS_DIR / "review_history" / "review_history.csv")
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
    c3.metric("원본 수정률", f"{modified.mean():.1%}")
    c4.metric("GPT-사람 일치율", f"{(match & llm_available).sum()/llm_available.sum():.1%}" if llm_available.sum() else "-")

    if "error_type" in history.columns:
        tmp = history.copy()
        tmp["modified"] = modified.astype(int)
        grouped = tmp.groupby("error_type", dropna=False).agg(reviewed=("image_id", "count"), modified=("modified", "sum")).reset_index()
        grouped["수정률"] = grouped["modified"] / grouped["reviewed"].clip(lower=1)
        st.dataframe(grouped.sort_values("수정률", ascending=False), use_container_width=True, hide_index=True)

    label_rows = []
    for label in LABEL_KEYS:
        hcol, ocol = f"human_{label}", f"original_{label}"
        if hcol in history.columns and ocol in history.columns:
            h = pd.to_numeric(history[hcol], errors="coerce").fillna(0).astype(int)
            o = pd.to_numeric(history[ocol], errors="coerce").fillna(0).astype(int)
            label_rows.append({"label": label, "수정건수": int((h != o).sum()), "수정률": float((h != o).mean())})
    if label_rows:
        st.markdown("### 클래스별 수정률")
        st.dataframe(pd.DataFrame(label_rows).sort_values("수정률", ascending=False), use_container_width=True, hide_index=True)


def show_review_reason_stats() -> None:
    st.markdown("## 검수 대상 선정 이유")
    frames = []
    root = OUTPUTS_DIR / "review_lists"
    if root.exists():
        for path in root.glob("*.csv"):
            try:
                frame = pd.read_csv(path)
            except Exception:
                continue
            if not frame.empty:
                frames.append(frame)
    if not frames:
        st.info("검수 목록 CSV가 아직 없습니다.")
        return
    df = pd.concat(frames, ignore_index=True, sort=False)
    if "review_reasons" in df.columns:
        reasons = []
        for value in df["review_reasons"].fillna("").astype(str):
            reasons.extend([r.strip() for r in value.split(",") if r.strip()] or ["-"])
        st.dataframe(pd.Series(reasons).value_counts().rename_axis("reason").reset_index(name="count"), use_container_width=True, hide_index=True)


def show_backup() -> None:
    st.markdown("## 본작업 백업")
    keep = backup_keep_count()
    if st.button("현재 outputs 백업 생성", use_container_width=True):
        with st.spinner("백업 생성 중..."):
            result = create_outputs_backup(OUTPUTS_DIR, keep_count=keep)
        st.success(f"백업 완료: {result['path']} · {result['file_count']}개 파일")
    backup_dir = OUTPUTS_DIR / "backups" / "project_outputs"
    backups = sorted(backup_dir.glob("outputs_backup_*.zip"), reverse=True) if backup_dir.exists() else []
    if backups:
        st.dataframe(pd.DataFrame([{"파일": p.name, "크기(MB)": round(p.stat().st_size / 1024 / 1024, 2)} for p in backups[:keep]]), use_container_width=True, hide_index=True)


def show_csv_browser() -> None:
    st.markdown("## 개별 결과 CSV 보기")
    roots = [OUTPUTS_DIR / "llm_results", OUTPUTS_DIR / "compare_results", OUTPUTS_DIR / "review_lists"]
    files = [p for root in roots if root.exists() for p in root.glob("*.csv")]
    if not files:
        st.info("결과 CSV가 없습니다.")
        return
    selected = st.selectbox("파일", sorted(files), format_func=lambda p: p.name)
    df = read_csv(selected)
    if df is not None:
        st.dataframe(df.head(200), use_container_width=True)


show_project_progress()
st.divider()
show_review_quality()
st.divider()
show_review_reason_stats()
st.divider()
show_backup()
st.divider()
show_csv_browser()
