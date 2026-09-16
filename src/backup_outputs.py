from __future__ import annotations

import os
import zipfile
from datetime import datetime
from pathlib import Path


DEFAULT_RELATIVE_PATHS = [
    "dataset_index.csv",
    "work_plan_3000.csv",
    "work_plan_3000.meta.json",
    "llm_results",
    "run_manifests",
    "compare_results",
    "review_lists",
    "reviewed_json",
    "review_events",
    "review_history",
    "quality",
    "model_eval",
]


def create_outputs_backup(outputs_dir: Path, backup_dir: Path, keep_count: int = 10) -> Path:
    outputs_dir = Path(outputs_dir)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"project_outputs_{datetime.now():%Y%m%d_%H%M%S}.zip"

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in DEFAULT_RELATIVE_PATHS:
            source = outputs_dir / relative
            if not source.exists():
                continue
            if source.is_file():
                archive.write(source, source.relative_to(outputs_dir.parent))
                continue
            for path in sorted(source.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(outputs_dir.parent))

    backups = sorted(backup_dir.glob("project_outputs_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[max(int(keep_count), 1):]:
        try:
            old.unlink()
        except OSError:
            pass
    return target


def backup_keep_count(default: int = 10) -> int:
    try:
        return max(1, int(os.getenv("BACKUP_KEEP_COUNT", str(default))))
    except Exception:
        return default
