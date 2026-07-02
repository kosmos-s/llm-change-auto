"""통합 UI 실행용 호환 파일.

예전처럼 이 파일을 열고 Ctrl + F5를 눌러도
검수 UI와 LLM 자동화 UI가 합쳐진 통합 앱이 실행됩니다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "app" / "main_app.py"


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", str(APP_PATH)])
    )
