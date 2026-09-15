"""Streamlit-based aerial image label verifier.

Run:
    streamlit run app/reviewer_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dataset_loader import SampleItem, find_combined_images, find_items_from_review_csv
from json_io import get_label_state, has_korean_reason, load_json, save_json, update_label_json
from review_events import append_review_event, backup_existing_reviewed_json, diff_keys


st.set_page_config(page_title="사람 검수", layout="wide", initial_sidebar_state="expanded")

LABEL_HELP = {
    "Artifact": "인공물 변화 전체",
    "arti_bu": "건물 신축/철거/구조/색상 변화",
    "arti_bu_t": "건물 기울임 변화",
    "arti_binil": "온실/비닐하우스 변화",
    "arti_road": "도로 신설/폐쇄/폭/노면 변화",
    "arti_roa_m": "도로 표식 변화",
    "arti_other": "적치물/옹벽/토지변형/건축중/태양광 등",
    "Tree": "나무 변화",
    "forest": "산림 변화",
    "farmland": "농경지 변화",
    "water": "수계 변화",
}

SOURCE_LABELS = {
    "dataset": "dataset - 일반 학습데이터",
    "errors": "errors - 오탐/미탐 검수데이터",
    "both": "both - dataset + errors",
}

LABEL_COMPARE_KEYS = [
    ("arti", "Artifact"), ("arti_bu", "arti_bu"), ("arti_bu_t", "arti_bu_t"),
    ("arti_binil", "arti_binil"), ("arti_road", "arti_road"), ("arti_roa_m", "arti_roa_m"),
    ("arti_other", "arti_other"), ("tree", "Tree"), ("fore", "forest"),
    ("farm", "farmland"), ("water", "water"),
]


@st.cache_data(show_spinner=False)
def load_items(root: str, split: str, source: str) -> list[SampleItem]:
    return find_combined_images(root, split, source)


@st.cache_data(show_spinner=False)
def load_review_items(csv_path: str) -> list[SampleItem]:
    return find_items_from_review_csv(csv_path)


def init_state() -> None:
    defaults = {
        "items": [], "raw_items": [], "index": 0, "loaded_root": "", "loaded_split": "test",
        "loaded_source": "dataset", "loaded_mode": "folder", "loaded_review_csv": "",
        "view_mode": "combined", "split_choice": "test", "source_choice": "dataset",
        "review_mode_choice": "folder", "filter_unreviewed": True, "filter_deferred": True,
        "filter_mismatch": False, "filter_low_conf": False, "filter_api_error": False,
        "filter_error_types": [], "filter_classes": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def normalize_folder(value: str) -> str:
    text = str(value or "").replace("\\", "/").strip().strip("/")
    return text if text and text != "." else "."


def reviewed_path_for_item(item: SampleItem) -> Path:
    target = PROJECT_ROOT / "outputs" / "reviewed_json" / item.source / item.split
    if normalize_folder(item.relative_folder) != ".":
        target = target / Path(item.relative_folder)
    return target / item.json_path.name


def item_is_reviewed(item: SampleItem) -> bool:
    return reviewed_path_for_item(item).exists()


def deferred_keys() -> set[str]:
    event_csv = PROJECT_ROOT / "outputs" / "review_events" / "review_events.csv"
    if not event_csv.exists():
        return set()
    try:
        df = pd.read_csv(event_csv)
    except Exception:
        return set()
    if df.empty or "status" not in df.columns:
        return set()
    latest = df.copy()
    latest["_key"] = (
        latest["source"].fillna("").astype(str) + "|" + latest["split"].fillna("").astype(str) + "|" +
        latest["relative_folder"].fillna(".").astype(str) + "|" + latest["image_id"].fillna("").astype(str)
    )
    latest = latest.drop_duplicates("_key", keep="last")
    return set(latest[latest["status"].astype(str) == "deferred"]["_key"].astype(str))


def item_key(item: SampleItem) -> str:
    return f"{item.source}|{item.split}|{normalize_folder(item.relative_folder)}|{item.image_id}"


def apply_review_filters(items: list[SampleItem]) -> list[SampleItem]:
    deferred = deferred_keys() if st.session_state.get("filter_deferred", True) else set()
    result: list[SampleItem] = []
    wanted_error_types = set(st.session_state.get("filter_error_types", []))
    wanted_classes = set(st.session_state.get("filter_classes", []))
    for item in items:
        info = item.llm_info or {}
        if st.session_state.get("filter_unreviewed", True) and item_is_reviewed(item):
            continue
        if item_key(item) in deferred:
            continue
        if st.session_state.get("filter_mismatch", False):
            mismatch = str(info.get("label_mismatch", "")).lower() in {"true", "1", "yes", "y", "o"}
            detail = str(info.get("detail_mismatch", "")).lower() in {"true", "1", "yes", "y", "o"}
            if not (mismatch or detail):
                continue
        if st.session_state.get("filter_low_conf", False):
            if str(info.get("low_confidence", "")).lower() not in {"true", "1", "yes", "y", "o"}:
                continue
        if st.session_state.get("filter_api_error", False):
            error = str(info.get("error", "") or "").strip()
            if not error or error.lower() == "nan":
                continue
        if wanted_error_types and item.error_type not in wanted_error_types:
            continue
        if wanted_classes and str(info.get("llm_class", "")) not in wanted_classes:
            continue
        result.append(item)
    return result


def refresh_filters() -> None:
    raw = st.session_state.get("raw_items", [])
    st.session_state["items"] = apply_review_filters(raw)
    st.session_state["index"] = 0


def clamp_index() -> None:
    items = st.session_state.get("items", [])
    if not items:
        st.session_state["index"] = 0
        return
    st.session_state["index"] = max(0, min(st.session_state["index"], len(items) - 1))


def current_item() -> SampleItem | None:
    items = st.session_state.get("items", [])
    if not items:
        return None
    clamp_index()
    return items[st.session_state["index"]]


def image_path_for_view(item: SampleItem, view_mode: str) -> Path:
    if view_mode == "left" and item.left_path.exists():
        return item.left_path
    if view_mode == "right" and item.right_path.exists():
        return item.right_path
    return item.combined_path


def widget_key(item: SampleItem, name: str) -> str:
    safe_folder = normalize_folder(item.relative_folder).replace("/", "_").replace(".", "root")
    review_row = item.llm_info.get("review_csv_row", "") if item.llm_info else ""
    return f"{item.source}_{item.split}_{safe_folder}_{item.image_id}_{review_row}_{name}"


def do_load_folder(root: str, split: str, source: str) -> None:
    root_path = Path(root)
    if not root_path.exists():
        st.sidebar.error(f"경로가 없습니다: {root_path}")
        return
    st.cache_data.clear()
    raw = load_items(str(root_path), split, source)
    st.session_state["raw_items"] = raw
    st.session_state["items"] = raw
    st.session_state["index"] = 0
    st.session_state["loaded_root"] = str(root_path)
    st.session_state["loaded_split"] = split
    st.session_state["loaded_source"] = source
    st.session_state["loaded_mode"] = "folder"
    st.session_state["loaded_review_csv"] = ""
    if raw:
        st.sidebar.success(f"{SOURCE_LABELS.get(source, source)} / {split}: {len(raw)}개 로드 완료")
    else:
        st.sidebar.warning("*_combined.jpg 파일을 찾지 못했습니다.")


def do_load_review_csv(csv_path: str) -> None:
    path = Path(csv_path)
    if not path.exists():
        st.sidebar.error(f"CSV 파일이 없습니다: {path}")
        return
    st.cache_data.clear()
    try:
        raw = load_review_items(str(path))
    except Exception as exc:
        st.sidebar.error(f"CSV를 불러오지 못했습니다: {exc}")
        return
    st.session_state["raw_items"] = raw
    st.session_state["items"] = apply_review_filters(raw)
    st.session_state["index"] = 0
    st.session_state["loaded_mode"] = "review_csv"
    st.session_state["loaded_review_csv"] = str(path)
    st.session_state["loaded_root"] = ""
    st.session_state["loaded_split"] = "csv"
    st.session_state["loaded_source"] = "csv"
    st.sidebar.success(f"검수 대상 CSV: 전체 {len(raw)}개 / 현재 필터 {len(st.session_state['items'])}개")


def render_sidebar() -> None:
    st.sidebar.title("데이터 불러오기")
    mode = st.sidebar.radio("검수 모드", ["folder", "review_csv"], format_func=lambda v: "폴더 전체 검수" if v == "folder" else "LLM 검수 대상 CSV", key="review_mode_choice")

    if mode == "folder":
        default_root = str(Path.home() / "Desktop" / "산학과제" / "dataset_sample")
        root = st.sidebar.text_input("데이터 루트 경로", value=st.session_state.get("loaded_root") or default_root)
        source = st.sidebar.radio("데이터 종류", ["dataset", "errors", "both"], format_func=lambda v: SOURCE_LABELS[v], key="source_choice")
        split = st.sidebar.radio("분할 선택", ["test", "train", "val", "all"], key="split_choice")
        if st.sidebar.button("Load / Reload", use_container_width=True):
            do_load_folder(root, split, source)
    else:
        default_csv = str(PROJECT_ROOT / "outputs" / "review_lists" / "prod_openai_errors_train_00000_00499_review.csv")
        csv_path = st.sidebar.text_input("review_list.csv 경로", value=st.session_state.get("loaded_review_csv") or default_csv)

        st.sidebar.markdown("#### 검수 필터")
        st.session_state["filter_unreviewed"] = st.sidebar.checkbox("미검수만 보기", value=st.session_state.get("filter_unreviewed", True))
        st.session_state["filter_deferred"] = st.sidebar.checkbox("보류 항목 제외", value=st.session_state.get("filter_deferred", True))
        st.session_state["filter_mismatch"] = st.sidebar.checkbox("라벨 불일치만", value=st.session_state.get("filter_mismatch", False))
        st.session_state["filter_low_conf"] = st.sidebar.checkbox("Low confidence만", value=st.session_state.get("filter_low_conf", False))
        st.session_state["filter_api_error"] = st.sidebar.checkbox("API 오류만", value=st.session_state.get("filter_api_error", False))

        raw = st.session_state.get("raw_items", [])
        error_options = sorted({item.error_type for item in raw if item.error_type})
        class_options = sorted({str((item.llm_info or {}).get("llm_class", "")) for item in raw if str((item.llm_info or {}).get("llm_class", ""))})
        st.session_state["filter_error_types"] = st.sidebar.multiselect("오류 유형", error_options, default=st.session_state.get("filter_error_types", []))
        st.session_state["filter_classes"] = st.sidebar.multiselect("GPT class", class_options, default=st.session_state.get("filter_classes", []))

        c1, c2 = st.sidebar.columns(2)
        if c1.button("Load CSV", use_container_width=True):
            do_load_review_csv(csv_path)
        if c2.button("필터 적용", use_container_width=True):
            refresh_filters()
            st.rerun()
        st.sidebar.caption("priority_score가 높은 항목부터 CSV에 정렬되어 있습니다.")

    if st.session_state.get("items"):
        st.sidebar.caption(f"현재 표시: {len(st.session_state['items'])}개")

    st.sidebar.divider()
    st.session_state["view_mode"] = st.sidebar.radio("표시 이미지", ["combined", "left", "right"], horizontal=True, key="view_mode_radio")


def render_navigation(total: int) -> None:
    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    with col1:
        if st.button("Previous File", use_container_width=True, disabled=st.session_state["index"] <= 0):
            st.session_state["index"] -= 1
            st.rerun()
    with col2:
        if st.button("Next File", use_container_width=True, disabled=st.session_state["index"] >= total - 1):
            st.session_state["index"] += 1
            st.rerun()
    with col3:
        jump_value = st.number_input("Jump", min_value=1, max_value=max(total, 1), value=st.session_state["index"] + 1, key=f"jump_{total}_{st.session_state['index']}")
    with col4:
        if st.button("Jump", use_container_width=True):
            st.session_state["index"] = int(jump_value) - 1
            st.rerun()


def read_current_ui_state(item: SampleItem) -> dict[str, object]:
    return {
        "Artifact": st.session_state.get(widget_key(item, "Artifact"), False),
        "arti_bu": st.session_state.get(widget_key(item, "arti_bu"), False),
        "arti_bu_t": st.session_state.get(widget_key(item, "arti_bu_t"), False),
        "arti_binil": st.session_state.get(widget_key(item, "arti_binil"), False),
        "arti_road": st.session_state.get(widget_key(item, "arti_road"), False),
        "arti_roa_m": st.session_state.get(widget_key(item, "arti_roa_m"), False),
        "arti_other": st.session_state.get(widget_key(item, "arti_other"), False),
        "Tree": st.session_state.get(widget_key(item, "Tree"), False),
        "forest": st.session_state.get(widget_key(item, "forest"), False),
        "farmland": st.session_state.get(widget_key(item, "farmland"), False),
        "water": st.session_state.get(widget_key(item, "water"), False),
        "reason": st.session_state.get(widget_key(item, "reason"), ""),
        "reason_ko": st.session_state.get(widget_key(item, "reason_ko"), ""),
    }


def source_data_for_item(item: SampleItem) -> tuple[Path, dict[str, Any]]:
    reviewed_path = reviewed_path_for_item(item)
    if reviewed_path.exists():
        return reviewed_path, load_json(reviewed_path)
    return item.json_path, load_json(item.json_path)


def log_review_event(item: SampleItem, status: str, before_state: dict[str, Any], after_state: dict[str, Any], save_path: str = "", note: str = "") -> None:
    info = item.llm_info or {}
    append_review_event(
        PROJECT_ROOT / "outputs" / "review_events" / "review_events.csv",
        {
            "image_id": item.image_id,
            "source": item.source,
            "split": item.split,
            "relative_folder": normalize_folder(item.relative_folder),
            "status": status,
            "save_path": save_path,
            "review_csv": info.get("review_csv", ""),
            "review_csv_row": info.get("review_csv_row", ""),
            "llm_model": info.get("llm_model", ""),
            "prompt_path": info.get("prompt_path", ""),
            "batch_id": info.get("batch_id", ""),
            "run_id": info.get("run_id", ""),
            "original_state": before_state,
            "new_state": after_state,
            "modified_keys": diff_keys(before_state, after_state),
            "note": note,
        },
    )


def save_current_item(item: SampleItem, data: dict[str, Any], save_mode: str, note: str) -> Path:
    before_state = get_label_state(data)
    new_state = read_current_ui_state(item)
    updated = update_label_json(data, new_state)
    if save_mode == "원본 JSON 덮어쓰기":
        save_path = item.json_path
    else:
        save_path = reviewed_path_for_item(item)
        backup_existing_reviewed_json(save_path, PROJECT_ROOT / "outputs" / "backups" / "reviewed_json")
    save_json(save_path, updated)
    after_state = get_label_state(updated)
    log_review_event(item, "saved", before_state, after_state, str(save_path), note)
    return save_path


def render_label_panel(item: SampleItem, total: int) -> None:
    data_path, data = source_data_for_item(item)
    state = get_label_state(data)
    ko_missing = not has_korean_reason(data)
    if data_path != item.json_path:
        st.success("기존 reviewed_json 값을 불러왔습니다.")

    st.subheader("타겟 클래스 / 세부 클래스")
    st.checkbox("Artifact", value=bool(state["Artifact"]), help=LABEL_HELP["Artifact"], key=widget_key(item, "Artifact"))
    st.markdown("**Artifact Detail**")
    for key in ["arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other"]:
        st.checkbox(key, value=bool(state[key]), help=LABEL_HELP[key], key=widget_key(item, key))
    st.divider()
    for key in ["Tree", "forest", "farmland", "water"]:
        st.checkbox(key, value=bool(state[key]), help=LABEL_HELP[key], key=widget_key(item, key))
    st.divider()
    st.text_area("reason", value=str(state["reason"]), height=90, key=widget_key(item, "reason"))
    st.text_area("reason (KO)", value=str(state["reason_ko"]), height=90, key=widget_key(item, "reason_ko"), placeholder="한글 검수 근거")
    if ko_missing:
        st.caption("현재 JSON에 reason_ko가 없습니다. 입력 후 저장하면 추가됩니다.")

    note = st.text_input("검수 메모(선택)", key=widget_key(item, "review_note"))
    save_mode = st.radio("저장 위치", ["reviewed_json 폴더에 저장", "원본 JSON 덮어쓰기"], horizontal=False)
    if save_mode == "원본 JSON 덮어쓰기":
        st.warning("본작업에서는 reviewed_json 저장을 권장합니다.")

    c1, c2, c3 = st.columns(3)
    if c1.button("저장", type="primary", use_container_width=True):
        save_path = save_current_item(item, data, save_mode, note)
        st.success(f"저장 완료: {save_path}")
    if c2.button("저장 + 다음", use_container_width=True):
        save_path = save_current_item(item, data, save_mode, note)
        if st.session_state["index"] < total - 1:
            st.session_state["index"] += 1
        st.rerun()
    if c3.button("보류 + 다음", use_container_width=True):
        before = get_label_state(data)
        log_review_event(item, "deferred", before, before, "", note)
        if st.session_state["index"] < total - 1:
            st.session_state["index"] += 1
        st.rerun()


def as_label(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"1", "1.0", "true", "o", "yes", "y"}:
        return "1"
    if text in {"0", "0.0", "false", "x", "no", "n", "", "nan"}:
        return "0"
    return str(value)


def render_llm_panel(item: SampleItem) -> None:
    info = item.llm_info or {}
    if not info:
        return
    st.markdown("### LLM 검수 정보")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("LLM change", info.get("llm_change", "-"))
    m2.metric("confidence", info.get("confidence", "-"))
    m3.metric("priority", info.get("priority_score", "-"))
    m4.metric("mismatch", info.get("label_mismatch", "-"))
    m5.metric("review", info.get("review_required_final", "-"))
    if info.get("review_reasons"):
        st.warning(f"검수 사유: {info.get('review_reasons')}")
    if info.get("detail_mismatch_keys"):
        st.info(f"세부 불일치: {info.get('detail_mismatch_keys')}")
    if info.get("error"):
        st.error(f"LLM 오류: {info.get('error')}")

    compare_rows = []
    for llm_key, display_key in LABEL_COMPARE_KEYS:
        original = as_label(info.get(f"original_{llm_key}", ""))
        llm_value = as_label(info.get(llm_key, ""))
        compare_rows.append({"label": display_key, "original": original, "llm": llm_value, "different": original != llm_value})
    compare_df = pd.DataFrame(compare_rows)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)

    if info.get("reason_ko") or info.get("reason_en"):
        with st.expander("LLM 판단 근거", expanded=True):
            if info.get("reason_ko"):
                st.markdown(f"**KO**: {info.get('reason_ko')}")
            if info.get("reason_en"):
                st.markdown(f"**EN**: {info.get('reason_en')}")


def main() -> None:
    init_state()
    render_sidebar()
    st.title("2. 사람 검수")
    st.caption("우선순위 검수 목록을 사람이 최종 확인하고 reviewed_json으로 저장합니다.")

    items = st.session_state.get("items", [])
    raw_items = st.session_state.get("raw_items", [])
    reviewed_in_raw = sum(1 for item in raw_items if item_is_reviewed(item)) if raw_items else 0
    if raw_items:
        c1, c2, c3 = st.columns(3)
        c1.metric("검수 목록 전체", len(raw_items))
        c2.metric("reviewed_json 완료", reviewed_in_raw)
        c3.metric("현재 필터 남음", len(items))
        st.progress(reviewed_in_raw / len(raw_items), text=f"이 목록 검수 진행률 {reviewed_in_raw}/{len(raw_items)} ({reviewed_in_raw/len(raw_items):.1%})")

    item = current_item()
    if item is None:
        st.info("왼쪽에서 데이터 또는 검수 CSV를 불러오세요. 미검수만 보기에서 0개라면 현재 목록 검수가 완료된 상태일 수 있습니다.")
        return

    total = len(items)
    st.markdown(f"**현재 [{st.session_state['index'] + 1}/{total}]** `{item.image_id}`")
    st.caption(f"source={item.source} | split={item.split} | folder={item.relative_folder} | error_type={item.error_type or '-'}")
    if item_is_reviewed(item):
        st.success("이 항목은 reviewed_json이 이미 있습니다. 기존 검수값을 불러옵니다.")

    if item.llm_info:
        render_llm_panel(item)

    left_col, right_col = st.columns([3.2, 1.25], gap="large")
    with left_col:
        path = image_path_for_view(item, st.session_state["view_mode"])
        st.image(str(path), caption=str(path), use_container_width=True)
        render_navigation(total)
    with right_col:
        render_label_panel(item, total)


if __name__ == "__main__":
    main()
