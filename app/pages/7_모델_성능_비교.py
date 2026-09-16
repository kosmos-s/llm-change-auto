"""Compare baseline and cleaned-data model metrics."""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from model_metrics import compare_metrics, load_metrics_file
from project_paths import ensure_output_dirs

OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)
MODEL_EVAL_DIR = OUTPUTS_DIR / "model_eval"
MODEL_EVAL_DIR.mkdir(parents=True, exist_ok=True)

st.title("7. 모델 성능 비교")
st.caption("기존 변화탐지 모델과 정제 데이터 재학습 모델의 Precision / Recall / F1 / F2를 비교합니다.")
st.info("이 화면의 F2가 산학과제 최종 모델 성능 비교용입니다. 6번 LLM 결과 분석의 GPT 비교용 F2와 구분해서 사용하세요.")


def metrics_from_upload(uploaded) -> dict[str, float]:
    if uploaded is None:
        return {}
    suffix = Path(uploaded.name).suffix.lower()
    if suffix == ".json":
        data = json.loads(uploaded.getvalue().decode("utf-8"))
        normalized = {str(k).lower(): float(v) for k, v in data.items() if str(k).lower() in {"precision", "recall", "f1", "f2"}}
        return normalized
    frame = pd.read_csv(io.BytesIO(uploaded.getvalue()))
    temp = MODEL_EVAL_DIR / f"_upload_{uploaded.name}"
    frame.to_csv(temp, index=False)
    try:
        return load_metrics_file(temp)
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def load_source(label: str, default_path: Path, key_prefix: str) -> dict[str, float]:
    st.markdown(f"### {label}")
    mode = st.radio("입력 방식", ["파일 경로", "파일 업로드", "직접 입력"], horizontal=True, key=f"{key_prefix}_mode")
    if mode == "파일 경로":
        path_text = st.text_input("metrics JSON/CSV 경로", value=str(default_path), key=f"{key_prefix}_path")
        path = Path(path_text)
        if path.exists():
            try:
                metrics = load_metrics_file(path)
                st.success(f"불러옴: {path.name}")
                return metrics
            except Exception as exc:
                st.error(str(exc))
        else:
            st.caption("파일이 아직 없습니다.")
        return {}
    if mode == "파일 업로드":
        uploaded = st.file_uploader("JSON 또는 CSV", type=["json", "csv"], key=f"{key_prefix}_upload")
        if uploaded is None:
            return {}
        try:
            return metrics_from_upload(uploaded)
        except Exception as exc:
            st.error(str(exc))
            return {}

    c1, c2 = st.columns(2)
    precision = c1.number_input("Precision", min_value=0.0, max_value=1.0, value=0.0, step=0.001, format="%.4f", key=f"{key_prefix}_precision")
    recall = c2.number_input("Recall", min_value=0.0, max_value=1.0, value=0.0, step=0.001, format="%.4f", key=f"{key_prefix}_recall")
    c3, c4 = st.columns(2)
    f1 = c3.number_input("F1", min_value=0.0, max_value=1.0, value=0.0, step=0.001, format="%.4f", key=f"{key_prefix}_f1")
    f2 = c4.number_input("F2", min_value=0.0, max_value=1.0, value=0.0, step=0.001, format="%.4f", key=f"{key_prefix}_f2")
    return {"precision": precision, "recall": recall, "f1": f1, "f2": f2}


left, right = st.columns(2)
with left:
    before = load_source("기존 모델 (Baseline)", MODEL_EVAL_DIR / "baseline_metrics.json", "before")
with right:
    after = load_source("정제 데이터 재학습 모델", MODEL_EVAL_DIR / "cleaned_metrics.json", "after")

if before and after:
    comparison = compare_metrics(before, after)
    st.divider()
    st.markdown("## Before / After")
    st.dataframe(comparison, use_container_width=True, hide_index=True)

    before_f2 = before.get("f2")
    after_f2 = after.get("f2")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("기존 F2", "-" if before_f2 is None else f"{before_f2:.4f}")
    c2.metric("정제 후 F2", "-" if after_f2 is None else f"{after_f2:.4f}")
    if before_f2 is not None and after_f2 is not None:
        c3.metric("F2 변화", f"{after_f2 - before_f2:+.4f}")
        c4.metric("목표 F2 0.85", "달성" if after_f2 >= 0.85 else f"{0.85 - after_f2:.4f} 남음")

    export = {
        "baseline": before,
        "cleaned": after,
        "delta": {row["metric"]: row["delta"] for _, row in comparison.iterrows()},
    }
    st.download_button(
        "비교 결과 JSON 다운로드",
        data=json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name="model_before_after_comparison.json",
        mime="application/json",
    )
else:
    st.info("기존 모델과 정제 후 모델의 평가 결과를 모두 입력하면 비교표가 표시됩니다.")

with st.expander("평가 파일 형식 예시"):
    st.code(
        '{\n  "precision": 0.80,\n  "recall": 0.88,\n  "f1": 0.84,\n  "f2": 0.86\n}',
        language="json",
    )
    st.caption("CSV는 precision, recall, f1, f2 컬럼을 가진 1행 형식 또는 metric,value 두 컬럼 형식을 지원합니다.")
