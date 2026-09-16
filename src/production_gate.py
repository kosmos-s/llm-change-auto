"""Production completion checks for the 3,000-item workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from results_inventory import unique_openai_results

TRUE_VALUES = {"true", "1", "yes", "y", "o"}


def successful_openai_results(results_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_rows = unique_openai_results(results_dir)
    if all_rows.empty:
        return all_rows.copy(), all_rows.copy()
    if "error" not in all_rows.columns:
        return all_rows.copy(), all_rows.iloc[0:0].copy()
    failed_mask = all_rows["error"].fillna("").astype(str).str.strip().ne("")
    return all_rows[~failed_mask].copy().reset_index(drop=True), all_rows[failed_mask].copy().reset_index(drop=True)


def latest_review_status(event_csv: Path) -> pd.DataFrame:
    if not event_csv.exists():
        return pd.DataFrame()
    try:
        events = pd.read_csv(event_csv)
    except Exception:
        return pd.DataFrame()
    if events.empty:
        return events
    for col, default in [("source", ""), ("split", ""), ("relative_folder", "."), ("image_id", "")]:
        if col not in events.columns:
            events[col] = default
    events["_key"] = (
        events["source"].fillna("").astype(str).str.lower().str.strip()
        + "|" + events["split"].fillna("").astype(str).str.lower().str.strip()
        + "|" + events["relative_folder"].fillna(".").astype(str).str.replace("\\", "/", regex=False).str.strip("/").replace("", ".")
        + "|" + events["image_id"].fillna("").astype(str).str.strip()
    )
    if "event_at" in events.columns:
        events["_event_order"] = pd.to_datetime(events["event_at"], errors="coerce")
        events = events.sort_values(["_event_order"], na_position="first")
    return events.drop_duplicates("_key", keep="last").reset_index(drop=True)


def reviewed_json_keys(reviewed_root: Path) -> set[str]:
    keys: set[str] = set()
    if not reviewed_root.exists():
        return keys
    for path in reviewed_root.rglob("*.json"):
        try:
            rel = path.relative_to(reviewed_root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) < 3:
            continue
        source, split = parts[0], parts[1]
        folder = "/".join(parts[2:-1]) or "."
        image_id = path.stem
        if image_id.endswith("_combined"):
            image_id = image_id[: -len("_combined")]
        keys.add(f"{source.lower()}|{split.lower()}|{folder.lower()}|{image_id}")
    return keys


def unresolved_review_items(review_lists_dir: Path, reviewed_root: Path, event_csv: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if review_lists_dir.exists():
        for path in sorted(review_lists_dir.glob("*.csv")):
            try:
                frame = pd.read_csv(path)
            except Exception:
                continue
            if frame.empty or "image_id" not in frame.columns:
                continue
            if "review_required_final" in frame.columns:
                required = frame["review_required_final"].fillna("").astype(str).str.lower().isin(TRUE_VALUES)
                frame = frame[required].copy()
            frame["_review_list"] = path.name
            frames.append(frame)
    if not frames:
        return pd.DataFrame()

    all_items = pd.concat(frames, ignore_index=True, sort=False)
    for col, default in [("group", ""), ("source", ""), ("split", ""), ("relative_folder", "."), ("image_id", "")]:
        if col not in all_items.columns:
            all_items[col] = default
    source_series = all_items["source"].where(all_items["source"].fillna("").astype(str).str.strip().ne(""), all_items["group"])
    folder = all_items["relative_folder"].fillna(".").astype(str).str.replace("\\", "/", regex=False).str.strip("/")
    folder = folder.mask(folder.eq(""), ".")
    all_items["_key"] = (
        source_series.fillna("").astype(str).str.lower().str.strip()
        + "|" + all_items["split"].fillna("").astype(str).str.lower().str.strip()
        + "|" + folder.str.lower()
        + "|" + all_items["image_id"].fillna("").astype(str).str.strip()
    )
    all_items = all_items.drop_duplicates("_key", keep="last")

    reviewed = reviewed_json_keys(reviewed_root)
    latest = latest_review_status(event_csv)
    deferred: set[str] = set()
    if not latest.empty and "status" in latest.columns:
        deferred = set(latest[latest["status"].astype(str) == "deferred"]["_key"].astype(str))

    pending = all_items[~all_items["_key"].isin(reviewed)].copy()
    pending["review_state"] = pending["_key"].map(lambda key: "deferred" if key in deferred else "unreviewed")
    return pending.reset_index(drop=True)


def final_gate_summary(outputs_dir: Path, target_total: int) -> dict[str, object]:
    success, failed = successful_openai_results(outputs_dir / "llm_results")
    pending = unresolved_review_items(
        outputs_dir / "review_lists",
        outputs_dir / "reviewed_json",
        outputs_dir / "review_events" / "review_events.csv",
    )
    return {
        "target_total": int(target_total),
        "success_count": int(len(success)),
        "failed_count": int(len(failed)),
        "missing_success": max(int(target_total) - int(len(success)), 0),
        "pending_review_count": int(len(pending)),
        "deferred_count": int((pending.get("review_state", pd.Series(dtype=str)) == "deferred").sum()) if not pending.empty else 0,
        "ready": bool(len(success) >= int(target_total) and len(failed) == 0 and len(pending) == 0),
    }
