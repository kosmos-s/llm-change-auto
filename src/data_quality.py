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


def _issue(severity: str, code: str, image_id: str, detail: str, path: str = "") -> dict[str, str]:
    return {
        "severity": severity,
        "code": code,
        "image_id": image_id,
        "detail": detail,
        "path": path,
    }


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

    key_cols = [col for col in ["group", "split", "relative_folder", "image_id"] if col in df.columns]
    duplicate_mask = df.duplicated(subset=key_cols, keep=False)
    for _, row in df[duplicate_mask].iterrows():
        issues.append(_issue("error", "duplicate_key", str(row.get("image_id", "")), f"중복 키: {key_cols}"))

    # Same image_id across multiple splits is a leakage risk.
    split_count = df.groupby("image_id")["split"].nunique(dropna=True)
    leaked_ids = set(split_count[split_count > 1].index.astype(str))
    for image_id in sorted(leaked_ids):
        splits = sorted(df[df["image_id"].astype(str) == image_id]["split"].astype(str).unique())
        issues.append(_issue("error", "split_leakage", image_id, f"여러 split에 존재: {', '.join(splits)}"))

    for _, row in df.iterrows():
        image_id = str(row.get("image_id", ""))
        paths = {
            "combined": str(row.get("image_path", "") or ""),
            "left": str(row.get("left_image_path", "") or ""),
            "right": str(row.get("right_image_path", "") or ""),
            "json": str(row.get("json_path", "") or ""),
        }
        for name, text in paths.items():
            if not text or text.lower() == "nan" or not Path(text).exists():
                severity = "error" if name in {"combined", "json"} else "warning"
                issues.append(_issue(severity, f"missing_{name}", image_id, f"{name} 파일 없음", text))

        json_text = paths["json"]
        if json_text and json_text.lower() != "nan" and Path(json_text).exists():
            try:
                data = _read_json(Path(json_text))
            except Exception as exc:
                issues.append(_issue("error", "invalid_json", image_id, str(exc), json_text))
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
        return pd.DataFrame(columns=["severity", "code", "image_id", "detail", "path"])
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
