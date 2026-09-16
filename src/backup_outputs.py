"""Create timestamped ZIP backups of important production outputs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import zipfile


BACKUP_TARGETS = [
    "dataset_index.csv",
    "work_plan_3000.csv",
    "llm_results",
    "compare_results",
    "review_lists",
    "reviewed_json",
    "review_events",
    "review_history",
    "quality",
    "clean_datasets",
    "model_eval",
    "run_manifests",
]


def create_outputs_backup(outputs_root: Path, keep_count: int = 10) -> dict[str, object]:
    outputs_root = Path(outputs_root)
    outputs_root.mkdir(parents=True, exist_ok=True)
    backup_dir = outputs_root / "backups" / "project_outputs"
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"outputs_backup_{stamp}.zip"
    file_count = 0
    total_bytes = 0

    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for target_name in BACKUP_TARGETS:
            target = outputs_root / target_name
            if target.is_file():
                archive.write(target, target.relative_to(outputs_root))
                file_count += 1
                total_bytes += target.stat().st_size
            elif target.is_dir():
                for path in sorted(target.rglob("*")):
                    if not path.is_file():
                        continue
                    if backup_dir in path.parents:
                        continue
                    archive.write(path, path.relative_to(outputs_root))
                    file_count += 1
                    total_bytes += path.stat().st_size

    backups = sorted(backup_dir.glob("outputs_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in backups[max(keep_count, 1):]:
        try:
            old.unlink()
        except OSError:
            pass

    return {
        "path": str(backup_path),
        "file_count": file_count,
        "source_bytes": total_bytes,
        "zip_bytes": backup_path.stat().st_size if backup_path.exists() else 0,
    }
