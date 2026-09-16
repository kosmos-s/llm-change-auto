"""Coverage checks for the production OpenAI -> compare -> review workflow."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from results_inventory import unique_openai_results
from work_plan import logical_key_frame

PRODUCTION_MODES = {"production", "prod", "본작업"}
TRUE_VALUES = {"true", "1", "yes", "y", "o"}
SIGNATURE_COLUMNS = ["run_id", "processed_at", "response_id"]


def _plan_keys(work_plan_path: Path) -> set[str]:
    if not work_plan_path.exists():
        return set()
    plan = pd.read_csv(work_plan_path)
    if plan.empty:
        return set()
    return set(logical_key_frame(plan).astype(str))


def _production_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "image_id" not in frame.columns or "work_mode" not in frame.columns:
        return frame.iloc[0:0].copy()
    mode = frame["work_mode"].fillna("").astype(str).str.strip().str.lower()
    return frame[mode.isin(PRODUCTION_MODES)].copy()


def _rows_from_csv_dir(directory: Path, pattern: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if not directory.exists():
        return pd.DataFrame()
    for order, path in enumerate(sorted(directory.glob(pattern))):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        frame = _production_rows(frame)
        if frame.empty:
            continue
        frame["_source_mtime"] = path.stat().st_mtime
        frame["_source_order"] = order
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _with_logical_key(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    copy = rows.copy()
    copy["_logical_key"] = logical_key_frame(copy)
    return copy


def _latest_rows(rows: pd.DataFrame, plan_keys: set[str]) -> pd.DataFrame:
    keyed = _with_logical_key(rows)
    if keyed.empty or not plan_keys:
        return keyed.iloc[0:0].copy()
    keyed = keyed[keyed["_logical_key"].isin(plan_keys)].copy()
    if keyed.empty:
        return keyed
    keyed["_row_order"] = range(len(keyed))
    sort_columns: list[str] = []
    if "processed_at" in keyed.columns:
        keyed["_processed_order"] = pd.to_datetime(keyed["processed_at"], errors="coerce")
        sort_columns.append("_processed_order")
    if "_source_mtime" in keyed.columns:
        sort_columns.append("_source_mtime")
    if "_source_order" in keyed.columns:
        sort_columns.append("_source_order")
    sort_columns.append("_row_order")
    keyed = keyed.sort_values(sort_columns, na_position="first", kind="stable")
    return keyed.drop_duplicates("_logical_key", keep="last").reset_index(drop=True)


def _signature_series(rows: pd.DataFrame) -> pd.Series:
    """Build an execution signature, returning blank when every component is blank."""
    if rows.empty:
        return pd.Series(dtype=str)
    parts: list[pd.Series] = []
    has_value = pd.Series(False, index=rows.index, dtype=bool)
    for column in SIGNATURE_COLUMNS:
        if column in rows.columns:
            part = rows[column].fillna("").astype(str).str.strip()
        else:
            part = pd.Series("", index=rows.index, dtype=str)
        parts.append(part)
        has_value = has_value | part.ne("")
    signature = parts[0]
    for part in parts[1:]:
        signature = signature + "|" + part
    return signature.where(has_value, "")


def _latest_openai_rows(outputs_dir: Path, plan_keys: set[str]) -> pd.DataFrame:
    rows = unique_openai_results(outputs_dir / "llm_results")
    rows = _production_rows(rows)
    return _latest_rows(rows, plan_keys)


def _fresh_compare_rows(outputs_dir: Path, work_plan_path: Path) -> tuple[pd.DataFrame, int]:
    plan_keys = _plan_keys(work_plan_path)
    latest_compare = _latest_rows(
        _rows_from_csv_dir(outputs_dir / "compare_results", "*_compare.csv"),
        plan_keys,
    )
    latest_openai = _latest_openai_rows(outputs_dir, plan_keys)
    if latest_compare.empty or latest_openai.empty:
        return latest_compare.iloc[0:0].copy(), len(latest_compare)

    compare = latest_compare.copy()
    openai = latest_openai.copy()
    compare["_execution_signature"] = _signature_series(compare)
    openai["_execution_signature"] = _signature_series(openai)
    expected = openai.set_index("_logical_key")["_execution_signature"].to_dict()
    fresh_mask = compare.apply(
        lambda row: bool(expected.get(str(row["_logical_key"]), ""))
        and str(row["_execution_signature"]) == str(expected.get(str(row["_logical_key"]), "")),
        axis=1,
    )
    fresh = compare[fresh_mask].copy().reset_index(drop=True)
    stale_count = int(len(compare) - len(fresh))
    return fresh, stale_count


def current_required_review_rows(outputs_dir: Path, work_plan_path: Path) -> pd.DataFrame:
    """Return current, fresh production compare rows that require human review."""
    fresh_compare, _ = _fresh_compare_rows(outputs_dir, work_plan_path)
    if fresh_compare.empty or "review_required_final" not in fresh_compare.columns:
        return fresh_compare.iloc[0:0].copy()
    required = fresh_compare["review_required_final"].fillna("").astype(str).str.strip().str.lower().isin(TRUE_VALUES)
    return fresh_compare[required].copy().reset_index(drop=True)


def _fresh_review_list_keys(
    outputs_dir: Path,
    work_plan_path: Path,
    required_rows: pd.DataFrame,
) -> tuple[set[str], int]:
    """Return required keys represented by a review list from the same OpenAI execution."""
    if required_rows.empty:
        return set(), 0

    plan_keys = _plan_keys(work_plan_path)
    review_rows = _latest_rows(
        _rows_from_csv_dir(outputs_dir / "review_lists", "*_review.csv"),
        plan_keys,
    )
    if review_rows.empty:
        return set(), 0

    required = required_rows.copy()
    review = review_rows.copy()
    required["_execution_signature"] = _signature_series(required)
    review["_execution_signature"] = _signature_series(review)
    expected = required.set_index("_logical_key")["_execution_signature"].to_dict()
    required_keys = set(expected)

    relevant = review[review["_logical_key"].astype(str).isin(required_keys)].copy()
    if relevant.empty:
        return set(), 0

    fresh_mask = relevant.apply(
        lambda row: bool(expected.get(str(row["_logical_key"]), ""))
        and str(row["_execution_signature"]) == str(expected.get(str(row["_logical_key"]), "")),
        axis=1,
    )
    fresh_keys = set(relevant.loc[fresh_mask, "_logical_key"].astype(str))
    stale_count = int((~fresh_mask).sum())
    return fresh_keys, stale_count


def pipeline_coverage(outputs_dir: Path, work_plan_path: Path) -> dict[str, int | bool]:
    """Return production coverage using only fresh outputs for the frozen work plan.

    A compare row is considered fresh only when its execution signature matches the
    latest OpenAI row for the same logical sample. Current review-required samples must
    also be present in a production review-list CSV created from that same execution,
    preventing stale review lists from satisfying the Final Gate after an OpenAI retry.
    """
    plan_keys = _plan_keys(work_plan_path)
    target = len(plan_keys)
    fresh_compare, stale_compare_count = _fresh_compare_rows(outputs_dir, work_plan_path)
    compare_count = int(len(fresh_compare))

    decision_rows = fresh_compare.iloc[0:0].copy()
    if not fresh_compare.empty and "review_required_final" in fresh_compare.columns:
        values = fresh_compare["review_required_final"]
        decided = values.notna() & values.astype(str).str.strip().ne("")
        decision_rows = fresh_compare[decided].copy()
    review_decision_count = int(len(decision_rows))

    required_rows = current_required_review_rows(outputs_dir, work_plan_path)
    required_keys = set(required_rows.get("_logical_key", pd.Series(dtype=str)).astype(str))
    review_required_count = len(required_keys)

    fresh_review_keys, stale_review_list_count = _fresh_review_list_keys(
        outputs_dir, work_plan_path, required_rows
    )
    review_list_count = len(required_keys & fresh_review_keys)
    review_list_missing = max(review_required_count - review_list_count, 0)

    return {
        "target": target,
        "compare_count": compare_count,
        "stale_compare_count": stale_compare_count,
        "review_decision_count": review_decision_count,
        "review_required_count": review_required_count,
        "review_list_count": review_list_count,
        "stale_review_list_count": stale_review_list_count,
        "review_list_missing": review_list_missing,
        "compare_missing": max(target - compare_count, 0),
        "review_decision_missing": max(target - review_decision_count, 0),
        "ready": bool(
            target > 0
            and compare_count >= target
            and review_decision_count >= target
            and stale_compare_count == 0
            and review_list_missing == 0
        ),
    }
