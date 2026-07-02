"""Read and write label JSON files for the verifier UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ARTIFACT_DETAIL_KEYS = [
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
]

REASON_KO_KEYS = ["reason_ko", "reason_KO", "reasonKo", "reason_kor", "reasonKor", "reason_kr"]


def bool_to_ox(value: bool) -> str:
    return "o" if value else "x"


def ox_to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"o", "1", "true", "yes", "y"}


def first_text(data: dict[str, Any], keys: list[str], default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return default


def has_korean_reason(data: dict[str, Any]) -> bool:
    return bool(first_text(data, REASON_KO_KEYS, ""))


def load_json(path: str | Path) -> dict[str, Any]:
    json_path = Path(path)
    if not json_path.exists():
        return make_empty_label_json()
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return json.loads(json_path.read_text(encoding="cp949"))


def save_json(path: str | Path, data: dict[str, Any]) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make_empty_label_json() -> dict[str, Any]:
    return {
        "Artifact": "x",
        "Tree": "x",
        "forest": "x",
        "farmland": "x",
        "water": "x",
        "reason": "",
        "reason_ko": "",
        "artifact_detail": {key: "x" for key in ARTIFACT_DETAIL_KEYS},
    }


def get_label_state(data: dict[str, Any]) -> dict[str, bool | str]:
    artifact_detail = data.get("artifact_detail", {}) or {}
    return {
        "Artifact": ox_to_bool(data.get("Artifact", "x")),
        "Tree": ox_to_bool(data.get("Tree", "x")),
        "forest": ox_to_bool(data.get("forest", "x")),
        "farmland": ox_to_bool(data.get("farmland", "x")),
        "water": ox_to_bool(data.get("water", "x")),
        "arti_bu": ox_to_bool(artifact_detail.get("arti_bu", "x")),
        "arti_bu_t": ox_to_bool(artifact_detail.get("arti_bu_t", "x")),
        "arti_binil": ox_to_bool(artifact_detail.get("arti_binil", "x")),
        "arti_road": ox_to_bool(artifact_detail.get("arti_road", "x")),
        "arti_roa_m": ox_to_bool(artifact_detail.get("arti_roa_m", "x")),
        "arti_other": ox_to_bool(artifact_detail.get("arti_other", "x")),
        "reason": first_text(data, ["reason"], ""),
        "reason_ko": first_text(data, REASON_KO_KEYS, ""),
    }


def update_label_json(data: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    new_data = dict(data)

    detail = dict(new_data.get("artifact_detail", {}) or {})
    has_artifact_detail = False
    for key in ARTIFACT_DETAIL_KEYS:
        checked = bool(state.get(key, False))
        has_artifact_detail = has_artifact_detail or checked
        detail[key] = bool_to_ox(checked)

    # 세부 인공물 라벨이 하나라도 체크되면 상위 Artifact도 자동으로 o 처리한다.
    artifact_checked = bool(state.get("Artifact", False)) or has_artifact_detail
    new_data["Artifact"] = bool_to_ox(artifact_checked)
    new_data["Tree"] = bool_to_ox(bool(state.get("Tree", False)))
    new_data["forest"] = bool_to_ox(bool(state.get("forest", False)))
    new_data["farmland"] = bool_to_ox(bool(state.get("farmland", False)))
    new_data["water"] = bool_to_ox(bool(state.get("water", False)))
    new_data["reason"] = str(state.get("reason", ""))
    new_data["reason_ko"] = str(state.get("reason_ko", ""))
    new_data["artifact_detail"] = detail
    return new_data
