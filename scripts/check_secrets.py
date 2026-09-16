"""Fail CI when likely API secrets are committed to tracked project files."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "env", "outputs", "logs", "__pycache__", ".ipynb_checkpoints"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".bat", ".ps1", ".example", ""}
PATTERNS = [
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("Bearer token", re.compile(r"(?i)authorization\s*[:=]\s*bearer\s+[A-Za-z0-9._-]{20,}")),
]


def should_scan(path: Path) -> bool:
    if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
        return False
    if path.name == ".env":
        return False
    return path.is_file() and (path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile", "Makefile"})


def main() -> int:
    findings: list[str] = []
    for path in ROOT.rglob("*"):
        if not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in PATTERNS:
            if pattern.search(text):
                findings.append(f"{name}: {path.relative_to(ROOT)}")

    if findings:
        print("Potential secrets found:")
        for finding in findings:
            print(f"- {finding}")
        return 1

    print("Secret scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
