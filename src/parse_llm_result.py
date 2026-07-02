"""Parse and normalize LLM JSON output."""

from __future__ import annotations

import json
import re
from typing import Any, Dict

LABEL_KEYS = [
    "arti",
    "arti_bu",
    "arti_bu_t",
    "arti_binil",
    "arti_road",
    "arti_roa_m",
    "arti_other",
    "tree",
    "fore",
    "farm",
    "water",
]


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in LLM response")
    return json.loads(match.group(0))


def normalize_result(data: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    result["llm_change"] = int(data.get("change", 0) or 0)
    result["llm_class"] = str(data.get("class", "no_change"))

    for key in LABEL_KEYS:
        result[key] = int(data.get(key, 0) or 0)

    result["reason_ko"] = str(data.get("reason_ko", ""))
    result["reason_en"] = str(data.get("reason_en", ""))
    result["confidence"] = float(data.get("confidence", 0.0) or 0.0)
    result["review_required"] = bool(data.get("review_required", True))
    return result
