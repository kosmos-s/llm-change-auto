"""Streamlit UI for the OpenAI auto-labeling pipeline."""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from compare_labels import compare
from data_quality import summarize_quality, validate_index
from make_review_list import make_review_list
from project_paths import (
    dataset_root_default,
    default_cost_limit_usd,
    ensure_output_dirs,
    openai_target_total,
)
from results_inventory import unique_openai_results
from run_llm_labeling import run as run_llm
from scan_dataset import scan_dataset

load_dotenv(PROJECT_ROOT / ".env")
OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)

st.set_page_config(page_title="OpenAI 자동판정", layout="wide", initial_sidebar_state="expanded")

SOURCE_OPTIONS = ["dataset", "errors", "all"]
SPLIT_OPTIONS = ["test", "train", "val", "all"]
PROMPT_OPTIONS = [
    "prompts/prompt_v4_quality.txt",
    "prompts/prompt_v3_json_strict.txt",
    "prompts/prompt_v2_guideline.txt",
    "prompts/prompt_v1_basic.txt",
]


def path_from_project(relative_path: str | Path) -> Path:
    path = Path(relative_path)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_csv_safe(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception as exc:
        st.error(f"CSV를 읽을 수 없습니다: {path}\n{exc}")
        return None


def csv_download_button(df: pd.DataFrame, filename: str, label: str) -> None:
    csv_bytes = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(label, data=csv_bytes, file_name=filename, mime="text/csv", use_container_width=True)


def show_csv_preview(path: Path, title: str, max_rows: int = 20) -> None:
    st.markdown(f"### {title}")
    st.caption(str(path))
    df = read_csv_safe(path)
    if df is None:
        st.info("아직 파일이 없습니다.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", len(df))
    c2.metric("Columns", len(df.columns))
    if "review_required_final" in df.columns:
        review_count = df["review_required_final"].astype(str).str.lower().isin(["true", "1", "yes", "y", "o"]).sum()
        c3.metric("Review", int(review_count))
    elif "error" in df.columns:
        error_count = df["error"].fillna("").astype(str).str.strip().ne("").sum()
        c3.metric("Errors", int(error_count))
    else:
        c3.metric("Preview", min(max_rows, len(df)))
    st.dataframe(df.head(max_rows), use_container_width=True, height=360)
    csv_download_button(df, path.name, f"{path.name} 다운로드")


def show_summary(path: Path) -> None:
    df = read_csv_safe(path)
    if df is None:
        return
    with st.expander("요약 보기", expanded=False):
        if "group" in df.columns and "split" in df.columns:
            st.dataframe(df.groupby(["group", "split"], dropna=False).size().reset_index(name="count"), use_container_width=True)
        if "llm_provider" in df.columns:
            group_cols = [col for col in ["llm_provider", "llm_model"] if col in df.columns]
            st.dataframe(df.groupby(group_cols, dropna=False).size().reset_index(name="count"), use_container_width=True)
        if "review_reasons" in df.columns:
            st.dataframe(df.groupby("review_reasons", dropna=False).size().reset_index(name="count"), use_container_width=True)
        if "confidence" in df.columns:
            st.dataframe(pd.to_numeric(df["confidence"], errors="coerce").describe().reset_index(), use_container_width=True)


def reviewed_counts() -> tuple[int, dict[str, int]]:
    root = OUTPUTS_DIR / "reviewed_json"
    files = list(root.rglob("*.json")) if root.exists() else []
    by_split = {"train": 0, "val": 0, "test": 0}
    for path in files:
        parts = [p.lower() for p in path.parts]
        for split in by_split:
            if split in parts:
                by_split[split] += 1
                break
    return len(files), by_split


def production_openai_results() -> pd.DataFrame:
    frame = unique_openai_results(OUTPUTS_DIR / "llm_results")
    if frame.empty:
        return frame
    if "work_mode" in frame.columns:
        work_mode = frame["work_mode"].fillna("").astype(str).str.strip().str.lower()
        production = frame[work_mode.isin(["production", "prod", "본작업"])].copy()
        if not production.empty:
            return production
    return frame


def fmt_seconds(seconds: float) -> str:
    seconds = max(int(seconds or 0), 0)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def make_default_prefix(work_mode: str, source: str, split: str, start: int, limit: int) -> str:
    end = start + max(limit - 1, 0)
    mode = "prod" if work_mode == "production" else "test"
    return f"{mode}_openai_{source}_{split}_{start:05d}_{end:05d}"


def render_settings() -> dict[str, object]:
    st.sidebar.title("OpenAI 자동판정 설정")
    default_root = str(dataset_root_default(PROJECT_ROOT))
    dataset_root = st.sidebar.text_input("데이터 루트 경로", value=default_root)

    work_mode = st.sidebar.radio("작업 모드", ["production", "test"], format_func=lambda v: "본작업" if v == "production" else "테스트", horizontal=True)
    source = st.sidebar.radio("데이터 종류", SOURCE_OPTIONS, horizontal=True)
    split = st.sidebar.radio("분할", SPLIT_OPTIONS, horizontal=True)
    c1, c2 = st.sidebar.columns(2)
    start = int(c1.number_input("시작 번호", min_value=0, value=0, step=1))
    limit = int(c2.number_input("개수", min_value=1, value=1000 if work_mode == "production" else 1, step=1))

    index_path = OUTPUTS_DIR / "dataset_index.csv"
    index_df = read_csv_safe(index_path)
    error_types: list[str] = []
    if index_df is not None and source in {"errors", "all"} and "error_type" in index_df.columns:
        options = sorted(v for v in index_df["error_type"].fillna("").astype(str).unique() if v)
        error_types = st.sidebar.multiselect("errors 유형", options, default=[])

    selection_mode = st.sidebar.selectbox(
        "대상 선택 방식",
        ["sequential", "balanced", "random"],
        format_func=lambda v: {"sequential": "순차", "balanced": "오류유형 균형", "random": "랜덤"}[v],
    )
    exclude_reviewed = st.sidebar.checkbox("이미 사람 검수한 항목 제외", value=True)

    model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")
    prompt = st.sidebar.selectbox("프롬프트", PROMPT_OPTIONS, index=0)
    confidence = st.sidebar.slider("검수 기준 confidence", 0.0, 1.0, 0.70, 0.05)

    st.sidebar.markdown("#### 중단/재실행 안전 설정")
    resume = st.sidebar.checkbox("중단된 결과 이어서 처리", value=True)
    retry_failed = st.sidebar.checkbox("기존 실패 항목 자동 재시도", value=True)
    retry_errors_only = st.sidebar.checkbox("실패 항목만 재시도", value=False)
    max_attempts = int(st.sidebar.number_input("항목당 최대 API 시도", min_value=1, max_value=10, value=3, step=1))
    backoff = float(st.sidebar.number_input("재시도 기본 대기(초)", min_value=0.0, value=2.0, step=0.5))

    st.sidebar.markdown("#### 비용 안전장치")
    input_price = float(st.sidebar.number_input("입력 $ / 1M tokens", min_value=0.0, value=float(os.getenv("OPENAI_INPUT_PRICE_PER_1M", "0") or 0), step=0.01, format="%.4f"))
    output_price = float(st.sidebar.number_input("출력 $ / 1M tokens", min_value=0.0, value=float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M", "0") or 0), step=0.01, format="%.4f"))
    cost_limit = float(st.sidebar.number_input("이번 결과파일 비용 상한($, 0=무제한)", min_value=0.0, value=default_cost_limit_usd(), step=1.0))
    st.sidebar.caption("가격은 변동될 수 있으므로 현재 OpenAI 가격을 직접 입력하세요. 실제 토큰 사용량은 CSV에 기록됩니다.")

    pricing_ready = input_price > 0 or output_price > 0
    allow_unpriced = True
    if work_mode == "production" and not pricing_ready:
        st.sidebar.warning("본작업인데 토큰 단가가 0입니다. 이 상태에서는 비용 상한을 정확히 계산할 수 없습니다.")
        allow_unpriced = st.sidebar.checkbox("단가 0 상태로 본작업 실행 허용", value=False)

    batch_size_confirmed = True
    if work_mode == "production" and limit > 1000:
        st.sidebar.warning("한 번에 1,000건을 초과했습니다. 배치 분할을 권장합니다.")
        batch_size_confirmed = st.sidebar.checkbox("1,000건 초과 실행을 확인", value=False)

    default_prefix = make_default_prefix(work_mode, source, split, start, limit)
    output_prefix = st.sidebar.text_input("출력 파일 접두어", value=default_prefix)

    st.sidebar.divider()
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here":
        st.sidebar.success("OPENAI_API_KEY 확인됨")
    else:
        st.sidebar.warning("OPENAI_API_KEY가 없습니다. 로컬 .env 파일을 확인하세요.")

    return {
        "dataset_root": dataset_root,
        "work_mode": work_mode,
        "source": source,
        "split": split,
        "start": start,
        "limit": limit,
        "error_types": error_types,
        "selection_mode": selection_mode,
        "exclude_reviewed": exclude_reviewed,
        "model": model,
        "prompt": prompt,
        "confidence": confidence,
        "resume": resume,
        "retry_failed": retry_failed,
        "retry_errors_only": retry_errors_only,
        "max_attempts": max_attempts,
        "backoff": backoff,
        "input_price": input_price,
        "output_price": output_price,
        "cost_limit": cost_limit,
        "output_prefix": output_prefix.strip() or default_prefix,
        "api_key_exists": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here"),
        "allow_unpriced": allow_unpriced,
        "batch_size_confirmed": batch_size_confirmed,
    }


def main() -> None:
    settings = render_settings()
    st.title("1. OpenAI 자동판정")
    st.caption("데이터 인덱스 → GPT 자동판정 → 기존 라벨 비교 → 우선순위 검수 목록")

    reviewed_total, reviewed_split = reviewed_counts()
    llm_all = production_openai_results()
    llm_count = len(llm_all)
    goal = openai_target_total()
    llm_errors = 0
    if not llm_all.empty and "error" in llm_all.columns:
        llm_errors = int(llm_all["error"].fillna("").astype(str).str.strip().ne("").sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("OpenAI 본작업 완료", f"{llm_count:,} / {goal:,}")
    c2.metric("사람 검수 완료", reviewed_total)
    c3.metric("OpenAI 목표까지 남음", max(goal - llm_count, 0))
    c4.metric("현재 OpenAI 오류", llm_errors)
    st.progress(min(llm_count / goal, 1.0), text=f"OpenAI 본작업 진행률 {llm_count:,}/{goal:,} ({min(llm_count / goal, 1.0):.1%})")
    st.caption(f"사람 검수는 3,000건 전체가 아니라 자동 선별된 후보만 진행합니다. split별 사람 검수: train {reviewed_split['train']} / val {reviewed_split['val']} / test {reviewed_split['test']}")

    index_path = OUTPUTS_DIR / "dataset_index.csv"
    llm_path = OUTPUTS_DIR / "llm_results" / f"{settings['output_prefix']}.csv"
    compare_path = OUTPUTS_DIR / "compare_results" / f"{settings['output_prefix']}_compare.csv"
    review_path = OUTPUTS_DIR / "review_lists" / f"{settings['output_prefix']}_review.csv"
    checkpoint_path = llm_path.with_suffix(".checkpoint.json")
    prompt_path = path_from_project(str(settings["prompt"]))

    st.markdown("## 1) 데이터 인덱스 / 무결성")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("dataset_index.csv 생성", type="primary", use_container_width=True):
            root = Path(str(settings["dataset_root"]))
            if not root.exists():
                st.error(f"데이터 경로가 없습니다: {root}")
            else:
                with st.spinner("데이터셋 스캔 중..."):
                    df = scan_dataset(root)
                    index_path.parent.mkdir(parents=True, exist_ok=True)
                    df.to_csv(index_path, index=False, encoding="utf-8-sig")
                st.success(f"생성 완료: {len(df):,}개")
    with c2:
        if st.button("데이터 무결성 검사", use_container_width=True, disabled=not index_path.exists()):
            report = validate_index(index_path, Path(str(settings["dataset_root"])))
            report_path = OUTPUTS_DIR / "quality" / "dataset_quality.csv"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report.to_csv(report_path, index=False, encoding="utf-8-sig")
            summary = summarize_quality(report)
            if summary["errors"]:
                st.error(f"오류 {summary['errors']}건 / 경고 {summary['warnings']}건")
            elif summary["warnings"]:
                st.warning(f"오류 0건 / 경고 {summary['warnings']}건")
            else:
                st.success("무결성 검사 통과")
            if not report.empty:
                st.dataframe(report.head(200), use_container_width=True)
    show_summary(index_path)

    st.markdown("## 2) OpenAI 자동판정")
    next_start = int(settings["start"]) + int(settings["limit"])
    st.caption(f"현재 Batch: `{settings['output_prefix']}` · 다음 순차 Batch 시작번호 제안: `{next_start}`")

    if llm_path.exists():
        existing = read_csv_safe(llm_path)
        st.warning(f"동일한 결과 파일이 이미 있습니다: {llm_path.name} / {0 if existing is None else len(existing)}행")
        st.caption("`중단된 결과 이어서 처리`가 켜져 있으면 성공한 항목은 자동 Skip하고 미처리/실패 항목만 처리합니다.")

    overwrite_confirm = True
    if llm_path.exists() and not bool(settings["resume"]) and not bool(settings["retry_errors_only"]):
        overwrite_confirm = st.checkbox("기존 결과를 새 작업으로 덮어쓸 수 있음을 확인", value=False)

    progress_bar = st.progress(0.0, text="대기 중")
    metrics = st.empty()
    current_box = st.empty()

    def progress_callback(state: dict[str, object]) -> None:
        total = int(state.get("total_to_run", 0) or 0)
        done = int(state.get("completed_this_run", 0) or 0)
        fraction = done / total if total else 1.0
        progress_bar.progress(min(fraction, 1.0), text=f"이번 실행 {done:,} / {total:,} ({fraction:.1%})")
        with metrics.container():
            a, b, c, d, e = st.columns(5)
            a.metric("완료", done)
            b.metric("기존 완료 Skip", int(state.get("already_complete", 0) or 0))
            c.metric("오류", int(state.get("error_count", 0) or 0))
            d.metric("경과", fmt_seconds(float(state.get("elapsed_seconds", 0) or 0)))
            e.metric("ETA", fmt_seconds(float(state.get("eta_seconds", 0) or 0)))
            a2, b2, c2 = st.columns(3)
            a2.metric("처리속도", f"{float(state.get('items_per_minute', 0) or 0):.1f} 건/분")
            b2.metric("추정 누적비용", f"${float(state.get('estimated_cost_usd', 0) or 0):.4f}")
            c2.metric("입력/출력 토큰", f"{int(state.get('input_tokens', 0) or 0):,} / {int(state.get('output_tokens', 0) or 0):,}")
        image_id = str(state.get("image_id", "") or "")
        stop_reason = str(state.get("stop_reason", "") or "")
        if stop_reason:
            current_box.warning(f"중지 사유: {stop_reason}")
        elif image_id:
            current_box.info(f"최근 처리: `{image_id}`")

    run_disabled = (
        (not bool(settings["api_key_exists"]))
        or (not index_path.exists())
        or (not overwrite_confirm)
        or (not bool(settings["allow_unpriced"]))
        or (not bool(settings["batch_size_confirmed"]))
    )
    if st.button("OpenAI 실행 / 이어서 처리", type="primary", use_container_width=True, disabled=run_disabled):
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            result = run_llm(
                input_csv=index_path,
                prompt_path=prompt_path,
                output_csv=llm_path,
                source=str(settings["source"]),
                split=str(settings["split"]),
                start=int(settings["start"]),
                limit=int(settings["limit"]),
                model=str(settings["model"]),
                progress_callback=progress_callback,
                resume=bool(settings["resume"]),
                retry_failed=bool(settings["retry_failed"]),
                retry_errors_only=bool(settings["retry_errors_only"]),
                max_attempts=int(settings["max_attempts"]),
                retry_backoff_seconds=float(settings["backoff"]),
                checkpoint_path=checkpoint_path,
                run_id=run_id,
                batch_id=str(settings["output_prefix"]),
                work_mode=str(settings["work_mode"]),
                error_types=list(settings["error_types"]),
                selection_mode=str(settings["selection_mode"]),
                exclude_reviewed_root=(OUTPUTS_DIR / "reviewed_json") if settings["exclude_reviewed"] else None,
                input_price_per_million=float(settings["input_price"]),
                output_price_per_million=float(settings["output_price"]),
                cost_limit_usd=float(settings["cost_limit"]),
            )
            st.success(f"결과 저장 완료: {llm_path.name} / 현재 {len(result):,}행")
        except Exception as exc:
            st.error(str(exc))
    show_csv_preview(llm_path, "OpenAI 결과")

    st.markdown("## 3) 기존 JSON 라벨과 비교")
    if st.button("비교 실행", type="primary", use_container_width=True):
        if not llm_path.exists():
            st.error("먼저 OpenAI 결과 CSV를 생성하세요.")
        else:
            compare(llm_path, compare_path, confidence_threshold=float(settings["confidence"]))
            st.success(f"비교 결과 생성 완료: {compare_path.name}")
    show_csv_preview(compare_path, "비교 결과")

    st.markdown("## 4) 우선순위 검수 목록 생성")
    if st.button("검수 목록 생성", type="primary", use_container_width=True):
        if not compare_path.exists():
            st.error("먼저 비교 결과 CSV를 생성하세요.")
        else:
            review_df = make_review_list(compare_path, review_path)
            st.success(f"검수 목록 생성 완료: {len(review_df):,}건 · priority_score 높은 순")
    show_csv_preview(review_path, "검수 대상 목록")

    st.markdown("## 다음 단계")
    st.info("검수 목록이 만들어지면 **2. 사람 검수**에서 LLM 검수 대상 CSV 모드로 불러오세요. 본작업 결과 CSV와 reviewed_json은 이제 삭제하지 않는 것을 권장합니다.")


if __name__ == "__main__":
    main()
