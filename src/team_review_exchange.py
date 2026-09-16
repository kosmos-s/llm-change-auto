"""Export and merge reviewed_json packages between teammate PCs."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_review_package(outputs_dir: Path, reviewer_name: str) -> Path:
    reviewed_root = outputs_dir / "reviewed_json"
    events = outputs_dir / "review_events" / "review_events.csv"
    packages = outputs_dir / "review_packages"
    packages.mkdir(parents=True, exist_ok=True)
    safe_reviewer = "_".join((reviewer_name.strip() or "unknown").split())
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = packages / f"reviews_{safe_reviewer}_{stamp}.zip"

    files: list[dict[str, str]] = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if reviewed_root.exists():
            for path in sorted(reviewed_root.rglob("*.json")):
                rel = path.relative_to(outputs_dir)
                archive.write(path, rel.as_posix())
                files.append({"path": rel.as_posix(), "sha256": _sha256(path)})
        if events.exists():
            archive.write(events, events.relative_to(outputs_dir).as_posix())
        manifest = {
            "reviewer_name": reviewer_name.strip() or "unknown",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "file_count": len(files),
            "files": files,
        }
        archive.writestr("review_package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return target


def preview_review_package(zip_path: Path, outputs_dir: Path) -> dict[str, object]:
    incoming: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        manifest = json.loads(archive.read("review_package_manifest.json").decode("utf-8"))
        for item in manifest.get("files", []):
            rel = str(item.get("path", ""))
            incoming_sha = str(item.get("sha256", ""))
            target = outputs_dir / Path(rel)
            state = "new"
            local_sha = ""
            if target.exists():
                local_sha = _sha256(target)
                state = "same" if local_sha == incoming_sha else "conflict"
            row = {"path": rel, "state": state, "incoming_sha256": incoming_sha, "local_sha256": local_sha}
            incoming.append(row)
            if state == "conflict":
                conflicts.append(row)
    return {"manifest": manifest, "items": incoming, "conflicts": conflicts}


def merge_review_package(zip_path: Path, outputs_dir: Path, *, conflict_policy: str = "keep_local") -> dict[str, int]:
    if conflict_policy not in {"keep_local", "use_incoming"}:
        raise ValueError("conflict_policy는 keep_local 또는 use_incoming 이어야 합니다.")
    stats = {"new": 0, "same": 0, "conflict": 0, "written": 0}
    with zipfile.ZipFile(zip_path, "r") as archive:
        manifest = json.loads(archive.read("review_package_manifest.json").decode("utf-8"))
        for item in manifest.get("files", []):
            rel = str(item.get("path", ""))
            if not rel.startswith("reviewed_json/") and not rel.startswith("outputs/reviewed_json/"):
                continue
            normalized = rel[len("outputs/") :] if rel.startswith("outputs/") else rel
            target = outputs_dir / Path(normalized)
            incoming_sha = str(item.get("sha256", ""))
            if target.exists():
                local_sha = _sha256(target)
                if local_sha == incoming_sha:
                    stats["same"] += 1
                    continue
                stats["conflict"] += 1
                if conflict_policy == "keep_local":
                    continue
                backup = outputs_dir / "backups" / "reviewed_json_merge" / datetime.now().strftime("%Y%m%d_%H%M%S_%f") / target.relative_to(outputs_dir)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            else:
                stats["new"] += 1
            member = rel
            if member not in archive.namelist() and normalized in archive.namelist():
                member = normalized
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            stats["written"] += 1
    return stats
