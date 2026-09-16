"""Portable project path and environment helpers."""

from __future__ import annotations

import os
from pathlib import Path


def _env_text(name: str) -> str:
    value = str(os.getenv(name, "") or "").strip()
    if value.lower() in {"", "none", "null", "your_dataset_path_here"}:
        return ""
    return value


def dataset_root_default(project_root: Path | None = None) -> Path:
    """Return DATASET_ROOT when configured, otherwise the team default path."""
    configured = _env_text("DATASET_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Desktop" / "산학과제" / "dataset_sample"


def outputs_root(project_root: Path) -> Path:
    """Runtime outputs stay under the repository so every page uses one location."""
    return project_root / "outputs"


def openai_target_total(default: int = 3000) -> int:
    try:
        return max(int(float(_env_text("OPENAI_TARGET_TOTAL") or default)), 1)
    except Exception:
        return default


def default_cost_limit_usd(default: float = 5.0) -> float:
    try:
        return max(float(_env_text("OPENAI_COST_LIMIT_USD") or default), 0.0)
    except Exception:
        return default


def backup_keep_count(default: int = 10) -> int:
    try:
        return max(int(float(_env_text("BACKUP_KEEP_COUNT") or default)), 1)
    except Exception:
        return default


def ensure_output_dirs(project_root: Path) -> Path:
    root = outputs_root(project_root)
    for relative in [
        "llm_results",
        "compare_results",
        "review_lists",
        "reviewed_json",
        "review_events",
        "review_history",
        "backups/reviewed_json",
        "backups/project_outputs",
        "quality",
        "clean_datasets",
        "model_eval",
    ]:
        (root / relative).mkdir(parents=True, exist_ok=True)
    return root
