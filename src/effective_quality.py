"""Quality checks for the effective JSON labels used by a clean snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from export_clean_dataset import reviewed_json_path_for_row

DETAIL_KEYS = ["arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other"]


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"o", "1", "true", "yes", "y"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        data = json.loads(path.read_text(encoding="cp949"))
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data


def validate_effective_labels(index_csv: Path, reviewed_root: Path) -> pd.DataFrame:
    """Validate the exact reviewed/original JSON that a snapshot would select."""
    if not index_csv.exists():
        raise FileNotFoundError(f"dataset_index.csv를 찾을 수 없습니다: {index_csv}")
    index = pd.read_csv(index_csv)
    issues: list[dict[str, str]] = []

    for _, row in index.iterrows():
        image_id = str(row.get("image_id", "")).strip()
        source = str(row.get("group", "")).strip()
        split = str(row.get("split", "")).strip()
        original = Path(str(row.get("json_path", "")).strip())
        reviewed = reviewed_json_path_for_row(row, reviewed_root)
        selected = reviewed if reviewed.exists() else original
        label_source = "reviewed" if reviewed.exists() else "original"

        if not selected.exists():
            issues.append({
                "severity": "error", "code": "effective_json_missing", "group": source,
                "split": split, "image_id": image_id, "label_source": label_source,
                "path": str(selected), "detail": "최종 선택 JSON 파일 없음",
            })
            continue
        try:
            data = _read_json(selected)
        except Exception as exc:
            issues.append({
                "severity": "error", "code": "effective_json_invalid", "group": source,
                "split": split, "image_id": image_id, "label_source": label_source,
                "path": str(selected), "detail": str(exc),
            })
            continue

        artifact = _truthy(data.get("Artifact", "x"))
        detail = data.get("artifact_detail", {}) or {}
        if not isinstance(detail, dict):
            issues.append({
                "severity": "error", "code": "effective_artifact_detail_invalid", "group": source,
                "split": split, "image_id": image_id, "label_source": label_source,
                "path": str(selected), "detail": "artifact_detail must be an object",
            })
            continue
        active = [key for key in DETAIL_KEYS if _truthy(detail.get(key, "x"))]
        if active and not artifact:
            issues.append({
                "severity": "error", "code": "effective_artifact_logic", "group": source,
                "split": split, "image_id": image_id, "label_source": label_source,
                "path": str(selected), "detail": "Artifact=x인데 세부 라벨 활성: " + ", ".join(active),
            })

    columns = ["severity", "code", "group", "split", "image_id", "label_source", "path", "detail"]
    return pd.DataFrame(issues, columns=columns)
