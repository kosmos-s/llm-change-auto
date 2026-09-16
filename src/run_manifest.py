"""Build reproducibility manifests for production OpenAI batches."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

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


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return path
