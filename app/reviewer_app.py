"""Streamlit-based aerial image label verifier.

Run:
    streamlit run app/reviewer_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dataset_loader import SampleItem, find_combined_images
from json_io import get_label_state, load_json, save_json, update_label_json


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


@st.cache_data(show_spinner=False)
def load_items(root: str, split: str) -> list[SampleItem]:
    return find_combined_images(root, split)


def init_state() -> None:
    st.session_state.setdefault("items", [])
    st.session_state.setdefault("index", 0)
    st.session_state.setdefault("loaded_root", "")
    st.session_state.setdefault("loaded_split", "test")
    st.session_state.setdefault("view_mode", "combined")


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


def render_sidebar() -> None:
    st.sidebar.title("데이터 불러오기")
    default_root = str(Path.home() / "Desktop" / "산학과제" / "dataset_sample")
    root = st.sidebar.text_input("dataset_sample 경로", value=st.session_state.get("loaded_root") or default_root)
    split = st.sidebar.selectbox("분할 선택", ["test", "train", "val", "all"], index=0)

    if st.sidebar.button("Load Directory", use_container_width=True):
        root_path = Path(root)
        if not root_path.exists():
            st.sidebar.error(f"경로가 없습니다: {root_path}")
        else:
            st.session_state["items"] = load_items(str(root_path), split)
            st.session_state["index"] = 0
            st.session_state["loaded_root"] = str(root_path)
            st.session_state["loaded_split"] = split
            if st.session_state["items"]:
                st.sidebar.success(f"{len(st.session_state['items'])}개 파일 로드 완료")
            else:
                st.sidebar.warning("*_combined.jpg 파일을 찾지 못했습니다.")

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
        jump_value = st.number_input("Jump", min_value=1, max_value=max(total, 1), value=st.session_state["index"] + 1)
    with col4:
        if st.button("Jump", use_container_width=True):
            st.session_state["index"] = int(jump_value) - 1
            st.rerun()


def render_label_panel(item: SampleItem) -> None:
    data = load_json(item.json_path)
    state = get_label_state(data)

    st.subheader("타겟 클래스 / 세부 클래스")

    artifact = st.checkbox("Artifact", value=bool(state["Artifact"]), help=LABEL_HELP["Artifact"])
    st.markdown("**Artifact Detail**")
    arti_bu = st.checkbox("arti_bu", value=bool(state["arti_bu"]), help=LABEL_HELP["arti_bu"])
    arti_bu_t = st.checkbox("arti_bu_t", value=bool(state["arti_bu_t"]), help=LABEL_HELP["arti_bu_t"])
    arti_binil = st.checkbox("arti_binil", value=bool(state["arti_binil"]), help=LABEL_HELP["arti_binil"])
    arti_road = st.checkbox("arti_road", value=bool(state["arti_road"]), help=LABEL_HELP["arti_road"])
    arti_roa_m = st.checkbox("arti_roa_m", value=bool(state["arti_roa_m"]), help=LABEL_HELP["arti_roa_m"])
    arti_other = st.checkbox("arti_other", value=bool(state["arti_other"]), help=LABEL_HELP["arti_other"])

    st.divider()
    tree = st.checkbox("Tree", value=bool(state["Tree"]), help=LABEL_HELP["Tree"])
    forest = st.checkbox("forest", value=bool(state["forest"]), help=LABEL_HELP["forest"])
    farmland = st.checkbox("farmland", value=bool(state["farmland"]), help=LABEL_HELP["farmland"])
    water = st.checkbox("water", value=bool(state["water"]), help=LABEL_HELP["water"])

    st.divider()
    reason = st.text_area("reason", value=str(state["reason"]), height=110)
    reason_ko = st.text_area("reason (KO)", value=str(state["reason_ko"]), height=110)

    new_state = {
        "Artifact": artifact,
        "arti_bu": arti_bu,
        "arti_bu_t": arti_bu_t,
        "arti_binil": arti_binil,
        "arti_road": arti_road,
        "arti_roa_m": arti_roa_m,
        "arti_other": arti_other,
        "Tree": tree,
        "forest": forest,
        "farmland": farmland,
        "water": water,
        "reason": reason,
        "reason_ko": reason_ko,
    }

    save_mode = st.radio("저장 위치", ["원본 JSON 덮어쓰기", "reviewed_json 폴더에 저장"], horizontal=False)
    if st.button("Save Changes", type="primary", use_container_width=True):
        updated = update_label_json(data, new_state)
        if save_mode == "원본 JSON 덮어쓰기":
            save_path = item.json_path
        else:
            save_dir = PROJECT_ROOT / "outputs" / "reviewed_json" / item.split
            save_path = save_dir / item.json_path.name
        save_json(save_path, updated)
        st.success(f"저장 완료: {save_path}")


def main() -> None:
    init_state()
    render_sidebar()

    st.title("항공영상 학습데이터 검수툴")
    st.caption("dataset_sample의 *_combined.jpg와 *_combined.json을 기준으로 라벨을 확인하고 수정합니다.")

    item = current_item()
    items = st.session_state.get("items", [])

    if item is None:
        st.info("왼쪽 사이드바에서 dataset_sample 경로를 입력하고 Load Directory를 누르세요.")
        st.code(r"C:\Users\rlarj\Desktop\산학과제\dataset_sample")
        return

    total = len(items)
    st.markdown(f"**Loaded file [{st.session_state['index'] + 1}/{total}]**  `{item.image_id}`")
    st.caption(f"split={item.split} | json={item.json_path}")

    left_col, right_col = st.columns([3.2, 1.25], gap="large")

    with left_col:
        path = image_path_for_view(item, st.session_state["view_mode"])
        st.image(str(path), caption=str(path), use_container_width=True)
        render_navigation(total)

    with right_col:
        render_label_panel(item)


if __name__ == "__main__":
    main()
