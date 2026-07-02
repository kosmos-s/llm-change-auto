"""Streamlit UI for the LLM auto-labeling pipeline.

Run:
    streamlit run app/llm_pipeline_app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from compare_labels import compare
from make_review_list import make_review_list
from run_llm_labeling import run as run_llm
from scan_dataset import scan_dataset


load_dotenv(PROJECT_ROOT / ".env")

st.set_page_config(
    page_title="LLM 자동화 파이프라인",
    layout="wide",
    initial_sidebar_state="expanded",
)

SOURCE_OPTIONS = ["dataset", "errors", "all"]
SPLIT_OPTIONS = ["test", "train", "val", "all"]
PROMPT_OPTIONS = [
    "prompts/prompt_v3_json_strict.txt",
    "prompts/prompt_v2_guideline.txt",
    "prompts/prompt_v1_basic.txt",
]


def path_from_project(relative_path: str | Path) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


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
            st.markdown("**group / split 개수**")
            st.dataframe(df.groupby(["group", "split"], dropna=False).size().reset_index(name="count"), use_container_width=True)
        if "review_reasons" in df.columns:
            st.markdown("**review_reasons 개수**")
            st.dataframe(df.groupby("review_reasons", dropna=False).size().reset_index(name="count"), use_container_width=True)
        if "confidence" in df.columns:
            st.markdown("**confidence 통계**")
            st.dataframe(pd.to_numeric(df["confidence"], errors="coerce").describe().reset_index(), use_container_width=True)


def make_default_prefix(source: str, split: str, limit: int) -> str:
    limit_part = f"{limit}" if limit else "all"
    return f"{source}_{split}_{limit_part}"


def render_settings() -> dict[str, object]:
    st.sidebar.title("LLM 자동화 설정")

    default_root = str(Path.home() / "Desktop" / "산학과제" / "dataset_sample")
    dataset_root = st.sidebar.text_input("데이터 루트 경로", value=default_root)

    source = st.sidebar.radio("데이터 종류", SOURCE_OPTIONS, horizontal=True)
    split = st.sidebar.radio("분할", SPLIT_OPTIONS, horizontal=True)

    c1, c2 = st.sidebar.columns(2)
    start = c1.number_input("시작 번호", min_value=0, value=0, step=1)
    limit = c2.number_input("개수", min_value=1, value=10, step=1)

    model = st.sidebar.text_input("OpenAI 모델", value="gpt-4o-mini")
    prompt = st.sidebar.selectbox("프롬프트", PROMPT_OPTIONS, index=0)
    confidence = st.sidebar.slider("검수 기준 confidence", min_value=0.0, max_value=1.0, value=0.70, step=0.05)

    default_prefix = make_default_prefix(source, split, int(limit))
    output_prefix = st.sidebar.text_input("출력 파일 접두어", value=default_prefix)

    st.sidebar.divider()
    api_key_exists = bool(os.getenv("OPENAI_API_KEY"))
    if api_key_exists:
        st.sidebar.success("OPENAI_API_KEY 확인됨")
    else:
        st.sidebar.warning("OPENAI_API_KEY가 없습니다. .env 파일을 확인하세요.")

    return {
        "dataset_root": dataset_root,
        "source": source,
        "split": split,
        "start": int(start),
        "limit": int(limit),
        "model": model,
        "prompt": prompt,
        "confidence": float(confidence),
        "output_prefix": output_prefix.strip() or default_prefix,
    }


def main() -> None:
    settings = render_settings()

    st.title("LLM 자동화 파이프라인")
    st.caption("데이터 인덱스 생성 → LLM 자동판별 → 기존 JSON 라벨 비교 → 검수 대상 CSV 생성")

    index_path = PROJECT_ROOT / "outputs" / "dataset_index.csv"
    llm_path = PROJECT_ROOT / "outputs" / "llm_results" / f"{settings['output_prefix']}.csv"
    compare_path = PROJECT_ROOT / "outputs" / "compare_results" / f"{settings['output_prefix']}_compare.csv"
    review_path = PROJECT_ROOT / "outputs" / "review_lists" / f"{settings['output_prefix']}_review.csv"
    prompt_path = path_from_project(str(settings["prompt"]))

    st.markdown("## 1. 데이터 인덱스 생성")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("dataset_index.csv 생성", type="primary", use_container_width=True):
            root = Path(str(settings["dataset_root"]))
            if not root.exists():
                st.error(f"데이터 경로가 없습니다: {root}")
            else:
                with st.spinner("데이터셋을 스캔하는 중..."):
                    index_path.parent.mkdir(parents=True, exist_ok=True)
                    df = scan_dataset(root)
                    df.to_csv(index_path, index=False, encoding="utf-8-sig")
                st.success(f"생성 완료: {index_path} / {len(df)}개")
    with c2:
        st.code(f"python src\\scan_dataset.py --root \"{settings['dataset_root']}\"")

    show_summary(index_path)

    st.markdown("## 2. LLM 자동판별")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("LLM 실행", type="primary", use_container_width=True):
            if not index_path.exists():
                st.error("먼저 dataset_index.csv를 생성하세요.")
            elif not prompt_path.exists():
                st.error(f"프롬프트 파일이 없습니다: {prompt_path}")
            else:
                with st.spinner("LLM 자동판별 실행 중... 10장도 시간이 걸릴 수 있습니다."):
                    run_llm(
                        input_csv=index_path,
                        prompt_path=prompt_path,
                        output_csv=llm_path,
                        source=str(settings["source"]),
                        split=str(settings["split"]),
                        start=int(settings["start"]),
                        limit=int(settings["limit"]),
                        model=str(settings["model"]),
                    )
                st.success(f"LLM 결과 생성 완료: {llm_path}")
    with c2:
        st.code(
            "python src\\run_llm_labeling.py "
            f"--input outputs\\dataset_index.csv --source {settings['source']} --split {settings['split']} "
            f"--start {settings['start']} --limit {settings['limit']} --output outputs\\llm_results\\{settings['output_prefix']}.csv"
        )

    show_csv_preview(llm_path, "LLM 결과 미리보기")
    show_summary(llm_path)

    st.markdown("## 3. 기존 JSON 라벨과 비교")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("비교 실행", type="primary", use_container_width=True):
            if not llm_path.exists():
                st.error("먼저 LLM 결과 CSV를 생성하세요.")
            else:
                with st.spinner("기존 라벨과 LLM 결과 비교 중..."):
                    compare(llm_path, compare_path, confidence_threshold=float(settings["confidence"]))
                st.success(f"비교 결과 생성 완료: {compare_path}")
    with c2:
        st.code(
            "python src\\compare_labels.py "
            f"--llm outputs\\llm_results\\{settings['output_prefix']}.csv "
            f"--output outputs\\compare_results\\{settings['output_prefix']}_compare.csv"
        )

    show_csv_preview(compare_path, "비교 결과 미리보기")
    show_summary(compare_path)

    st.markdown("## 4. 검수 대상 목록 생성")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("검수 목록 생성", type="primary", use_container_width=True):
            if not compare_path.exists():
                st.error("먼저 비교 결과 CSV를 생성하세요.")
            else:
                with st.spinner("검수 대상 목록 생성 중..."):
                    make_review_list(compare_path, review_path)
                st.success(f"검수 목록 생성 완료: {review_path}")
    with c2:
        st.code(
            "python src\\make_review_list.py "
            f"--compare outputs\\compare_results\\{settings['output_prefix']}_compare.csv "
            f"--output outputs\\review_lists\\{settings['output_prefix']}_review.csv"
        )

    show_csv_preview(review_path, "검수 대상 목록 미리보기")
    show_summary(review_path)

    st.markdown("## 다음 단계")
    st.info("검수 대상 CSV가 만들어지면, 해당 파일 목록을 검수툴 UI와 연결해서 LLM이 의심한 항목만 순서대로 확인하는 기능을 추가할 수 있습니다.")


if __name__ == "__main__":
    main()
