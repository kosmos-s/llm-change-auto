"""Production completion checks for the 3,000-item workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline_coverage import pipeline_coverage
from production_integrity import validate_plan_binding
from results_inventory import unique_openai_results
from work_plan import logical_key_frame

TRUE_VALUES = {"true", "1", "yes", "y", "o"}
PRODUCTION_MODES = {"production", "prod", "본작업"}


def _default_plan_for_results(results_dir: Path) -> Path | None:
    candidate = Path(results_dir).parent / "work_plan_3000.csv"
    return candidate if candidate.exists() else None


def _plan_keys(work_plan_path: Path | None) -> set[str]:
    if work_plan_path is None or not work_plan_path.exists():
        return set()
    try:
        plan = pd.read_csv(work_plan_path)
    except Exception:
        return set()
    return set(logical_key_frame(plan).astype(str)) if not plan.empty else set()


def _filter_to_work_plan(rows: pd.DataFrame, work_plan_path: Path | None) -> pd.DataFrame:
    if rows.empty or work_plan_path is None or not work_plan_path.exists():
        return rows.copy()
    keys = _plan_keys(work_plan_path)
    if not keys:
        return rows.iloc[0:0].copy()
    copy = rows.copy()
    copy["_logical_key"] = logical_key_frame(copy)
    return copy[copy["_logical_key"].isin(keys)].drop(columns=["_logical_key"], errors="ignore").reset_index(drop=True)


def successful_openai_results(results_dir: Path, work_plan_path: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    if work_plan_path is None:
        work_plan_path = _default_plan_for_results(results_dir)
    frozen_plan = work_plan_path is not None and work_plan_path.exists()
    all_rows = _filter_to_work_plan(unique_openai_results(results_dir), work_plan_path)

    # Once a production plan is frozen, only rows explicitly created in production
    # mode may count. Legacy/pilot rows without work_mode and explicit test rows are
    # ignored even if they happen to share the same logical sample key.
    if frozen_plan and not all_rows.empty:
        if "work_mode" not in all_rows.columns:
            all_rows = all_rows.iloc[0:0].copy()
        else:
            mode = all_rows["work_mode"].fillna("").astype(str).str.strip().str.lower()
            all_rows = all_rows[mode.isin(PRODUCTION_MODES)].copy().reset_index(drop=True)

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
    folder = events["relative_folder"].fillna(".").astype(str).str.replace("\\", "/", regex=False).str.strip("/").replace("", ".")
    events["_key"] = events["source"].fillna("").astype(str).str.lower().str.strip() + "|" + events["split"].fillna("").astype(str).str.lower().str.strip() + "|" + folder.str.lower() + "|" + events["image_id"].fillna("").astype(str).str.strip()
    if "event_at" in events.columns:
        events["_event_order"] = pd.to_datetime(events["event_at"], errors="coerce")
        events = events.sort_values("_event_order", na_position="first")
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
            image_id = image_id[:-9]
        keys.add(f"{source.lower()}|{split.lower()}|{folder.lower()}|{image_id}")
    return keys


def unresolved_review_items(review_lists_dir: Path, reviewed_root: Path, event_csv: Path, work_plan_path: Path | None = None) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if review_lists_dir.exists():
        for path in sorted(review_lists_dir.glob("*.csv")):
            try:
                frame = pd.read_csv(path)
            except Exception:
                continue
            if frame.empty or "image_id" not in frame.columns:
                continue
            if "work_mode" in frame.columns:
                mode = frame["work_mode"].fillna("").astype(str).str.strip().str.lower()
                frame = frame[mode.isin(PRODUCTION_MODES)].copy()
            elif work_plan_path is not None:
                continue
            if "review_required_final" in frame.columns:
                frame = frame[frame["review_required_final"].fillna("").astype(str).str.lower().isin(TRUE_VALUES)].copy()
            frame["_review_list"] = path.name
            frames.append(frame)
    if not frames:
        return pd.DataFrame()

    all_items = pd.concat(frames, ignore_index=True, sort=False)
    for col, default in [("group", ""), ("source", ""), ("split", ""), ("relative_folder", "."), ("image_id", "")]:
        if col not in all_items.columns:
            all_items[col] = default
    source_series = all_items["source"].where(all_items["source"].fillna("").astype(str).str.strip().ne(""), all_items["group"])
    folder = all_items["relative_folder"].fillna(".").astype(str).str.replace("\\", "/", regex=False).str.strip("/").replace("", ".")
    all_items["_key"] = source_series.fillna("").astype(str).str.lower().str.strip() + "|" + all_items["split"].fillna("").astype(str).str.lower().str.strip() + "|" + folder.str.lower() + "|" + all_items["image_id"].fillna("").astype(str).str.strip()
    all_items = all_items.drop_duplicates("_key", keep="last")

    keys = _plan_keys(work_plan_path)
    if keys:
        all_items = all_items[all_items["_key"].isin(keys)].copy()

    reviewed = reviewed_json_keys(reviewed_root)
    latest = latest_review_status(event_csv)
    deferred = set(latest[latest["status"].astype(str) == "deferred"]["_key"].astype(str)) if not latest.empty and "status" in latest.columns else set()
    pending = all_items[~all_items["_key"].isin(reviewed)].copy()
    pending["review_state"] = pending["_key"].map(lambda key: "deferred" if key in deferred else "unreviewed")
    return pending.reset_index(drop=True)


def final_gate_summary(outputs_dir: Path, target_total: int) -> dict[str, object]:
    work_plan_path = outputs_dir / "work_plan_3000.csv"
    index_path = outputs_dir / "dataset_index.csv"
    binding = validate_plan_binding(index_path, work_plan_path)
    success, failed = successful_openai_results(outputs_dir / "llm_results", work_plan_path if work_plan_path.exists() else None)
    pending = unresolved_review_items(outputs_dir / "review_lists", outputs_dir / "reviewed_json", outputs_dir / "review_events" / "review_events.csv", work_plan_path if work_plan_path.exists() else None)
    try:
        plan_count = len(pd.read_csv(work_plan_path)) if work_plan_path.exists() else 0
    except Exception:
        plan_count = 0
    effective_target = plan_count or int(target_total)
    coverage = pipeline_coverage(outputs_dir, work_plan_path) if work_plan_path.exists() else {
        "target": effective_target,
        "compare_count": 0,
        "review_decision_count": 0,
        "compare_missing": effective_target,
        "review_decision_missing": effective_target,
        "ready": False,
    }
    return {
        "target_total": effective_target,
        "success_count": len(success),
        "failed_count": len(failed),
        "missing_success": max(effective_target - len(success), 0),
        "compare_count": int(coverage["compare_count"]),
        "compare_missing": int(coverage["compare_missing"]),
        "review_decision_count": int(coverage["review_decision_count"]),
        "review_decision_missing": int(coverage["review_decision_missing"]),
        "pending_review_count": len(pending),
        "deferred_count": int((pending.get("review_state", pd.Series(dtype=str)) == "deferred").sum()) if not pending.empty else 0,
        "work_plan_present": work_plan_path.exists(),
        "plan_binding_ready": bool(binding["ready"]),
        "plan_binding_reasons": list(binding["reasons"]),
        "coverage_ready": bool(coverage["ready"]),
        "ready": bool(
            work_plan_path.exists()
            and bool(binding["ready"])
            and len(success) >= effective_target
            and len(failed) == 0
            and bool(coverage["ready"])
            and len(pending) == 0
        ),
    }
