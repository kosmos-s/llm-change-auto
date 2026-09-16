"""Integrity helpers that bind a production run to one frozen dataset/work plan."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from work_plan import file_sha256, logical_key_frame


PLAN_META_NAME = "work_plan_3000.meta.json"
LOCAL_PATH_COLUMNS = {"image_path", "left_image_path", "right_image_path", "json_path"}


def plan_metadata_path(work_plan_path: Path) -> Path:
    return work_plan_path.with_name(PLAN_META_NAME)


def _portable_frame(path: Path) -> pd.DataFrame:
    """Return a deterministic dataframe excluding PC-specific absolute path columns."""
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    keep = [column for column in frame.columns if column not in LOCAL_PATH_COLUMNS]
    frame = frame[keep].copy()
    if "relative_folder" in frame.columns:
        frame["relative_folder"] = (
            frame["relative_folder"].fillna(".").astype(str).str.replace("\\", "/", regex=False).str.strip("/").replace("", ".")
        )
    if "image_id" in frame.columns:
        frame["_logical_key"] = logical_key_frame(frame)
        frame = frame.sort_values("_logical_key", kind="stable").drop(columns=["_logical_key"])
    frame = frame.reset_index(drop=True)
    return frame


def portable_csv_sha256(path: Path) -> str:
    """Hash logical CSV content so identical datasets on different PCs match."""
    frame = _portable_frame(Path(path))
    if frame.empty and not Path(path).exists():
        return ""
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_plan_metadata(index_path: Path, work_plan_path: Path) -> dict[str, Any]:
    return {
        "dataset_index_path": str(index_path),
        "dataset_index_sha256": file_sha256(index_path) if index_path.exists() else "",
        "dataset_index_portable_sha256": portable_csv_sha256(index_path),
        "work_plan_path": str(work_plan_path),
        "work_plan_sha256": file_sha256(work_plan_path) if work_plan_path.exists() else "",
        "work_plan_portable_sha256": portable_csv_sha256(work_plan_path),
    }


def write_plan_metadata(index_path: Path, work_plan_path: Path) -> Path:
    meta_path = plan_metadata_path(work_plan_path)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_plan_metadata(index_path, work_plan_path)
    tmp = meta_path.with_suffix(meta_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(meta_path)
    return meta_path


def read_plan_metadata(work_plan_path: Path) -> dict[str, Any]:
    meta_path = plan_metadata_path(work_plan_path)
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def validate_plan_binding(index_path: Path, work_plan_path: Path) -> dict[str, Any]:
    """Check that current local files match the exact hashes frozen at plan creation."""
    meta = read_plan_metadata(work_plan_path)
    current_index_sha = file_sha256(index_path) if index_path.exists() else ""
    current_plan_sha = file_sha256(work_plan_path) if work_plan_path.exists() else ""
    expected_index_sha = str(meta.get("dataset_index_sha256", ""))
    expected_plan_sha = str(meta.get("work_plan_sha256", ""))

    ready = bool(
        meta
        and current_index_sha
        and current_plan_sha
        and expected_index_sha == current_index_sha
        and expected_plan_sha == current_plan_sha
    )
    reasons: list[str] = []
    if not meta:
        reasons.append("plan_metadata_missing")
    if not index_path.exists():
        reasons.append("dataset_index_missing")
    if not work_plan_path.exists():
        reasons.append("work_plan_missing")
    if expected_index_sha and current_index_sha and expected_index_sha != current_index_sha:
        reasons.append("dataset_index_changed")
    if expected_plan_sha and current_plan_sha and expected_plan_sha != current_plan_sha:
        reasons.append("work_plan_changed")

    return {
        "ready": ready,
        "reasons": reasons,
        "expected_index_sha256": expected_index_sha,
        "current_index_sha256": current_index_sha,
        "expected_work_plan_sha256": expected_plan_sha,
        "current_work_plan_sha256": current_plan_sha,
        "dataset_index_portable_sha256": portable_csv_sha256(index_path) if index_path.exists() else "",
        "work_plan_portable_sha256": portable_csv_sha256(work_plan_path) if work_plan_path.exists() else "",
        "metadata_path": str(plan_metadata_path(work_plan_path)),
    }


def run_manifest_compatible(existing: dict[str, Any], current: dict[str, Any]) -> tuple[bool, list[str]]:
    """Return whether an existing batch may be safely resumed with current settings."""
    checks = {
        "model": (existing.get("model"), current.get("model")),
        "prompt_sha256": (existing.get("prompt_sha256"), current.get("prompt_sha256")),
        "work_plan_sha256": (existing.get("work_plan_sha256"), current.get("work_plan_sha256")),
        "dataset_index_sha256": (existing.get("dataset_index_sha256"), current.get("dataset_index_sha256")),
    }
    old_settings = existing.get("settings") if isinstance(existing.get("settings"), dict) else {}
    new_settings = current.get("settings") if isinstance(current.get("settings"), dict) else {}
    for key in ["work_mode", "source", "split", "start", "limit", "selection_mode", "confidence"]:
        checks[f"settings.{key}"] = (old_settings.get(key), new_settings.get(key))

    mismatches = [name for name, (old, new) in checks.items() if str(old) != str(new)]
    return not mismatches, mismatches
