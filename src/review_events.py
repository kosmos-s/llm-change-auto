"""Append-only human-review event log and reviewed JSON backup helpers."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


EVENT_COLUMNS = [
    "event_at",
    "reviewer_name",
    "image_id",
    "source",
    "split",
    "relative_folder",
    "status",
    "save_path",
    "review_csv",
    "review_csv_row",
    "llm_model",
    "prompt_path",
    "batch_id",
    "run_id",
    "original_state",
    "new_state",
    "modified_keys",
    "note",
]


def _serialize(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(value)


def diff_keys(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    keys = sorted(set(before) | set(after))
    return [key for key in keys if _serialize(before.get(key)) != _serialize(after.get(key))]


def append_review_event(csv_path: Path, event: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: event.get(column, "") for column in EVENT_COLUMNS}
    row["event_at"] = row["event_at"] or datetime.now().isoformat(timespec="seconds")
    row["reviewer_name"] = str(row.get("reviewer_name") or os.getenv("REVIEWER_NAME", "") or "unknown").strip()
    row["original_state"] = _serialize(row.get("original_state", ""))
    row["new_state"] = _serialize(row.get("new_state", ""))
    row["modified_keys"] = _serialize(row.get("modified_keys", ""))
    df = pd.DataFrame([row], columns=EVENT_COLUMNS)
    df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False, encoding="utf-8-sig")


def backup_existing_reviewed_json(save_path: Path, backup_root: Path) -> Path | None:
    """Back up the previous reviewed JSON before it is overwritten."""
    if not save_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    try:
        relative = save_path.parts[-4:]
        target = backup_root / timestamp / Path(*relative)
    except Exception:
        target = backup_root / timestamp / save_path.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(save_path, target)
    return target
