"""LLM/VLM client wrapper.

현재는 OpenAI Vision API 호출 구조를 기준으로 작성한다.
API Key는 .env에 저장하고 GitHub에는 올리지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

from image_utils import image_to_base64


load_dotenv()


def ask_openai_vision(image_path: str | Path, prompt: str, model: str = "gpt-4o-mini") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    image_path = Path(image_path)
    image_b64 = image_to_base64(image_path)
    mime = "image/jpeg"
    if image_path.suffix.lower() == ".png":
        mime = "image/png"

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_b64}"},
                    },
                ],
            }
        ],
        temperature=0,
    )
    return response.choices[0].message.content or ""
