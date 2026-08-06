"""Build a human-review history CSV from reviewed JSON files.

This first version records the latest saved reviewed JSON state and joins it with
original labels and the most recent OpenAI result for the same image.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from json_io import get_label_state, load_json

LABEL_KEYS = [
    "arti",
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
    "tree",
    "fore",
    "farm",
    "water",
]

STATE_TO_LABEL = {
    "Artifact": "arti",
    "arti_bu": "arti_bu",
    "arti_bu_t": "arti_bu_t",
    "arti_binil": "arti_binil",
    "arti_road": "arti_road",
    "arti_roa_m": "arti_roa_m",
    "arti_other": "arti_other",
    "Tree": "tree",
    "forest": "fore",
    "farmland": "farm",
    "water": "water",
}


def as_int(value: object) -> int:
    try:
        return int(float(value))
    except Exception:
        text = str(value).strip().lower()
        return 1 if text in {"o", "true", "yes", "y"} else 0


def normalize_reviewed_json(path: Path) -> dict[str, Any]:
    state = get_label_state(load_json(path))
    labels = {
        label_key: int(bool(state.get(state_key, False)))
        for state_key, label_key in STATE_TO_LABEL.items()
    }
    labels["change"] = int(any(labels[key] for key in LABEL_KEYS))
    labels["reason"] = str(state.get("reason", ""))
    labels["reason_ko"] = str(state.get("reason_ko", ""))
    return labels


def load_latest_llm_rows(results_dir: Path) -> pd.DataFrame:
    if not results_dir.exists():
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for csv_path in sorted(results_dir.glob("*.csv")):
        try:
            frame = pd.read_csv(csv_path)
        except Exception:
            continue
        if frame.empty or "image_id" not in frame.columns:
            continue
        frame = frame.copy()
        frame["_llm_csv"] = str(csv_path)
        frame["_llm_csv_mtime"] = csv_path.stat().st_mtime
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    key_cols = [col for col in ["group", "split", "image_id"] if col in merged.columns]
    if "image_id" not in key_cols:
        return pd.DataFrame()

    merged = merged.sort_values("_llm_csv_mtime")
    return merged.drop_duplicates(subset=key_cols, keep="last")


def make_lookup_key(source: str, split: str, image_id: str) -> tuple[str, str, str]:
    return (str(source).strip().lower(), str(split).strip().lower(), str(image_id).strip())


def infer_review_location(reviewed_path: Path, reviewed_root: Path) -> tuple[str, str, str]:
    relative = reviewed_path.relative_to(reviewed_root)
    parts = relative.parts
    source = parts[0] if len(parts) >= 1 else "unknown"
    split = parts[1] if len(parts) >= 2 else "unknown"
    folder = "/".join(parts[2:-1]) if len(parts) > 3 else "."
    return source, split, folder


def build_review_history(
    index_csv: Path,
    reviewed_root: Path,
    llm_results_dir: Path,
    output_csv: Path,
) -> pd.DataFrame:
    if not index_csv.exists():
        raise FileNotFoundError(f"dataset_index.csv를 찾을 수 없습니다: {index_csv}")

    index_df = pd.read_csv(index_csv)
    required = {"image_id", "group", "split", "json_path", "image_path"}
    missing = sorted(required - set(index_df.columns))
    if missing:
        raise ValueError(f"dataset_index.csv 필수 컬럼이 없습니다: {', '.join(missing)}")

    index_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for _, row in index_df.iterrows():
        key = make_lookup_key(row.get("group", ""), row.get("split", ""), row.get("image_id", ""))
        index_lookup[key] = row.to_dict()

    llm_df = load_latest_llm_rows(llm_results_dir)
    llm_lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not llm_df.empty:
        for _, row in llm_df.iterrows():
            key = make_lookup_key(row.get("group", ""), row.get("split", ""), row.get("image_id", ""))
            llm_lookup[key] = row.to_dict()

    reviewed_files = sorted(reviewed_root.rglob("*.json")) if reviewed_root.exists() else []
    rows: list[dict[str, Any]] = []

    for reviewed_path in reviewed_files:
        source, split, relative_folder = infer_review_location(reviewed_path, reviewed_root)
        image_id = reviewed_path.stem.replace("_combined", "")
        key = make_lookup_key(source, split, image_id)
        original = index_lookup.get(key)
        if original is None:
            continue

        human = normalize_reviewed_json(reviewed_path)
        llm = llm_lookup.get(key, {})

        modified_keys: list[str] = []
        row_data: dict[str, Any] = {
            "reviewed_at": datetime.fromtimestamp(reviewed_path.stat().st_mtime).isoformat(timespec="seconds"),
            "image_id": image_id,
            "source": source,
            "split": split,
            "relative_folder": relative_folder,
            "image_path": str(original.get("image_path", "")),
            "original_json_path": str(original.get("json_path", "")),
            "reviewed_json_path": str(reviewed_path),
            "llm_result_csv": str(llm.get("_llm_csv", "")),
            "original_change": as_int(original.get("original_change", 0)),
            "llm_change": as_int(llm.get("llm_change", 0)) if llm else "",
            "human_change": human["change"],
            "original_reason": str(original.get("original_reason", "")),
            "llm_reason_ko": str(llm.get("reason_ko", "")),
            "human_reason": human["reason"],
            "human_reason_ko": human["reason_ko"],
            "llm_confidence": llm.get("confidence", ""),
            "llm_model": llm.get("llm_model", ""),
            "llm_error": llm.get("error", ""),
            "review_reasons": llm.get("review_reasons", ""),
        }

        if row_data["original_change"] != row_data["human_change"]:
            modified_keys.append("change")

        for label in LABEL_KEYS:
            original_value = as_int(original.get(f"original_{label}", 0))
            llm_value: int | str = as_int(llm.get(label, 0)) if llm else ""
            human_value = int(human[label])
            row_data[f"original_{label}"] = original_value
            row_data[f"llm_{label}"] = llm_value
            row_data[f"human_{label}"] = human_value
            if original_value != human_value:
                modified_keys.append(label)

        row_data["labels_modified"] = bool(modified_keys)
        row_data["modified_keys"] = ",".join(modified_keys)
        row_data["review_status"] = "modified" if modified_keys else "unchanged"
        row_data["llm_human_change_match"] = (
            row_data["llm_change"] == row_data["human_change"]
            if row_data["llm_change"] != ""
            else ""
        )
        rows.append(row_data)

    result = pd.DataFrame(rows)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_csv, index=False, encoding="utf-8-sig")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="outputs/dataset_index.csv")
    parser.add_argument("--reviewed-root", default="outputs/reviewed_json")
    parser.add_argument("--llm-results", default="outputs/llm_results")
    parser.add_argument("--output", default="outputs/review_history/review_history.csv")
    args = parser.parse_args()

    result = build_review_history(
        index_csv=Path(args.index),
        reviewed_root=Path(args.reviewed_root),
        llm_results_dir=Path(args.llm_results),
        output_csv=Path(args.output),
    )
    print(f"reviewed={len(result)} saved={args.output}")


if __name__ == "__main__":
    main()
