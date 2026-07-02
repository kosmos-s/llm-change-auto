"""Prompt loading and composition."""

from __future__ import annotations

from pathlib import Path


def load_prompt(path: str | Path) -> str:
    prompt_path = Path(path)
    return prompt_path.read_text(encoding="utf-8")


def build_prompt(base_prompt: str, image_name: str | None = None, original_label: str | None = None) -> str:
    extra = []
    if image_name:
        extra.append(f"이미지 파일명: {image_name}")
    if original_label:
        extra.append(f"기존 라벨 힌트: {original_label}")
    if not extra:
        return base_prompt
    return base_prompt + "\n\n" + "\n".join(extra)
