"""LLM 자동화 UI 실행용 파일.

VS Code에서 이 파일을 열고 Ctrl + F5를 누르면 LLM 자동화 UI가 실행됩니다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app" / "llm_pipeline_app.py"


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(APP_PATH)])
    )
