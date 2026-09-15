"""Run OpenAI labeling for scanned dataset rows.

Large-batch safety features:
- saves after every image,
- resumes from an existing result CSV,
- skips already completed rows,
- retries transient failures with exponential backoff,
- can retry only failed rows,
- writes a checkpoint JSON after every row,
- records token usage, run/batch IDs and configurable cost estimates.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from tqdm import tqdm

from llm_client import ask_openai_vision_with_meta, sanitize_error_message
from parse_llm_result import extract_json, normalize_result
from prompt_builder import build_prompt, load_prompt


ProgressCallback = Callable[[dict[str, Any]], None]


def normalize_folder(value: object) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or text.lower() == "nan" or text == ".":
        return "."
    return text.strip("/") or "."


def row_key(row: pd.Series | dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("group", "")).strip().lower(),
            str(row.get("split", "")).strip().lower(),
            normalize_folder(row.get("relative_folder", ".")).lower(),
            str(row.get("image_id", "")).strip(),
        ]
    )


def reviewed_json_exists(row: pd.Series, reviewed_root: Path | None) -> bool:
    if reviewed_root is None:
        return False
    source = str(row.get("group", "")).strip() or "unknown"
    split = str(row.get("split", "")).strip() or "unknown"
    folder = normalize_folder(row.get("relative_folder", "."))
    json_path = Path(str(row.get("json_path", "")))
    if not json_path.name:
        return False
    target = reviewed_root / source / split
    if folder != ".":
        target = target / Path(folder)
    return (target / json_path.name).exists()


def _balanced_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "error_type" not in df.columns:
        return df.reset_index(drop=True)
    groups = [group.reset_index(drop=True) for _, group in df.groupby("error_type", dropna=False, sort=True)]
    rows: list[pd.Series] = []
    index = 0
    while groups:
        next_groups = []
        for group in groups:
            if index < len(group):
                rows.append(group.iloc[index])
            if index + 1 < len(group):
                next_groups.append(group)
        groups = next_groups
        index += 1
    return pd.DataFrame(rows).reset_index(drop=True) if rows else df.iloc[0:0].copy()


def filter_dataframe(
    df: pd.DataFrame,
    source: str = "dataset",
    split: str = "test",
    start: int = 0,
    limit: int | None = None,
    error_types: list[str] | None = None,
    selection_mode: str = "sequential",
    random_seed: int = 42,
    exclude_reviewed_root: Path | None = None,
) -> pd.DataFrame:
    """Select a stable batch, then optionally remove already-reviewed items.

    Important: `start/limit` are applied before reviewed-item exclusion so batch ranges do
    not shift as human reviews accumulate between runs.
    """
    filtered = df.copy()

    if source != "all" and "group" in filtered.columns:
        filtered = filtered[filtered["group"].astype(str).str.lower() == source.lower()]
    if split != "all" and "split" in filtered.columns:
        filtered = filtered[filtered["split"].astype(str).str.lower() == split.lower()]
    if error_types and "error_type" in filtered.columns:
        wanted = {str(v).strip() for v in error_types if str(v).strip()}
        if wanted:
            filtered = filtered[filtered["error_type"].fillna("").astype(str).isin(wanted)]

    filtered = filtered.reset_index(drop=True)
    if selection_mode == "random" and not filtered.empty:
        filtered = filtered.sample(frac=1.0, random_state=random_seed).reset_index(drop=True)
    elif selection_mode == "balanced":
        filtered = _balanced_rows(filtered)

    if start:
        filtered = filtered.iloc[start:].reset_index(drop=True)
    if limit:
        filtered = filtered.head(limit).reset_index(drop=True)

    if exclude_reviewed_root is not None and not filtered.empty:
        keep_mask = [not reviewed_json_exists(row, exclude_reviewed_root) for _, row in filtered.iterrows()]
        filtered = filtered[pd.Series(keep_mask, index=filtered.index)].reset_index(drop=True)

    return filtered.reset_index(drop=True)


def _atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8-sig")
    os.replace(tmp, path)


def _atomic_write_json(data: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df.copy()
    df["_row_key"] = df.apply(row_key, axis=1)
    return df


def _upsert(existing: pd.DataFrame, row: dict[str, Any]) -> pd.DataFrame:
    new = pd.DataFrame([row])
    new["_row_key"] = new.apply(row_key, axis=1)
    if existing.empty:
        merged = new
    else:
        base = existing.copy()
        if "_row_key" not in base.columns:
            base["_row_key"] = base.apply(row_key, axis=1)
        merged = pd.concat([base, new], ignore_index=True, sort=False)
        merged = merged.drop_duplicates(subset=["_row_key"], keep="last")
    return merged.reset_index(drop=True)


def _public_frame(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=["_row_key"], errors="ignore")


def _estimated_cost(input_tokens: int, output_tokens: int, input_price_per_million: float, output_price_per_million: float) -> float:
    return (input_tokens / 1_000_000.0) * input_price_per_million + (output_tokens / 1_000_000.0) * output_price_per_million


def _totals(df: pd.DataFrame) -> tuple[float, int, int, int]:
    if df.empty:
        return 0.0, 0, 0, 0
    cost = float(pd.to_numeric(df.get("estimated_cost_usd", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    input_tokens = int(pd.to_numeric(df.get("input_tokens", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    output_tokens = int(pd.to_numeric(df.get("output_tokens", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    if "error" in df.columns:
        error_count = int(df["error"].fillna("").astype(str).str.strip().ne("").sum())
    else:
        error_count = 0
    return cost, input_tokens, output_tokens, error_count


def run(
    input_csv: Path,
    prompt_path: Path,
    output_csv: Path,
    source: str = "dataset",
    split: str = "test",
    start: int = 0,
    limit: int | None = None,
    model: str = "gpt-4o-mini",
    progress_callback: ProgressCallback | None = None,
    *,
    resume: bool = True,
    retry_failed: bool = True,
    retry_errors_only: bool = False,
    max_attempts: int = 3,
    retry_backoff_seconds: float = 2.0,
    checkpoint_path: Path | None = None,
    run_id: str = "",
    batch_id: str = "",
    work_mode: str = "production",
    error_types: list[str] | None = None,
    selection_mode: str = "sequential",
    random_seed: int = 42,
    exclude_reviewed_root: Path | None = None,
    input_price_per_million: float = 0.0,
    output_price_per_million: float = 0.0,
    cost_limit_usd: float = 0.0,
) -> pd.DataFrame:
    df = pd.read_csv(input_csv)
    df = filter_dataframe(
        df,
        source=source,
        split=split,
        start=start,
        limit=limit,
        error_types=error_types,
        selection_mode=selection_mode,
        random_seed=random_seed,
        exclude_reviewed_root=exclude_reviewed_root,
    )
    if df.empty:
        raise ValueError(f"OpenAI 실행 대상이 없습니다. source={source}, split={split}, input={input_csv}")

    base_prompt = load_prompt(prompt_path)
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_id = batch_id or f"{source}_{split}_{start}_{limit or 'all'}"
    checkpoint_path = checkpoint_path or output_csv.with_suffix(".checkpoint.json")

    existing = _load_existing(output_csv) if resume or retry_errors_only else pd.DataFrame()
    existing_lookup: dict[str, dict[str, Any]] = {}
    if not existing.empty:
        for _, row in existing.iterrows():
            existing_lookup[str(row["_row_key"])] = row.to_dict()

    selected_total = len(df)
    work_rows: list[pd.Series] = []
    already_complete = 0
    for _, row in df.iterrows():
        key = row_key(row)
        previous = existing_lookup.get(key)
        if previous is None:
            if not retry_errors_only:
                work_rows.append(row)
            continue
        previous_error = str(previous.get("error", "") or "").strip()
        if previous_error:
            if retry_failed or retry_errors_only:
                work_rows.append(row)
            else:
                already_complete += 1
        else:
            already_complete += 1

    if retry_errors_only and not work_rows:
        raise ValueError("현재 결과 CSV에서 재시도할 실패 항목이 없습니다.")

    total_to_run = len(work_rows)
    cumulative_cost, cumulative_input_tokens, cumulative_output_tokens, current_errors = _totals(_public_frame(existing))
    started = time.monotonic()
    stop_reason = ""

    def notify(completed_this_run: int, image_id: str = "") -> None:
        if progress_callback is None:
            return
        elapsed = max(time.monotonic() - started, 0.001)
        rate = completed_this_run / elapsed if completed_this_run else 0.0
        remaining = max(total_to_run - completed_this_run, 0)
        eta = remaining / rate if rate > 0 else 0.0
        progress_callback(
            {
                "completed_this_run": completed_this_run,
                "total_to_run": total_to_run,
                "selected_total": selected_total,
                "already_complete": already_complete,
                "remaining": remaining,
                "image_id": image_id,
                "error_count": current_errors,
                "elapsed_seconds": elapsed,
                "eta_seconds": eta,
                "items_per_minute": rate * 60.0,
                "estimated_cost_usd": cumulative_cost,
                "input_tokens": cumulative_input_tokens,
                "output_tokens": cumulative_output_tokens,
                "stop_reason": stop_reason,
                "batch_id": batch_id,
                "run_id": run_id,
            }
        )

    notify(0)
    completed_this_run = 0

    for row in tqdm(work_rows, total=total_to_run):
        image_path = str(row["image_path"])
        image_id = str(row.get("image_id", Path(image_path).stem))

        if cost_limit_usd > 0 and cumulative_cost >= cost_limit_usd:
            stop_reason = f"cost_limit_usd={cost_limit_usd:.4f} 도달"
            break

        prompt = build_prompt(base_prompt, row.get("image_name"), None)
        result_row = row.to_dict()
        result_row.update(
            {
                "llm_provider": "openai",
                "llm_model": model,
                "prompt_path": str(prompt_path),
                "run_id": run_id,
                "batch_id": batch_id,
                "work_mode": work_mode,
                "processed_at": datetime.now().isoformat(timespec="seconds"),
                "selection_mode": selection_mode,
            }
        )

        last_error = ""
        success = False
        meta: dict[str, Any] = {}
        attempt = 0
        for attempt in range(1, max(1, max_attempts) + 1):
            try:
                meta = ask_openai_vision_with_meta(image_path, prompt, model=model)
                raw_text = str(meta.get("text", ""))
                parsed = normalize_result(extract_json(raw_text))
                result_row.update(parsed)
                result_row["raw_response"] = raw_text
                result_row["error"] = ""
                success = True
                break
            except Exception as exc:
                last_error = sanitize_error_message(exc)
                if attempt < max(1, max_attempts):
                    time.sleep(max(retry_backoff_seconds, 0.0) * (2 ** (attempt - 1)))

        input_tokens = int(meta.get("input_tokens", 0) or 0)
        output_tokens = int(meta.get("output_tokens", 0) or 0)
        total_tokens = int(meta.get("total_tokens", input_tokens + output_tokens) or 0)
        row_cost = _estimated_cost(input_tokens, output_tokens, input_price_per_million, output_price_per_million)

        result_row["attempt_count"] = attempt
        result_row["input_tokens"] = input_tokens
        result_row["output_tokens"] = output_tokens
        result_row["total_tokens"] = total_tokens
        result_row["estimated_cost_usd"] = row_cost
        result_row["response_id"] = str(meta.get("response_id", ""))

        if not success:
            result_row["raw_response"] = ""
            result_row["error"] = last_error
            result_row["llm_change"] = 0
            result_row["llm_class"] = "error"
            result_row["confidence"] = 0.0
            result_row["review_required"] = True

        existing = _upsert(existing, result_row)
        public = _public_frame(existing)
        _atomic_write_csv(public, output_csv)
        cumulative_cost, cumulative_input_tokens, cumulative_output_tokens, current_errors = _totals(public)
        completed_this_run += 1

        checkpoint = {
            "status": "running",
            "run_id": run_id,
            "batch_id": batch_id,
            "work_mode": work_mode,
            "source": source,
            "split": split,
            "start": start,
            "limit": limit,
            "selection_mode": selection_mode,
            "error_types": error_types or [],
            "selected_total": selected_total,
            "already_complete": already_complete,
            "completed_this_run": completed_this_run,
            "total_to_run": total_to_run,
            "last_image_id": image_id,
            "error_count": current_errors,
            "estimated_cost_usd": cumulative_cost,
            "input_tokens": cumulative_input_tokens,
            "output_tokens": cumulative_output_tokens,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        _atomic_write_json(checkpoint, checkpoint_path)
        notify(completed_this_run, image_id)

    status = "completed" if not stop_reason and completed_this_run >= total_to_run else "stopped"
    final_checkpoint = {
        "status": status,
        "stop_reason": stop_reason,
        "run_id": run_id,
        "batch_id": batch_id,
        "work_mode": work_mode,
        "source": source,
        "split": split,
        "start": start,
        "limit": limit,
        "selected_total": selected_total,
        "already_complete": already_complete,
        "completed_this_run": completed_this_run,
        "total_to_run": total_to_run,
        "error_count": current_errors,
        "estimated_cost_usd": cumulative_cost,
        "input_tokens": cumulative_input_tokens,
        "output_tokens": cumulative_output_tokens,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _atomic_write_json(final_checkpoint, checkpoint_path)
    notify(completed_this_run)

    result = _public_frame(existing)
    print(
        f"provider=openai model={model} source={source} split={split} selected={selected_total} "
        f"processed={completed_this_run} already_complete={already_complete} status={status} saved={output_csv}"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="outputs/dataset_index.csv")
    parser.add_argument("--prompt", default="prompts/prompt_v4_quality.txt")
    parser.add_argument("--output", default="outputs/llm_results/openai_results.csv")
    parser.add_argument("--source", choices=["dataset", "errors", "all"], default="dataset")
    parser.add_argument("--split", choices=["test", "train", "val", "all"], default="test")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--retry-errors-only", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--selection-mode", choices=["sequential", "random", "balanced"], default="sequential")
    parser.add_argument("--exclude-reviewed", default="outputs/reviewed_json")
    parser.add_argument("--input-price", type=float, default=float(os.getenv("OPENAI_INPUT_PRICE_PER_1M", "0") or 0))
    parser.add_argument("--output-price", type=float, default=float(os.getenv("OPENAI_OUTPUT_PRICE_PER_1M", "0") or 0))
    parser.add_argument("--cost-limit", type=float, default=0.0)
    args = parser.parse_args()

    run(
        input_csv=Path(args.input),
        prompt_path=Path(args.prompt),
        output_csv=Path(args.output),
        source=args.source,
        split=args.split,
        start=args.start,
        limit=args.limit,
        model=args.model,
        resume=not args.no_resume,
        retry_errors_only=bool(args.retry_errors_only),
        max_attempts=args.max_attempts,
        selection_mode=args.selection_mode,
        exclude_reviewed_root=Path(args.exclude_reviewed) if args.exclude_reviewed else None,
        input_price_per_million=args.input_price,
        output_price_per_million=args.output_price,
        cost_limit_usd=args.cost_limit,
    )


if __name__ == "__main__":
    main()
