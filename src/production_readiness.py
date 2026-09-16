"""Pre-production readiness checks for freezing the 3,000-item work plan."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_quality import summarize_quality, validate_index


def preflight_quality_summary(index_csv: Path, dataset_root: Path | None) -> dict[str, object]:
    """Run data-quality validation and summarize whether production planning is safe.

    A frozen production work plan must only be created after the current dataset index
    passes with zero blocking errors. The returned report is intentionally not persisted
    here; UI callers decide where to save it.
    """
    if not Path(index_csv).exists():
        return {"ready": False, "errors": 0, "warnings": 0, "total": 0, "report": pd.DataFrame(), "reason": "dataset_index_missing"}

    report = validate_index(Path(index_csv), dataset_root)
    summary = summarize_quality(report)
    return {
        "ready": int(summary.get("errors", 0)) == 0,
        "errors": int(summary.get("errors", 0)),
        "warnings": int(summary.get("warnings", 0)),
        "total": int(summary.get("total", 0)),
        "report": report,
        "reason": "" if int(summary.get("errors", 0)) == 0 else "quality_errors",
    }
