"""Multipage wrapper for llm_pipeline_app.py."""

from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import llm_pipeline_app

llm_pipeline_app.PROMPT_OPTIONS = [
    "prompts/prompt_v4_target85.txt",
    "prompts/prompt_v3_json_strict.txt",
    "prompts/prompt_v2_guideline.txt",
    "prompts/prompt_v1_basic.txt",
]

llm_pipeline_app.main()
