"""Build a human-review history CSV from reviewed JSON files.

The latest reviewed JSON state is joined with the matching original label row and
the most recent OpenAI result. Matching includes relative_folder so duplicate
image_id values under different errors subfolders do not collide.
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


def normalize_folder(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.lower() == "nan" or text == ".":
        return "."
    return text.strip("/") or "."


def infer_relative_folder_from_image_path(image_path: object, split: object) -> str:
    path_text = str(image_path or "").strip()
    split_text = str(split or "").strip().lower()
    if not path_text or not split_text or split_text == "nan":
        return "."

    path = Path(path_text)
    parts = list(path.parts)
    lower_parts = [part.lower() for part in parts]
    split_indexes = [index for index, part in enumerate(lower_parts) if part == split_text]
    if not split_indexes:
        return "."

    split_index = split_indexes[-1]
    folder_parts = parts[split_index + 1 : -1]
    return normalize_folder("/".join(folder_parts))


def row_relative_folder(row: pd.Series | dict[str, Any]) -> str:
    value = row.get("relative_folder", "")
    normalized = normalize_folder(value)
    if normalized != ".":
        return normalized
    return infer_relative_folder_from_image_path(row.get("image_path", ""), row.get("split", ""))


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


def filter_openai_rows(frame: pd.DataFrame, csv_path: Path) -> pd.DataFrame:
    """Keep only OpenAI rows.

    New result CSVs contain llm_provider=openai. Older OpenAI CSVs may not have
    that column, so an openai_ filename is accepted as a backward-compatible
    fallback. Gemini files are never included.
    """
    if frame.empty:
        return frame

    if "llm_provider" in frame.columns:
        provider = frame["llm_provider"].fillna("").astype(str).str.strip().str.lower()
        openai_rows = frame[provider == "openai"].copy()
        if not openai_rows.empty:
            return openai_rows
        if provider.ne("").any():
            return frame.iloc[0:0].copy()

    filename = csv_path.name.lower()
    if filename.startswith("openai_") and "gemini" not in filename:
        result = frame.copy()
        if "llm_provider" not in result.columns:
            result["llm_provider"] = "openai"
        else:
            result["llm_provider"] = result["llm_provider"].replace("", "openai").fillna("openai")
        return result

    return frame.iloc[0:0].copy()


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

        frame = filter_openai_rows(frame, csv_path)
        if frame.empty:
            continue

        frame = frame.copy()
        frame["_relative_folder"] = frame.apply(row_relative_folder, axis=1)
        frame["_llm_csv"] = str(csv_path)
        frame["_llm_csv_mtime"] = csv_path.stat().st_mtime
        frames.append(frame)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True, sort=False)
    required_key_cols = ["group", "split", "_relative_folder", "image_id"]
    if not all(col in merged.columns for col in required_key_cols):
        return pd.DataFrame()

    merged = merged.sort_values("_llm_csv_mtime")
    return merged.drop_duplicates(subset=required_key_cols, keep="last")


def make_lookup_key(source: str, split: str, relative_folder: str, image_id: str) -> tuple[str, str, str, str]:
    return (
        str(source).strip().lower(),
        str(split).strip().lower(),
        normalize_folder(relative_folder).lower(),
        str(image_id).strip(),
    )


def infer_review_location(reviewed_path: Path, reviewed_root: Path) -> tuple[str, str, str]:
    relative = reviewed_path.relative_to(reviewed_root)
    parts = relative.parts
    source = parts[0] if len(parts) >= 1 else "unknown"
    split = parts[1] if len(parts) >= 2 else "unknown"
    folder = normalize_folder("/".join(parts[2:-1])) if len(parts) > 3 else "."
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

    index_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for _, row in index_df.iterrows():
        relative_folder = row_relative_folder(row)
        key = make_lookup_key(
            row.get("group", ""),
            row.get("split", ""),
            relative_folder,
            row.get("image_id", ""),
        )
        row_data = row.to_dict()
        row_data["relative_folder"] = relative_folder
        index_lookup[key] = row_data

    llm_df = load_latest_llm_rows(llm_results_dir)
    llm_lookup: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    if not llm_df.empty:
        for _, row in llm_df.iterrows():
            relative_folder = normalize_folder(row.get("_relative_folder", "."))
            key = make_lookup_key(
                row.get("group", ""),
                row.get("split", ""),
                relative_folder,
                row.get("image_id", ""),
            )
            row_data = row.to_dict()
            row_data["relative_folder"] = relative_folder
            llm_lookup[key] = row_data

    reviewed_files = sorted(reviewed_root.rglob("*.json")) if reviewed_root.exists() else []
    rows: list[dict[str, Any]] = []

    for reviewed_path in reviewed_files:
        source, split, relative_folder = infer_review_location(reviewed_path, reviewed_root)
        image_id = reviewed_path.stem.replace("_combined", "")
        key = make_lookup_key(source, split, relative_folder, image_id)
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
            "error_type": relative_folder.split("/")[0] if source == "errors" and relative_folder != "." else "",
            "image_path": str(original.get("image_path", "")),
            "original_json_path": str(original.get("json_path", "")),
            "reviewed_json_path": str(reviewed_path),
            "llm_result_csv": str(llm.get("_llm_csv", "")),
            "llm_provider": str(llm.get("llm_provider", "openai" if llm else "")),
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
