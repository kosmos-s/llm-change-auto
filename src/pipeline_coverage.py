"""Coverage checks for the OpenAI -> compare -> review-decision production pipeline."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from work_plan import logical_key_frame


def _plan_keys(work_plan_path: Path) -> set[str]:
    if not work_plan_path.exists():
        return set()
    plan = pd.read_csv(work_plan_path)
    if plan.empty:
        return set()
    return set(logical_key_frame(plan).astype(str))


def _rows_from_csv_dir(directory: Path, pattern: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not directory.exists():
        return pd.DataFrame()
    for path in sorted(directory.glob(pattern)):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty or "image_id" not in frame.columns:
            continue
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _coverage_count(rows: pd.DataFrame, plan_keys: set[str]) -> int:
    if rows.empty or not plan_keys:
        return 0
    copy = rows.copy()
    copy["_logical_key"] = logical_key_frame(copy)
    return int(copy[copy["_logical_key"].isin(plan_keys)]["_logical_key"].drop_duplicates().shape[0])


def pipeline_coverage(outputs_dir: Path, work_plan_path: Path) -> dict[str, int | bool]:
    """Return unique work-plan coverage at compare and review-decision stages.

    Review-decision coverage means every work-plan sample reached the step that decides
    whether human review is required. `make_review_list` outputs all compared rows, with
    `review_required_final` indicating whether human review is needed, so coverage is
    measured over all review-list rows rather than only the required subset.
    """
    plan_keys = _plan_keys(work_plan_path)
    target = len(plan_keys)
    compare_rows = _rows_from_csv_dir(outputs_dir / "compare_results", "*_compare.csv")
    review_rows = _rows_from_csv_dir(outputs_dir / "review_lists", "*_review.csv")
    compare_count = _coverage_count(compare_rows, plan_keys)
    review_decision_count = _coverage_count(review_rows, plan_keys)
    return {
        "target": target,
        "compare_count": compare_count,
        "review_decision_count": review_decision_count,
        "compare_missing": max(target - compare_count, 0),
        "review_decision_missing": max(target - review_decision_count, 0),
        "ready": bool(target > 0 and compare_count >= target and review_decision_count >= target),
    }
