from __future__ import annotations

import argparse
from pathlib import Path


def set_env_value(path: Path, key: str, value: str) -> None:
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    prefix = key + "="
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            out.append(prefix + value)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(prefix + value)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--dataset-root", default="")
    parser.add_argument("--reviewer-name", default="")
    args = parser.parse_args()
    path = Path(args.env)
    if args.dataset_root:
        set_env_value(path, "DATASET_ROOT", str(Path(args.dataset_root).expanduser().resolve()))
    if args.reviewer_name:
        set_env_value(path, "REVIEWER_NAME", args.reviewer_name.strip())


if __name__ == "__main__":
    main()
