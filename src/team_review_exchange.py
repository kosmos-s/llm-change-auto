"""Export and merge reviewed_json packages between teammate PCs."""
from __future__ import annotations
import hashlib, io, json, shutil, zipfile
from datetime import datetime
from pathlib import Path
import pandas as pd


def _sha256(path: Path) -> str:
    d=hashlib.sha256()
    with path.open("rb") as h:
        for c in iter(lambda:h.read(1024*1024),b""): d.update(c)
    return d.hexdigest()


def _safe_review_path(value: str) -> Path:
    text=value.replace("\\","/")
    if text.startswith("outputs/"): text=text[len("outputs/"):]
    p=Path(text)
    if not p.parts or p.parts[0] != "reviewed_json" or p.is_absolute() or ".." in p.parts:
        raise ValueError(f"허용되지 않은 package 경로: {value}")
    return p


def export_review_package(outputs_dir: Path, reviewer_name: str) -> Path:
    reviewed_root=outputs_dir/"reviewed_json"; events=outputs_dir/"review_events"/"review_events.csv"
    packages=outputs_dir/"review_packages"; packages.mkdir(parents=True,exist_ok=True)
    safe="_".join((reviewer_name.strip() or "unknown").split()); target=packages/f"reviews_{safe}_{datetime.now():%Y%m%d_%H%M%S}.zip"
    files=[]
    with zipfile.ZipFile(target,"w",compression=zipfile.ZIP_DEFLATED) as z:
        if reviewed_root.exists():
            for p in sorted(reviewed_root.rglob("*.json")):
                rel=p.relative_to(outputs_dir).as_posix(); z.write(p,rel); files.append({"path":rel,"sha256":_sha256(p)})
        if events.exists(): z.write(events,"review_events/review_events.csv")
        z.writestr("review_package_manifest.json",json.dumps({"reviewer_name":reviewer_name.strip() or "unknown","created_at":datetime.now().isoformat(timespec="seconds"),"file_count":len(files),"files":files},ensure_ascii=False,indent=2))
    return target


def preview_review_package(zip_path: Path, outputs_dir: Path) -> dict[str,object]:
    incoming=[]; conflicts=[]
    with zipfile.ZipFile(zip_path,"r") as z:
        manifest=json.loads(z.read("review_package_manifest.json").decode("utf-8"))
        for item in manifest.get("files",[]):
            rel=str(item.get("path","")); normalized=_safe_review_path(rel); target=outputs_dir/normalized
            incoming_sha=str(item.get("sha256","")); local_sha=_sha256(target) if target.exists() else ""
            state="new" if not target.exists() else ("same" if local_sha==incoming_sha else "conflict")
            row={"path":rel,"state":state,"incoming_sha256":incoming_sha,"local_sha256":local_sha}; incoming.append(row)
            if state=="conflict": conflicts.append(row)
    return {"manifest":manifest,"items":incoming,"conflicts":conflicts}


def _merge_events(z: zipfile.ZipFile, outputs_dir: Path) -> int:
    member="review_events/review_events.csv"
    if member not in z.namelist(): return 0
    incoming=pd.read_csv(io.BytesIO(z.read(member)))
    target=outputs_dir/member; target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        try: local=pd.read_csv(target)
        except Exception: local=pd.DataFrame()
        merged=pd.concat([local,incoming],ignore_index=True,sort=False)
    else: merged=incoming
    dedup_cols=[c for c in ["event_at","reviewer_name","source","split","relative_folder","image_id","status","modified_keys"] if c in merged.columns]
    if dedup_cols: merged=merged.drop_duplicates(dedup_cols,keep="last")
    merged.to_csv(target,index=False,encoding="utf-8-sig")
    return len(incoming)


def merge_review_package(zip_path: Path, outputs_dir: Path, *, conflict_policy: str="keep_local") -> dict[str,int]:
    if conflict_policy not in {"keep_local","use_incoming"}: raise ValueError("잘못된 conflict_policy")
    stats={"new":0,"same":0,"conflict":0,"written":0,"events_merged":0}
    with zipfile.ZipFile(zip_path,"r") as z:
        manifest=json.loads(z.read("review_package_manifest.json").decode("utf-8"))
        for item in manifest.get("files",[]):
            rel=str(item.get("path","")); normalized=_safe_review_path(rel); target=outputs_dir/normalized; incoming_sha=str(item.get("sha256",""))
            if target.exists():
                local_sha=_sha256(target)
                if local_sha==incoming_sha: stats["same"]+=1; continue
                stats["conflict"]+=1
                if conflict_policy=="keep_local": continue
                backup=outputs_dir/"backups"/"reviewed_json_merge"/datetime.now().strftime("%Y%m%d_%H%M%S_%f")/normalized
                backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
            else: stats["new"]+=1
            member=rel[len("outputs/"):] if rel.startswith("outputs/") else rel
            if member not in z.namelist(): raise ValueError(f"package 파일 누락: {member}")
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(member) as src,target.open("wb") as dst: shutil.copyfileobj(src,dst)
            stats["written"]+=1
        stats["events_merged"]=_merge_events(z,outputs_dir)
    return stats
