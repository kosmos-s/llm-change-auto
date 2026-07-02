"""Streamlit-based aerial image label verifier.

Run:
    streamlit run app/reviewer_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dataset_loader import SampleItem, find_combined_images, find_items_from_review_csv
from json_io import get_label_state, has_korean_reason, load_json, save_json, update_label_json


st.set_page_config(
    page_title="항공영상 학습데이터 검수툴",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    ("arti", "Artifact"),
    ("arti_bu", "arti_bu"),
    ("arti_bu_t", "arti_bu_t"),
    ("arti_binil", "arti_binil"),
    ("arti_road", "arti_road"),
    ("arti_roa_m", "arti_roa_m"),
    ("arti_other", "arti_other"),
    ("tree", "Tree"),
    ("fore", "forest"),
    ("farm", "farmland"),
    ("water", "water"),
]


@st.cache_data(show_spinner=False)
def load_items(root: str, split: str, source: str) -> list[SampleItem]:
    return find_combined_images(root, split, source)


@st.cache_data(show_spinner=False)
def load_review_items(csv_path: str) -> list[SampleItem]:
    return find_items_from_review_csv(csv_path)


def init_state() -> None:
    st.session_state.setdefault("items", [])
    st.session_state.setdefault("index", 0)
    st.session_state.setdefault("loaded_root", "")
    st.session_state.setdefault("loaded_split", "test")
    st.session_state.setdefault("loaded_source", "dataset")
    st.session_state.setdefault("loaded_mode", "folder")
    st.session_state.setdefault("loaded_review_csv", "")
    st.session_state.setdefault("view_mode", "combined")
    st.session_state.setdefault("split_choice", "test")
    st.session_state.setdefault("source_choice", "dataset")
    st.session_state.setdefault("review_mode_choice", "folder")


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
    safe_folder = item.relative_folder.replace("/", "_").replace("\\", "_").replace(".", "root")
    review_row = item.llm_info.get("review_csv_row", "") if item.llm_info else ""
    return f"{item.source}_{item.split}_{safe_folder}_{item.image_id}_{review_row}_{name}"


def do_load_folder(root: str, split: str, source: str) -> None:
    root_path = Path(root)
    if not root_path.exists():
        st.sidebar.error(f"경로가 없습니다: {root_path}")
        return

    st.cache_data.clear()
    st.session_state["items"] = load_items(str(root_path), split, source)
    st.session_state["index"] = 0
    st.session_state["loaded_root"] = str(root_path)
    st.session_state["loaded_split"] = split
    st.session_state["loaded_source"] = source
    st.session_state["loaded_mode"] = "folder"
    st.session_state["loaded_review_csv"] = ""

    if st.session_state["items"]:
        st.sidebar.success(f"{SOURCE_LABELS.get(source, source)} / {split}: {len(st.session_state['items'])}개 로드 완료")
    else:
        st.sidebar.warning("*_combined.jpg 파일을 찾지 못했습니다. 데이터 종류, 분할, 경로를 확인하세요.")


def do_load_review_csv(csv_path: str) -> None:
    path = Path(csv_path)
    if not path.exists():
        st.sidebar.error(f"CSV 파일이 없습니다: {path}")
        return

    st.cache_data.clear()
    try:
        items = load_review_items(str(path))
    except Exception as exc:
        st.sidebar.error(f"CSV를 불러오지 못했습니다: {exc}")
        return

    st.session_state["items"] = items
    st.session_state["index"] = 0
    st.session_state["loaded_mode"] = "review_csv"
    st.session_state["loaded_review_csv"] = str(path)
    st.session_state["loaded_root"] = ""
    st.session_state["loaded_split"] = "csv"
    st.session_state["loaded_source"] = "csv"

    if items:
        st.sidebar.success(f"검수 대상 CSV: {len(items)}개 로드 완료")
    else:
        st.sidebar.warning("CSV에서 image_path를 가진 검수 대상을 찾지 못했습니다.")


def render_sidebar() -> None:
    st.sidebar.title("데이터 불러오기")

    mode = st.sidebar.radio(
        "검수 모드",
        ["folder", "review_csv"],
        format_func=lambda value: "폴더 전체 검수" if value == "folder" else "LLM 검수 대상 CSV",
        key="review_mode_choice",
    )

    if mode == "folder":
        default_root = str(Path.home() / "Desktop" / "산학과제" / "dataset_sample")
        root = st.sidebar.text_input("데이터 루트 경로", value=st.session_state.get("loaded_root") or default_root)

        st.sidebar.caption("데이터 종류")
        source = st.sidebar.radio(
            "데이터 종류",
            ["dataset", "errors", "both"],
            format_func=lambda value: SOURCE_LABELS[value],
            key="source_choice",
            label_visibility="collapsed",
        )

        st.sidebar.caption("분할 선택")
        split = st.sidebar.radio(
            "분할 선택",
            ["test", "train", "val", "all"],
            key="split_choice",
            label_visibility="collapsed",
        )

        col1, col2 = st.sidebar.columns(2)
        with col1:
            if st.button("Load", use_container_width=True):
                do_load_folder(root, split, source)
        with col2:
            if st.button("Reload", use_container_width=True):
                do_load_folder(root, split, source)

        already_loaded = bool(st.session_state.get("items")) and st.session_state.get("loaded_mode") == "folder"
        same_root = str(Path(root)) == st.session_state.get("loaded_root")
        source_changed = source != st.session_state.get("loaded_source")
        split_changed = split != st.session_state.get("loaded_split")
        if already_loaded and same_root and (source_changed or split_changed):
            do_load_folder(root, split, source)

    else:
        default_csv = str(PROJECT_ROOT / "outputs" / "review_lists" / "dataset_test_10_review.csv")
        csv_path = st.sidebar.text_input("review_list.csv 경로", value=st.session_state.get("loaded_review_csv") or default_csv)
        if st.sidebar.button("Load Review CSV", use_container_width=True):
            do_load_review_csv(csv_path)
        st.sidebar.caption("LLM 자동화 UI에서 생성한 `outputs/review_lists/*_review.csv` 파일을 불러옵니다.")

    if st.session_state.get("items"):
        loaded_mode = st.session_state.get("loaded_mode")
        if loaded_mode == "review_csv":
            st.sidebar.caption(
                f"현재 로드: LLM 검수 대상 CSV / {len(st.session_state.get('items', []))}개"
            )
        else:
            st.sidebar.caption(
                f"현재 로드: {SOURCE_LABELS.get(st.session_state.get('loaded_source'), st.session_state.get('loaded_source'))} / "
                f"{st.session_state.get('loaded_split')} / "
                f"{len(st.session_state.get('items', []))}개"
            )

    st.sidebar.divider()
    st.sidebar.caption("이미지 보기")
    st.session_state["view_mode"] = st.sidebar.radio(
        "표시 이미지",
        ["combined", "left", "right"],
        horizontal=True,
        label_visibility="collapsed",
    )
    st.sidebar.caption("combined는 LLM 입력용, left/right는 참고용입니다.")


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
        jump_value = st.number_input(
            "Jump",
            min_value=1,
            max_value=max(total, 1),
            value=st.session_state["index"] + 1,
            key=f"jump_value_{total}_{st.session_state['index']}",
        )
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


def save_current_item(item: SampleItem, data: dict, save_mode: str) -> Path:
    new_state = read_current_ui_state(item)
    updated = update_label_json(data, new_state)
    if save_mode == "원본 JSON 덮어쓰기":
        save_path = item.json_path
    else:
        save_dir = PROJECT_ROOT / "outputs" / "reviewed_json" / item.source / item.split
        if item.relative_folder != ".":
            save_dir = save_dir / item.relative_folder
        save_path = save_dir / item.json_path.name
    save_json(save_path, updated)
    return save_path


def render_label_panel(item: SampleItem, total: int) -> None:
    data = load_json(item.json_path)
    state = get_label_state(data)
    ko_missing = not has_korean_reason(data)

    st.subheader("타겟 클래스 / 세부 클래스")

    st.checkbox("Artifact", value=bool(state["Artifact"]), help=LABEL_HELP["Artifact"], key=widget_key(item, "Artifact"))
    st.markdown("**Artifact Detail**")
    st.checkbox("arti_bu", value=bool(state["arti_bu"]), help=LABEL_HELP["arti_bu"], key=widget_key(item, "arti_bu"))
    st.checkbox("arti_bu_t", value=bool(state["arti_bu_t"]), help=LABEL_HELP["arti_bu_t"], key=widget_key(item, "arti_bu_t"))
    st.checkbox("arti_binil", value=bool(state["arti_binil"]), help=LABEL_HELP["arti_binil"], key=widget_key(item, "arti_binil"))
    st.checkbox("arti_road", value=bool(state["arti_road"]), help=LABEL_HELP["arti_road"], key=widget_key(item, "arti_road"))
    st.checkbox("arti_roa_m", value=bool(state["arti_roa_m"]), help=LABEL_HELP["arti_roa_m"], key=widget_key(item, "arti_roa_m"))
    st.checkbox("arti_other", value=bool(state["arti_other"]), help=LABEL_HELP["arti_other"], key=widget_key(item, "arti_other"))

    st.divider()
    st.checkbox("Tree", value=bool(state["Tree"]), help=LABEL_HELP["Tree"], key=widget_key(item, "Tree"))
    st.checkbox("forest", value=bool(state["forest"]), help=LABEL_HELP["forest"], key=widget_key(item, "forest"))
    st.checkbox("farmland", value=bool(state["farmland"]), help=LABEL_HELP["farmland"], key=widget_key(item, "farmland"))
    st.checkbox("water", value=bool(state["water"]), help=LABEL_HELP["water"], key=widget_key(item, "water"))

    st.divider()
    st.text_area("reason", value=str(state["reason"]), height=110, key=widget_key(item, "reason"))
    st.text_area(
        "reason (KO)",
        value=str(state["reason_ko"]),
        height=110,
        key=widget_key(item, "reason_ko"),
        placeholder="기존 JSON에 한글 설명이 없으면 비어 있습니다. 검수 후 한글 설명을 입력하세요.",
    )
    if ko_missing:
        st.caption("현재 JSON에 `reason_ko` 값이 없어 비어 있습니다. 입력 후 저장하면 `reason_ko` 필드가 새로 저장됩니다.")

    detail_keys = ["arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other"]
    if any(st.session_state.get(widget_key(item, key), False) for key in detail_keys) and not st.session_state.get(widget_key(item, "Artifact"), False):
        st.info("세부 인공물 라벨이 체크되어 저장 시 Artifact가 자동으로 체크됩니다.")

    save_mode = st.radio("저장 위치", ["reviewed_json 폴더에 저장", "원본 JSON 덮어쓰기"], horizontal=False)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save Changes", type="primary", use_container_width=True):
            save_path = save_current_item(item, data, save_mode)
            st.success(f"저장 완료: {save_path}")
    with col2:
        if st.button("Save & Next", use_container_width=True):
            save_path = save_current_item(item, data, save_mode)
            st.success(f"저장 완료: {save_path}")
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
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("LLM change", info.get("llm_change", "-"))
    m2.metric("confidence", info.get("confidence", "-"))
    m3.metric("mismatch", info.get("label_mismatch", "-"))
    m4.metric("review", info.get("review_required_final", "-"))

    if info.get("review_reasons"):
        st.warning(f"검수 사유: {info.get('review_reasons')}")
    if info.get("detail_mismatch_keys"):
        st.info(f"세부 불일치 라벨: {info.get('detail_mismatch_keys')}")
    if info.get("error"):
        st.error(f"LLM 오류: {info.get('error')}")

    compare_rows = []
    for llm_key, display_key in LABEL_COMPARE_KEYS:
        original_key = f"original_{llm_key}"
        if original_key in info or llm_key in info:
            compare_rows.append(
                {
                    "label": display_key,
                    "original": as_label(info.get(original_key, "")),
                    "llm": as_label(info.get(llm_key, "")),
                }
            )
    if compare_rows:
        st.dataframe(compare_rows, use_container_width=True, hide_index=True)

    if info.get("reason_ko") or info.get("reason_en"):
        with st.expander("LLM 판단 근거", expanded=True):
            if info.get("reason_ko"):
                st.markdown(f"**KO**: {info.get('reason_ko')}")
            if info.get("reason_en"):
                st.markdown(f"**EN**: {info.get('reason_en')}")

    with st.expander("CSV 원본 정보", expanded=False):
        st.json(info)


def main() -> None:
    init_state()
    render_sidebar()

    st.title("항공영상 학습데이터 검수툴")
    st.caption("폴더 전체 검수 또는 LLM이 생성한 review_list.csv 기반 검수를 지원합니다.")

    item = current_item()
    items = st.session_state.get("items", [])

    if item is None:
        st.info("왼쪽 사이드바에서 검수 모드를 선택하고 데이터를 불러오세요.")
        st.code(r"C:\Users\rlarj\Desktop\산학과제\dataset_sample")
        return

    total = len(items)
    st.markdown(f"**Loaded file [{st.session_state['index'] + 1}/{total}]**  `{item.image_id}`")
    st.caption(
        f"source={item.source} | split={item.split} | folder={item.relative_folder} | "
        f"error_type={item.error_type or '-'} | json={item.json_path}"
    )

    if st.session_state.get("loaded_mode") == "review_csv":
        st.info(f"현재 모드: LLM 검수 대상 CSV / {st.session_state.get('loaded_review_csv')}", icon="📄")
    elif item.source == "errors":
        st.warning("현재 파일은 errors 폴더의 오탐/미탐 검수 대상입니다.", icon="⚠️")
    else:
        st.success("현재 파일은 dataset 폴더의 일반 학습데이터입니다.", icon="✅")

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
