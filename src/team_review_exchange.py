"""Export and merge reviewed_json packages between teammate PCs."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from production_integrity import validate_plan_binding
from work_plan import file_sha256


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_review_path(value: str) -> Path:
    text = value.replace("\\", "/")
    if text.startswith("outputs/"):
        text = text[len("outputs/"):]
    path = Path(text)
    if not path.parts or path.parts[0] != "reviewed_json" or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"허용되지 않은 package 경로: {value}")
    return path


def _production_fingerprint(outputs_dir: Path) -> dict[str, str]:
    index_path = outputs_dir / "dataset_index.csv"
    plan_path = outputs_dir / "work_plan_3000.csv"
    binding = validate_plan_binding(index_path, plan_path)
    if not binding["ready"]:
        raise ValueError("현재 dataset_index/work plan 고정 상태가 유효하지 않습니다: " + ", ".join(binding["reasons"]))
    return {
        "dataset_index_sha256": file_sha256(index_path),
        "work_plan_sha256": file_sha256(plan_path),
    }


def export_review_package(outputs_dir: Path, reviewer_name: str) -> Path:
    fingerprint = _production_fingerprint(outputs_dir)
    reviewed_root = outputs_dir / "reviewed_json"
    events = outputs_dir / "review_events" / "review_events.csv"
    packages = outputs_dir / "review_packages"
    packages.mkdir(parents=True, exist_ok=True)
    safe = "_".join((reviewer_name.strip() or "unknown").split())
    target = packages / f"reviews_{safe}_{datetime.now():%Y%m%d_%H%M%S}.zip"
    files: list[dict[str, str]] = []

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if reviewed_root.exists():
            for path in sorted(reviewed_root.rglob("*.json")):
                rel = path.relative_to(outputs_dir).as_posix()
                archive.write(path, rel)
                files.append({"path": rel, "sha256": _sha256(path)})
        if events.exists():
            archive.write(events, "review_events/review_events.csv")
        archive.writestr(
            "review_package_manifest.json",
            json.dumps(
                {
                    "schema_version": 2,
                    "reviewer_name": reviewer_name.strip() or "unknown",
                    "created_at": datetime.now().isoformat(timespec="seconds"),
                    "file_count": len(files),
                    "files": files,
                    **fingerprint,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    return target


def _compatibility(manifest: dict[str, object], outputs_dir: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        fingerprint = _production_fingerprint(outputs_dir)
    except Exception as exc:
        return False, [str(exc)]

    for key in ["dataset_index_sha256", "work_plan_sha256"]:
        incoming = str(manifest.get(key, ""))
        current = fingerprint[key]
        if not incoming:
            errors.append(f"package_{key}_missing")
        elif incoming != current:
            errors.append(f"{key}_mismatch")
    return not errors, errors


def preview_review_package(zip_path: Path, outputs_dir: Path) -> dict[str, object]:
    incoming: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    with zipfile.ZipFile(zip_path, "r") as archive:
        if "review_package_manifest.json" not in archive.namelist():
            raise ValueError("review_package_manifest.json이 없는 패키지입니다.")
        manifest = json.loads(archive.read("review_package_manifest.json").decode("utf-8"))
        compatible, compatibility_errors = _compatibility(manifest, outputs_dir)
        for item in manifest.get("files", []):
            rel = str(item.get("path", ""))
            normalized = _safe_review_path(rel)
            member = rel[len("outputs/"):] if rel.startswith("outputs/") else rel
            if member not in archive.namelist():
                raise ValueError(f"package 파일 누락: {member}")
            incoming_bytes = archive.read(member)
            incoming_sha = str(item.get("sha256", ""))
            if not incoming_sha or _bytes_sha256(incoming_bytes) != incoming_sha:
                raise ValueError(f"package 파일 해시 불일치: {member}")
            target = outputs_dir / normalized
            local_sha = _sha256(target) if target.exists() else ""
            state = "new" if not target.exists() else ("same" if local_sha == incoming_sha else "conflict")
            row = {"path": rel, "state": state, "incoming_sha256": incoming_sha, "local_sha256": local_sha}
            incoming.append(row)
            if state == "conflict":
                conflicts.append(row)
    return {
        "manifest": manifest,
        "items": incoming,
        "conflicts": conflicts,
        "compatible": compatible,
        "compatibility_errors": compatibility_errors,
    }


def _merge_events(archive: zipfile.ZipFile, outputs_dir: Path) -> int:
    member = "review_events/review_events.csv"
    if member not in archive.namelist():
        return 0
    incoming = pd.read_csv(io.BytesIO(archive.read(member)))
    target = outputs_dir / member
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        try:
            local = pd.read_csv(target)
        except Exception:
            local = pd.DataFrame()
        merged = pd.concat([local, incoming], ignore_index=True, sort=False)
    else:
        merged = incoming
    dedup_cols = [c for c in ["event_at", "reviewer_name", "source", "split", "relative_folder", "image_id", "status", "modified_keys"] if c in merged.columns]
    if dedup_cols:
        merged = merged.drop_duplicates(dedup_cols, keep="last")
    merged.to_csv(target, index=False, encoding="utf-8-sig")
    return len(incoming)


def merge_review_package(zip_path: Path, outputs_dir: Path, *, conflict_policy: str = "keep_local") -> dict[str, int]:
    if conflict_policy not in {"keep_local", "use_incoming"}:
        raise ValueError("잘못된 conflict_policy")
    preview = preview_review_package(zip_path, outputs_dir)
    if not preview.get("compatible", False):
        raise ValueError("현재 본작업과 다른 검수 패키지입니다: " + ", ".join(preview.get("compatibility_errors", [])))

    stats = {"new": 0, "same": 0, "conflict": 0, "written": 0, "events_merged": 0}
    with zipfile.ZipFile(zip_path, "r") as archive:
        manifest = json.loads(archive.read("review_package_manifest.json").decode("utf-8"))
        for item in manifest.get("files", []):
            rel = str(item.get("path", ""))
            normalized = _safe_review_path(rel)
            target = outputs_dir / normalized
            incoming_sha = str(item.get("sha256", ""))
            member = rel[len("outputs/"):] if rel.startswith("outputs/") else rel
            incoming_bytes = archive.read(member)
            if _bytes_sha256(incoming_bytes) != incoming_sha:
                raise ValueError(f"병합 직전 package 파일 해시 불일치: {member}")

            if target.exists():
                local_sha = _sha256(target)
                if local_sha == incoming_sha:
                    stats["same"] += 1
                    continue
                stats["conflict"] += 1
                if conflict_policy == "keep_local":
                    continue
                backup = outputs_dir / "backups" / "reviewed_json_merge" / datetime.now().strftime("%Y%m%d_%H%M%S_%f") / normalized
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            else:
                stats["new"] += 1

            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(incoming_bytes)
            stats["written"] += 1
        stats["events_merged"] = _merge_events(archive, outputs_dir)
    return stats
