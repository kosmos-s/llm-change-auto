"""Integrity helpers that bind a production run to one frozen dataset/work plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from work_plan import file_sha256


PLAN_META_NAME = "work_plan_3000.meta.json"


def plan_metadata_path(work_plan_path: Path) -> Path:
    return work_plan_path.with_name(PLAN_META_NAME)


def build_plan_metadata(index_path: Path, work_plan_path: Path) -> dict[str, Any]:
    return {
        "dataset_index_path": str(index_path),
        "dataset_index_sha256": file_sha256(index_path) if index_path.exists() else "",
        "work_plan_path": str(work_plan_path),
        "work_plan_sha256": file_sha256(work_plan_path) if work_plan_path.exists() else "",
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
    """Check that the current index/work-plan files match the hashes frozen at plan creation."""
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
