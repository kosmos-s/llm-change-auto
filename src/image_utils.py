"""Image utility functions for LLM/VLM input."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Tuple
from PIL import Image


def image_to_base64(path: str | Path) -> str:
    image_path = Path(path)
    with image_path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_size(path: str | Path) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def validate_image(path: str | Path) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False
