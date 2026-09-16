"""Turn data-quality findings into a safe remediation plan without mutating raw data."""

from __future__ import annotations

import pandas as pd

ACTION_MAP = {
    "split_leakage": ("blocking", "split 결정 필요", "같은 group의 train/val/test 중 하나만 남기도록 사람이 분할을 확정"),
    "duplicate_key": ("blocking", "중복 행 확인", "동일 논리 키가 중복된 원인을 확인하고 dataset_index/원본 구성을 정리"),
    "missing_combined": ("blocking", "combined 복구", "combined 이미지 누락 여부를 확인하고 원본 세트를 복구"),
    "missing_json": ("blocking", "JSON 복구", "정답 JSON 누락 여부를 확인하고 원본 세트를 복구"),
    "invalid_json": ("blocking", "JSON 수정", "JSON 문법/인코딩 오류를 수정"),
    "artifact_logic": ("review", "라벨 재검수", "Artifact=x인데 세부 인공물 라벨이 활성인 항목을 사람 검수 대상으로 전달"),
    "missing_left": ("review", "left 확인", "left 이미지 누락 여부 확인"),
    "missing_right": ("review", "right 확인", "right 이미지 누락 여부 확인"),
    "orphan_file_set": ("review", "파일 세트 확인", "combined 없이 남은 관련 파일이 실제 고아 파일인지 확인"),
    "cross_group_split_overlap": ("info", "교차 group 확인", "dataset/errors 간 중복은 별도 컬렉션일 수 있으므로 기록만 유지"),
}


def build_quality_action_plan(report: pd.DataFrame) -> pd.DataFrame:
    if report is None or report.empty:
        return pd.DataFrame(columns=["priority", "severity", "code", "group", "image_id", "action", "recommendation", "path"])

    rows = []
    for _, row in report.iterrows():
        code = str(row.get("code", ""))
        priority, action, recommendation = ACTION_MAP.get(
            code,
            ("review", "수동 확인", "원본 데이터와 품질검사 상세 내용을 사람이 확인"),
        )
        rows.append(
            {
                "priority": priority,
                "severity": str(row.get("severity", "")),
                "code": code,
                "group": str(row.get("group", "")),
                "image_id": str(row.get("image_id", "")),
                "action": action,
                "recommendation": recommendation,
                "detail": str(row.get("detail", "")),
                "path": str(row.get("path", "")),
            }
        )

    result = pd.DataFrame(rows)
    order = {"blocking": 0, "review": 1, "info": 2}
    result["_order"] = result["priority"].map(order).fillna(9)
    return result.sort_values(["_order", "code", "image_id"]).drop(columns=["_order"]).reset_index(drop=True)
