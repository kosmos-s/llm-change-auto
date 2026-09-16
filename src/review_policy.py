"""Human-review label consistency rules."""

from __future__ import annotations

ARTIFACT_DETAILS = ["arti_bu", "arti_bu_t", "arti_binil", "arti_road", "arti_roa_m", "arti_other"]


def normalize_review_state(state: dict[str, object]) -> dict[str, object]:
    """Return a copy with parent Artifact enabled whenever a detail is enabled."""
    normalized = dict(state)
    if any(bool(normalized.get(key, False)) for key in ARTIFACT_DETAILS):
        normalized["Artifact"] = True
    return normalized


def validation_errors(state: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if any(bool(state.get(key, False)) for key in ARTIFACT_DETAILS) and not bool(state.get("Artifact", False)):
        errors.append("인공물 세부 라벨이 선택되어 있으면 Artifact도 선택되어야 합니다.")
    return errors
