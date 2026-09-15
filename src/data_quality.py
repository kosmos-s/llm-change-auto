"""Dataset integrity checks used before large runs and clean exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


DETAIL_KEYS = ["arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other"]
ALL_LABEL_KEYS = ["arti", *DETAIL_KEYS, "tree", "fore", "farm", "water"]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(path.read_text(encoding="cp949"))


def _issue(
    severity: str,
    code: str,
    image_id: str,
    detail: str,
    path: str = "",
    group: str = "",
) -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "group": group,
        "image_id": image_id,
        "detail": detail,
        "path": path,
    }


def _clean_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def validate_index(index_csv: Path, dataset_root: Path | None = None) -> pd.DataFrame:
    if not index_csv.exists():
        raise FileNotFoundError(f"dataset_index.csv를 찾을 수 없습니다: {index_csv}")

    df = pd.read_csv(index_csv)
    issues: list[dict[str, str]] = []

    required = ["image_id", "group", "split", "image_path", "json_path"]
    for column in required:
        if column not in df.columns:
            issues.append(_issue("error", "missing_column", "", f"필수 컬럼 없음: {column}"))
    if issues:
        return pd.DataFrame(issues)

    normalized = df.copy()
    for column in ["image_id", "group", "split", "relative_folder"]:
        if column in normalized.columns:
            normalized[column] = normalized[column].map(_clean_text)

    key_cols = [col for col in ["group", "split", "relative_folder", "image_id"] if col in normalized.columns]
    duplicate_mask = normalized.duplicated(subset=key_cols, keep=False)
    for _, row in normalized[duplicate_mask].iterrows():
        issues.append(
            _issue(
                "error",
                "duplicate_key",
                _clean_text(row.get("image_id", "")),
                f"중복 키: {key_cols}",
                group=_clean_text(row.get("group", "")),
            )
        )

    # Split leakage is only a blocking error when the same image_id appears in
    # multiple splits inside the same logical group (dataset or errors).
    # The same image_id may legitimately appear once in dataset and once in
    # errors because errors is a separate review/error collection.  Such
    # cross-group split overlap is still surfaced as a warning for visibility.
    for image_id, image_rows in normalized.groupby("image_id", dropna=False):
        image_id = _clean_text(image_id)
        if not image_id:
            continue

        has_within_group_leakage = False
        group_split_map: dict[str, list[str]] = {}

        for group_value, group_rows in image_rows.groupby("group", dropna=False):
            group_name = _clean_text(group_value)
            splits = sorted({_clean_text(value) for value in group_rows["split"] if _clean_text(value)})
            group_split_map[group_name] = splits
            if len(splits) > 1:
                has_within_group_leakage = True
                issues.append(
                    _issue(
                        "error",
                        "split_leakage",
                        image_id,
                        f"같은 group 안에서 여러 split에 존재: {', '.join(splits)}",
                        group=group_name,
                    )
                )

        groups = sorted(group for group in group_split_map if group)
        all_splits = sorted({split for splits in group_split_map.values() for split in splits})
        if len(groups) > 1 and len(all_splits) > 1 and not has_within_group_leakage:
            mapping = "; ".join(
                f"{group}={','.join(group_split_map[group]) or '-'}"
                for group in groups
            )
            issues.append(
                _issue(
                    "warning",
                    "cross_group_split_overlap",
                    image_id,
                    f"서로 다른 group에서 split이 다름: {mapping}",
                    group=" / ".join(groups),
                )
            )

    for _, row in normalized.iterrows():
        image_id = _clean_text(row.get("image_id", ""))
        group_name = _clean_text(row.get("group", ""))
        paths = {
            "combined": _clean_text(row.get("image_path", "")),
            "left": _clean_text(row.get("left_image_path", "")),
            "right": _clean_text(row.get("right_image_path", "")),
            "json": _clean_text(row.get("json_path", "")),
        }
        for name, text in paths.items():
            if not text or not Path(text).exists():
                severity = "error" if name in {"combined", "json"} else "warning"
                issues.append(
                    _issue(
                        severity,
                        f"missing_{name}",
                        image_id,
                        f"{name} 파일 없음",
                        text,
                        group=group_name,
                    )
                )

        json_text = paths["json"]
        if json_text and Path(json_text).exists():
            try:
                data = _read_json(Path(json_text))
            except Exception as exc:
                issues.append(
                    _issue("error", "invalid_json", image_id, str(exc), json_text, group=group_name)
                )
                continue

            artifact = str(data.get("Artifact", "x")).strip().lower() in {"o", "1", "true", "yes", "y"}
            detail = data.get("artifact_detail", {}) or {}
            active_details = [
                key
                for key in DETAIL_KEYS
                if str(detail.get(key, "x")).strip().lower() in {"o", "1", "true", "yes", "y"}
            ]
            if active_details and not artifact:
                issues.append(
                    _issue(
                        "warning",
                        "artifact_logic",
                        image_id,
                        f"Artifact=x인데 세부 라벨 활성: {', '.join(active_details)}",
                        json_text,
                        group=group_name,
                    )
                )

    # Files not represented by complete 4-file sets.
    if dataset_root is not None and dataset_root.exists():
        combined_stems = {path.stem.replace("_combined", "") for path in dataset_root.rglob("*_combined.jpg")}
        left_stems = {path.stem.replace("_left", "") for path in dataset_root.rglob("*_left.jpg")}
        right_stems = {path.stem.replace("_right", "") for path in dataset_root.rglob("*_right.jpg")}
        json_stems = {path.stem.replace("_combined", "") for path in dataset_root.rglob("*_combined.json")}
        orphan_ids = (left_stems | right_stems | json_stems) - combined_stems
        for image_id in sorted(orphan_ids):
            issues.append(_issue("warning", "orphan_file_set", image_id, "combined.jpg 없이 관련 파일이 존재"))

    if not issues:
        return pd.DataFrame(columns=["severity", "code", "group", "image_id", "detail", "path"])
    return pd.DataFrame(issues)


def summarize_quality(report: pd.DataFrame) -> dict[str, int]:
    if report.empty:
        return {"errors": 0, "warnings": 0, "total": 0}
    severity = report["severity"].fillna("").astype(str).str.lower()
    return {
        "errors": int((severity == "error").sum()),
        "warnings": int((severity == "warning").sum()),
        "total": len(report),
    }
