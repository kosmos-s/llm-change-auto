"""Unified Streamlit entrypoint.

검수 UI, OpenAI 자동화 UI, 통계 UI를 하나의 Streamlit 서버에서 함께 사용한다.

Run:
    streamlit run app/main_app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="LLM Change Auto",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("LLM Change Auto")
st.caption("항공영상 학습데이터 검수 + OpenAI GPT 자동화 통합 UI")

st.markdown(
    """
## 사용 방법

왼쪽 사이드바의 **Pages**에서 원하는 화면을 선택하세요.

- **검수 UI**: `dataset/errors` 이미지를 보고 JSON 라벨을 수정합니다.
- **OpenAI GPT 자동화 UI**: 데이터 인덱스 생성, GPT 자동판별, 라벨 비교, 검수 대상 CSV 생성을 실행합니다.
- **통계 UI**: 생성된 CSV와 reviewed_json 저장 결과를 요약합니다.

모든 화면은 하나의 Streamlit 앱에서 동작하므로 `localhost:8501` 하나만 사용합니다.
"""
)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("검수 UI")
    st.write("이미지를 직접 보면서 라벨과 reason을 수정합니다.")
    st.page_link("pages/1_검수_UI.py", label="검수 UI 열기", icon="✅")

with col2:
    st.subheader("OpenAI GPT 자동화 UI")
    st.write("GPT 실행부터 검수 대상 CSV 생성까지 버튼으로 처리합니다.")
    st.page_link("pages/2_LLM_자동화_UI.py", label="OpenAI GPT 자동화 UI 열기", icon="🤖")

with col3:
    st.subheader("통계 UI")
    st.write("CSV 결과와 reviewed_json 저장 현황을 요약합니다.")
    st.page_link("pages/3_통계_UI.py", label="통계 UI 열기", icon="📊")

st.divider()
st.info("VS Code에서는 `app/run_app.py`를 열고 Ctrl + F5를 누르면 이 통합 UI가 실행됩니다.")
