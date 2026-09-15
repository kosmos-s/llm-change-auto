"""OpenAI vision client for aerial-image change detection.

The API key is loaded only from OPENAI_API_KEY in the local environment.
It is never accepted from UI input or written to result files.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from image_utils import image_to_base64


PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "change": {"type": "integer", "enum": [0, 1]},
        "class": {"type": "string"},
        "arti": {"type": "integer", "enum": [0, 1]},
        "arti_bu": {"type": "integer", "enum": [0, 1]},
        "arti_bu_t": {"type": "integer", "enum": [0, 1]},
        "arti_binil": {"type": "integer", "enum": [0, 1]},
        "arti_road": {"type": "integer", "enum": [0, 1]},
        "arti_roa_m": {"type": "integer", "enum": [0, 1]},
        "arti_other": {"type": "integer", "enum": [0, 1]},
        "tree": {"type": "integer", "enum": [0, 1]},
        "fore": {"type": "integer", "enum": [0, 1]},
        "farm": {"type": "integer", "enum": [0, 1]},
        "water": {"type": "integer", "enum": [0, 1]},
        "reason_ko": {"type": "string"},
        "reason_en": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "review_required": {"type": "boolean"},
    },
    "required": [
        "change",
        "class",
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
        "reason_ko",
        "reason_en",
        "confidence",
        "review_required",
    ],
    "additionalProperties": False,
}


def get_mime_type(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def sanitize_error_message(error: Exception | str) -> str:
    """Remove API-key-shaped text before saving or displaying an error."""
    message = str(error)
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        message = message.replace(api_key, "[REDACTED_API_KEY]")

    message = re.sub(
        r"(?i)\b(?:sk|key)[-_][a-z0-9_*.-]{6,}",
        "[REDACTED_API_KEY]",
        message,
    )
    message = re.sub(
        r"(?i)OPENAI_API_KEY\s*=\s*\S+",
        "OPENAI_API_KEY=[REDACTED]",
        message,
    )
    return message


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0
    value = getattr(usage, name, 0)
    try:
        return int(value or 0)
    except Exception:
        return 0


def ask_openai_vision_with_meta(
    image_path: str | Path,
    prompt: str,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """Run one vision request and return text plus token usage metadata."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. 로컬 .env 파일을 확인하세요.")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai 패키지가 설치되지 않았습니다. pip install -r requirements.txt를 실행하세요."
        ) from exc

    image_b64 = image_to_base64(image_path)
    mime_type = get_mime_type(image_path)
    timeout_seconds = float(os.getenv("OPENAI_TIMEOUT", "60"))

    # SDK 자체 재시도는 최소 수준으로 두고, 배치 재시도는 run_llm_labeling.py에서 관리한다.
    client = OpenAI(timeout=timeout_seconds, max_retries=1)
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_b64}",
                        "detail": "high",
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "change_detection_label",
                "strict": True,
                "schema": RESULT_SCHEMA,
            }
        },
        temperature=0,
        max_output_tokens=800,
        store=False,
    )

    output_text = response.output_text or ""
    if not output_text.strip():
        raise RuntimeError("OpenAI 응답에 출력 텍스트가 없습니다.")

    usage = getattr(response, "usage", None)
    input_tokens = _usage_value(usage, "input_tokens")
    output_tokens = _usage_value(usage, "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens") or input_tokens + output_tokens
    return {
        "text": output_text,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "response_id": str(getattr(response, "id", "") or ""),
    }


def ask_openai_vision(
    image_path: str | Path,
    prompt: str,
    model: str = "gpt-4o-mini",
) -> str:
    """Backward-compatible text-only helper."""
    return str(ask_openai_vision_with_meta(image_path, prompt, model=model)["text"])
