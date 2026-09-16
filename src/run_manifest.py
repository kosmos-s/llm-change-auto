"""Build reproducibility manifests for production OpenAI batches."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from production_integrity import run_manifest_compatible
from work_plan import file_sha256


def git_commit_sha(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def build_manifest(
    *,
    project_root: Path,
    batch_id: str,
    model: str,
    prompt_path: Path,
    index_path: Path,
    work_plan_path: Path | None,
    settings: dict[str, Any],
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "git_commit": git_commit_sha(project_root),
        "batch_id": batch_id,
        "model": model,
        "prompt_path": str(prompt_path),
        "prompt_sha256": file_sha256(prompt_path) if prompt_path.exists() else "",
        "dataset_index_path": str(index_path),
        "dataset_index_sha256": file_sha256(index_path) if index_path.exists() else "",
        "work_plan_path": str(work_plan_path or ""),
        "work_plan_sha256": file_sha256(work_plan_path) if work_plan_path and work_plan_path.exists() else "",
        "settings": settings,
    }
    return manifest


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def validate_resume_manifest(path: Path, current_manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate that a batch resume uses the same frozen execution configuration."""
    existing = read_manifest(path)
    if not existing:
        return False, ["existing_manifest_missing_or_invalid"]
    return run_manifest_compatible(existing, current_manifest)


def _batch_artifact_paths(manifest_path: Path, batch_id: str) -> list[Path]:
    outputs_dir = manifest_path.parent.parent
    return [
        outputs_dir / "llm_results" / f"{batch_id}.csv",
        outputs_dir / "llm_results" / f"{batch_id}.checkpoint.json",
        outputs_dir / "compare_results" / f"{batch_id}_compare.csv",
        outputs_dir / "review_lists" / f"{batch_id}_review.csv",
        manifest_path,
    ]


def archive_existing_batch(manifest_path: Path, batch_id: str) -> Path | None:
    """Move existing same-prefix artifacts aside before a deliberate fresh overwrite.

    The Streamlit UI calls `write_manifest` only for a new batch or an explicitly
    confirmed non-resume overwrite. Archiving first prevents an old result CSV from
    being paired with a newly written manifest if the fresh run fails before its first
    output row is saved.
    """
    existing = [path for path in _batch_artifact_paths(manifest_path, batch_id) if path.exists()]
    if not existing:
        return None

    outputs_dir = manifest_path.parent.parent
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_root = outputs_dir / "backups" / "overwritten_batches" / stamp / batch_id
    backup_root.mkdir(parents=True, exist_ok=True)

    for source in existing:
        try:
            relative = source.relative_to(outputs_dir)
        except ValueError:
            relative = Path(source.name)
        target = backup_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    return backup_root


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    batch_id = str(manifest.get("batch_id", "") or path.stem).strip() or path.stem
    archive_existing_batch(path, batch_id)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
