"""Create human-review CSVs from data-quality findings without mutating raw data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def make_quality_review_list(
    index_csv: Path,
    quality_csv: Path,
    output_csv: Path,
    codes: list[str] | None = None,
) -> pd.DataFrame:
    if not index_csv.exists():
        raise FileNotFoundError(index_csv)
    if not quality_csv.exists():
        raise FileNotFoundError(quality_csv)

    index_df = pd.read_csv(index_csv)
    quality = pd.read_csv(quality_csv)
    if quality.empty:
        result = index_df.iloc[0:0].copy()
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_csv, index=False, encoding="utf-8-sig")
        return result

    wanted = set(codes or ["artifact_logic"])
    quality = quality[quality["code"].astype(str).isin(wanted)].copy()
    rows: list[dict[str, object]] = []

    for _, issue in quality.iterrows():
        image_id = str(issue.get("image_id", "")).strip()
        group = str(issue.get("group", "")).strip()
        candidates = index_df[index_df["image_id"].astype(str) == image_id]
        if group and "group" in candidates.columns:
            grouped = candidates[candidates["group"].astype(str) == group]
            if not grouped.empty:
                candidates = grouped

        issue_path = str(issue.get("path", "") or "").strip()
        if issue_path and "json_path" in candidates.columns:
            exact = candidates[candidates["json_path"].astype(str) == issue_path]
            if not exact.empty:
                candidates = exact

        for _, row in candidates.iterrows():
            data = row.to_dict()
            data["review_required_final"] = True
            data["priority_score"] = 95 if str(issue.get("severity", "")).lower() == "error" else 80
            data["review_reasons"] = f"quality:{issue.get('code', '')}"
            data["quality_code"] = str(issue.get("code", ""))
            data["quality_detail"] = str(issue.get("detail", ""))
            rows.append(data)

    result = pd.DataFrame(rows)
    if not result.empty:
        key_cols = [col for col in ["group", "split", "relative_folder", "image_id"] if col in result.columns]
        result = result.drop_duplicates(key_cols, keep="first")
        if "priority_score" in result.columns:
            result = result.sort_values("priority_score", ascending=False)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return result.reset_index(drop=True)
