"""Run LLM labeling for scanned dataset rows.

Example:
    python src/run_llm_labeling.py --input outputs/dataset_index.csv --source dataset --split test --limit 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from llm_client import ask_openai_vision
from parse_llm_result import extract_json, normalize_result
from prompt_builder import load_prompt, build_prompt


def filter_dataframe(df: pd.DataFrame, source: str = "dataset", split: str = "test", start: int = 0, limit: int | None = None) -> pd.DataFrame:
    filtered = df.copy()

    # scan_dataset.py에서는 dataset/errors 구분 컬럼명이 group이다.
    if source != "all" and "group" in filtered.columns:
        filtered = filtered[filtered["group"].astype(str).str.lower() == source.lower()]

    if split != "all" and "split" in filtered.columns:
        filtered = filtered[filtered["split"].astype(str).str.lower() == split.lower()]

    filtered = filtered.reset_index(drop=True)
    if start:
        filtered = filtered.iloc[start:]
    if limit:
        filtered = filtered.head(limit)
    return filtered.reset_index(drop=True)


def run(
    input_csv: Path,
    prompt_path: Path,
    output_csv: Path,
    source: str = "dataset",
    split: str = "test",
    start: int = 0,
    limit: int | None = None,
    model: str = "gpt-4o-mini",
) -> None:
    df = pd.read_csv(input_csv)
    df = filter_dataframe(df, source=source, split=split, start=start, limit=limit)

    if df.empty:
        raise ValueError(f"LLM 실행 대상이 없습니다. source={source}, split={split}, input={input_csv}")

    base_prompt = load_prompt(prompt_path)
    rows = []

    for _, row in tqdm(df.iterrows(), total=len(df)):
        image_path = row["image_path"]
        # 기존 정답 라벨은 LLM에 제공하지 않는다. 파일명만 힌트로 전달한다.
        prompt = build_prompt(base_prompt, row.get("image_name"), None)
        result_row = row.to_dict()
        result_row["llm_model"] = model
        result_row["prompt_path"] = str(prompt_path)
        try:
            raw_text = ask_openai_vision(image_path, prompt, model=model)
            parsed = normalize_result(extract_json(raw_text))
            result_row.update(parsed)
            result_row["raw_response"] = raw_text
            result_row["error"] = ""
        except Exception as exc:
            result_row["raw_response"] = ""
            result_row["error"] = str(exc)
            result_row["llm_change"] = 0
            result_row["llm_class"] = "error"
            result_row["confidence"] = 0.0
            result_row["review_required"] = True
        rows.append(result_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"source={source} split={split} rows={len(rows)} saved={output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="outputs/dataset_index.csv")
    parser.add_argument("--prompt", default="prompts/prompt_v3_json_strict.txt")
    parser.add_argument("--output", default="outputs/llm_results/llm_results.csv")
    parser.add_argument("--source", choices=["dataset", "errors", "all"], default="dataset")
    parser.add_argument("--split", choices=["test", "train", "val", "all"], default="test")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default="gpt-4o-mini")
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
    )


if __name__ == "__main__":
    main()
