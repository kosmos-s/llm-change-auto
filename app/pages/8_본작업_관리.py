"""Production work-plan, final-gate, and team review exchange management."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from production_gate import final_gate_summary, unresolved_review_items
from project_paths import ensure_output_dirs, openai_target_total
from team_review_exchange import export_review_package, merge_review_package, preview_review_package
from work_plan import DEFAULT_SPLIT_COUNTS, build_work_plan, file_sha256, load_work_plan

load_dotenv(PROJECT_ROOT / ".env")
OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)
INDEX = OUTPUTS_DIR / "dataset_index.csv"
PLAN = OUTPUTS_DIR / "work_plan_3000.csv"

st.title("8. 본작업 관리")
st.caption("3,000건 작업계획 고정, Final 준비상태, 팀원 검수 결과 교환을 관리합니다.")

st.markdown("## 1) 3,000건 작업계획 고정")
st.info("본작업 시작 전에 한 번 생성한 work_plan_3000.csv는 3,000건이 끝날 때까지 다시 만들지 않는 것을 권장합니다.")
if PLAN.exists():
    plan = load_work_plan(PLAN)
    c1, c2 = st.columns(2)
    c1.metric("고정 샘플", len(plan))
    c2.metric("work plan SHA256", file_sha256(PLAN)[:16] + "…")
    st.dataframe(plan.groupby(["group", "split"], dropna=False).size().reset_index(name="count"), use_container_width=True, hide_index=True)
else:
    st.warning("work_plan_3000.csv가 아직 없습니다.")
    if st.button("errors/train·val·test 각 1,000건 작업계획 생성", type="primary", disabled=not INDEX.exists(), use_container_width=True):
        plan = build_work_plan(INDEX, PLAN, source="errors", split_counts=DEFAULT_SPLIT_COUNTS)
        st.success(f"고정 완료: {len(plan):,}건 → {PLAN}")
        st.rerun()

st.divider()
st.markdown("## 2) Final 준비상태")
gate = final_gate_summary(OUTPUTS_DIR, openai_target_total())
c1, c2, c3, c4 = st.columns(4)
c1.metric("OpenAI 성공", f"{gate['success_count']:,}/{gate['target_total']:,}")
c2.metric("미해결 API 오류", gate["failed_count"])
c3.metric("미검수/보류", gate["pending_review_count"])
c4.metric("Final Gate", "READY" if gate["ready"] else "BLOCK")
if gate["ready"]:
    st.success("OpenAI 성공 목표, API 오류 0, 검수 후보 처리 완료 조건을 만족합니다.")
else:
    st.warning("아직 Final Snapshot 조건을 만족하지 않습니다.")
    pending = unresolved_review_items(OUTPUTS_DIR / "review_lists", OUTPUTS_DIR / "reviewed_json", OUTPUTS_DIR / "review_events" / "review_events.csv")
    if not pending.empty:
        st.dataframe(pending[[c for c in ["group", "split", "relative_folder", "image_id", "review_state", "_review_list"] if c in pending.columns]].head(300), use_container_width=True, hide_index=True)

st.divider()
st.markdown("## 3) 팀원 검수 결과 교환")
reviewer = os.getenv("REVIEWER_NAME", "").strip()
reviewer_name = st.text_input("내 검수자 이름", value=reviewer, placeholder="예: 김건보")
if st.button("내 검수 결과 ZIP 만들기", use_container_width=True):
    package = export_review_package(OUTPUTS_DIR, reviewer_name)
    st.success(f"생성 완료: {package}")

uploaded = st.file_uploader("팀원이 보낸 review package ZIP", type=["zip"])
if uploaded is not None:
    temp = OUTPUTS_DIR / "review_packages" / ("incoming_" + Path(uploaded.name).name)
    temp.parent.mkdir(parents=True, exist_ok=True)
    temp.write_bytes(uploaded.getvalue())
    try:
        preview = preview_review_package(temp, OUTPUTS_DIR)
        st.write(f"보낸 사람: **{preview['manifest'].get('reviewer_name', 'unknown')}**")
        items = pd.DataFrame(preview["items"])
        if not items.empty:
            st.dataframe(items, use_container_width=True, hide_index=True)
        conflicts = preview["conflicts"]
        if conflicts:
            st.error(f"충돌 {len(conflicts)}건: 같은 reviewed_json에 서로 다른 내용이 있습니다.")
            policy = st.radio("충돌 처리", ["keep_local", "use_incoming"], format_func=lambda x: "내 PC 결과 유지" if x == "keep_local" else "들어온 결과 사용")
        else:
            policy = "keep_local"
        if st.button("검수 결과 병합", type="primary", use_container_width=True):
            result = merge_review_package(temp, OUTPUTS_DIR, conflict_policy=policy)
            st.success(f"병합 완료: 신규 {result['new']} / 동일 {result['same']} / 충돌 {result['conflict']} / 기록 {result['written']}")
    except Exception as exc:
        st.error(str(exc))

st.caption("병합 후 3. 검수 이력에서 `검수 이력 갱신`을 다시 실행하세요.")
