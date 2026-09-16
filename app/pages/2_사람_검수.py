"""Multipage wrapper for reviewer_app.py with portable defaults."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_DIR.parent
SRC_DIR = PROJECT_ROOT / "src"
for path in [APP_DIR, SRC_DIR]:
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from project_paths import dataset_root_default, ensure_output_dirs

load_dotenv(PROJECT_ROOT / ".env")
outputs = ensure_output_dirs(PROJECT_ROOT)

st.session_state.setdefault("loaded_root", str(dataset_root_default(PROJECT_ROOT)))
review_files = sorted((outputs / "review_lists").glob("*_review.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
if review_files:
    st.session_state.setdefault("loaded_review_csv", str(review_files[0]))

import reviewer_app

reviewer_app.main()
