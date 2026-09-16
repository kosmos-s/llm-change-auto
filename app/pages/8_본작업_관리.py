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
from production_readiness import preflight_quality_summary
from project_paths import dataset_root_default, ensure_output_dirs, openai_target_total
from team_review_exchange import export_review_package, merge_review_package, preview_review_package
from work_plan import DEFAULT_SPLIT_COUNTS, build_work_plan, file_sha256, load_work_plan

load_dotenv(PROJECT_ROOT / ".env")
OUTPUTS_DIR = ensure_output_dirs(PROJECT_ROOT)
INDEX = OUTPUTS_DIR / "dataset_index.csv"
PLAN = OUTPUTS_DIR / "work_plan_3000.csv"
QUALITY = OUTPUTS_DIR / "quality" / "production_preflight_quality.csv"

st.title("8. 본작업 관리")
st.caption("본작업 전 품질검사 → 3,000건 작업계획 고정 → Final coverage 확인 → 팀원 검수 결과 교환")

st.markdown("## 1) 본작업 전 품질검사")
st.info("work_plan_3000.csv는 현재 dataset_index가 무결성 Error=0일 때만 생성할 수 있습니다. Error를 수정했다면 dataset_index를 다시 생성하고 다시 검사하세요.")
preflight = None
if INDEX.exists():
    try:
        preflight = preflight_quality_summary(INDEX, dataset_root_default(PROJECT_ROOT))
        QUALITY.parent.mkdir(parents=True, exist_ok=True)
        preflight["report"].to_csv(QUALITY, index=False, encoding="utf-8-sig")
        q1, q2, q3 = st.columns(3)
        q1.metric("Preflight Error", preflight["errors"])
        q2.metric("Warning", preflight["warnings"])
        q3.metric("Work plan 생성", "가능" if preflight["ready"] else "차단")
        if preflight["errors"]:
            st.error("품질 Error가 남아 있어 본작업 계획을 고정할 수 없습니다.")
            if not preflight["report"].empty:
                st.dataframe(preflight["report"].head(300), use_container_width=True, hide_index=True)
        elif preflight["warnings"]:
            st.warning("Error는 0입니다. Warning을 확인한 뒤 작업계획을 고정할 수 있습니다.")
        else:
            st.success("본작업 전 품질검사 통과: Error 0")
    except Exception as exc:
        st.error(f"본작업 전 품질검사 실패: {exc}")
else:
    st.warning("dataset_index.csv가 없습니다. 1. OpenAI 자동판정에서 먼저 생성하세요.")

st.divider()
st.markdown("## 2) 3,000건 작업계획 고정")
st.info("품질검사를 통과한 뒤 한 번 생성한 work_plan_3000.csv는 3,000건이 끝날 때까지 다시 만들지 마세요.")
if PLAN.exists():
    plan = load_work_plan(PLAN)
    c1, c2 = st.columns(2)
    c1.metric("고정 샘플", len(plan))
    c2.metric("work plan SHA256", file_sha256(PLAN)[:16] + "…")
    st.dataframe(plan.groupby(["group", "split"], dropna=False).size().reset_index(name="count"), use_container_width=True, hide_index=True)
else:
    st.warning("work_plan_3000.csv가 아직 없습니다.")
    plan_allowed = bool(INDEX.exists() and preflight is not None and preflight.get("ready"))
    if st.button("errors/train·val·test 각 1,000건 작업계획 생성", type="primary", disabled=not plan_allowed, use_container_width=True):
        plan = build_work_plan(INDEX, PLAN, source="errors", split_counts=DEFAULT_SPLIT_COUNTS)
        st.success(f"고정 완료: {len(plan):,}건 → {PLAN}")
        st.rerun()
    if INDEX.exists() and not plan_allowed:
        st.caption("품질 Error를 0으로 만든 뒤 버튼이 활성화됩니다.")

st.divider()
st.markdown("## 3) Final 준비상태")
gate = final_gate_summary(OUTPUTS_DIR, openai_target_total())
c1, c2, c3, c4 = st.columns(4)
c1.metric("OpenAI 성공", f"{gate['success_count']:,}/{gate['target_total']:,}")
c2.metric("Compare coverage", f"{gate['compare_count']:,}/{gate['target_total']:,}")
c3.metric("Review 판정 coverage", f"{gate['review_decision_count']:,}/{gate['target_total']:,}")
c4.metric("Final Gate", "READY" if gate["ready"] else "BLOCK")
c5, c6, c7 = st.columns(3)
c5.metric("미해결 API 오류", gate["failed_count"])
c6.metric("미검수/보류", gate["pending_review_count"])
c7.metric("Coverage 누락", gate["compare_missing"] + gate["review_decision_missing"])

if gate["ready"]:
    st.success("OpenAI 성공, Compare 100%, Review 판정 100%, API 오류 0, 사람 검수 완료 조건을 모두 만족합니다.")
else:
    reasons = []
    if not gate["work_plan_present"]:
        reasons.append("work plan 없음")
    if gate["missing_success"]:
        reasons.append(f"OpenAI 성공 {gate['missing_success']}건 부족")
    if gate["failed_count"]:
        reasons.append(f"API 오류 {gate['failed_count']}건")
    if gate["compare_missing"]:
        reasons.append(f"Compare {gate['compare_missing']}건 미처리")
    if gate["review_decision_missing"]:
        reasons.append(f"Review 판정 {gate['review_decision_missing']}건 미처리")
    if gate["pending_review_count"]:
        reasons.append(f"사람 검수 {gate['pending_review_count']}건 미완료")
    st.warning("Final BLOCK: " + (" / ".join(reasons) if reasons else "미완료 조건이 있습니다."))
    pending = unresolved_review_items(
        OUTPUTS_DIR / "review_lists",
        OUTPUTS_DIR / "reviewed_json",
        OUTPUTS_DIR / "review_events" / "review_events.csv",
        PLAN if PLAN.exists() else None,
    )
    if not pending.empty:
        st.dataframe(pending[[c for c in ["group", "split", "relative_folder", "image_id", "review_state", "_review_list"] if c in pending.columns]].head(300), use_container_width=True, hide_index=True)

st.divider()
st.markdown("## 4) 팀원 검수 결과 교환")
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
