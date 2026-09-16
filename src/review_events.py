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
    "event_at", "reviewer_name", "image_id", "source", "split", "relative_folder",
    "status", "save_path", "review_csv", "review_csv_row", "llm_model", "prompt_path",
    "batch_id", "run_id", "original_state", "new_state", "modified_keys", "note",
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


def _ensure_event_schema(csv_path: Path) -> None:
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return
    try:
        existing = pd.read_csv(csv_path)
    except Exception:
        return
    if list(existing.columns) == EVENT_COLUMNS:
        return
    for column in EVENT_COLUMNS:
        if column not in existing.columns:
            existing[column] = ""
    existing = existing[EVENT_COLUMNS]
    temp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    existing.to_csv(temp, index=False, encoding="utf-8-sig")
    os.replace(temp, csv_path)


def append_review_event(csv_path: Path, event: dict[str, Any]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_event_schema(csv_path)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    row = {column: event.get(column, "") for column in EVENT_COLUMNS}
    row["event_at"] = row["event_at"] or datetime.now().isoformat(timespec="seconds")
    row["reviewer_name"] = str(row.get("reviewer_name") or os.getenv("REVIEWER_NAME", "") or "unknown").strip()
    row["original_state"] = _serialize(row.get("original_state", ""))
    row["new_state"] = _serialize(row.get("new_state", ""))
    row["modified_keys"] = _serialize(row.get("modified_keys", ""))
    pd.DataFrame([row], columns=EVENT_COLUMNS).to_csv(
        csv_path, mode="a", header=needs_header, index=False, encoding="utf-8-sig"
    )


def _reviewed_relative_path(save_path: Path) -> Path:
    """Preserve every path component below `reviewed_json` in backups."""
    parts = list(save_path.parts)
    lowered = [part.lower() for part in parts]
    indexes = [index for index, part in enumerate(lowered) if part == "reviewed_json"]
    if indexes and indexes[-1] + 1 < len(parts):
        return Path(*parts[indexes[-1] + 1 :])
    return Path(save_path.name)


def backup_existing_reviewed_json(save_path: Path, backup_root: Path) -> Path | None:
    """Back up the previous reviewed JSON before it is overwritten."""
    if not save_path.exists():
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_root / timestamp / _reviewed_relative_path(save_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(save_path, target)
    return target
