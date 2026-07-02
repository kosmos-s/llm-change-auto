"""Run LLM labeling for scanned dataset rows."""

from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
from tqdm import tqdm

from llm_client import ask_openai_vision
from parse_llm_result import extract_json, normalize_result
from prompt_builder import load_prompt, build_prompt


def run(input_csv: Path, prompt_path: Path, output_csv: Path, limit: int | None = None) -> None:
    df = pd.read_csv(input_csv)
    if limit:
        df = df.head(limit)

    base_prompt = load_prompt(prompt_path)
    rows = []

    for _, row in tqdm(df.iterrows(), total=len(df)):
        image_path = row["image_path"]
        prompt = build_prompt(base_prompt, row.get("image_name"), row.get("original_label"))
        result_row = row.to_dict()
        try:
            raw_text = ask_openai_vision(image_path, prompt)
            parsed = normalize_result(extract_json(raw_text))
            result_row.update(parsed)
            result_row["raw_response"] = raw_text
            result_row["error"] = ""
        except Exception as exc:
            result_row["raw_response"] = ""
            result_row["error"] = str(exc)
            result_row["review_required"] = True
        rows.append(result_row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"saved={output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="outputs/dataset_index.csv")
    parser.add_argument("--prompt", default="prompts/prompt_v3_json_strict.txt")
    parser.add_argument("--output", default="outputs/llm_results/llm_results.csv")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    run(Path(args.input), Path(args.prompt), Path(args.output), args.limit)


if __name__ == "__main__":
    main()
