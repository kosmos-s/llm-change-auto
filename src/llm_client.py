"""LLM/VLM client wrapper.

OpenAI와 Gemini를 모두 지원한다.
API Key는 .env에 저장하고 GitHub에는 올리지 않는다.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from image_utils import image_to_base64


load_dotenv()


def get_mime_type(image_path: Path) -> str:
    suffix = image_path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/jpeg"


def ask_vision(image_path: str | Path, prompt: str, model: str, provider: str = "gemini") -> str:
    provider = provider.lower().strip()
    if provider == "gemini":
        return ask_gemini_vision(image_path, prompt, model=model)
    if provider == "openai":
        return ask_openai_vision(image_path, prompt, model=model)
    raise ValueError(f"지원하지 않는 provider입니다: {provider}")


def ask_gemini_vision(image_path: str | Path, prompt: str, model: str = "gemini-2.5-flash") -> str:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    image_b64 = image_to_base64(image_path)
    mime = get_mime_type(image_path)
    timeout_sec = int(os.getenv("GEMINI_TIMEOUT", "60"))

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime,
                            "data": image_b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "response_mime_type": "application/json",
        },
    }
    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=timeout_sec,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Gemini API 오류 {response.status_code}: {response.text[:1000]}")

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini 응답에 candidates가 없습니다: {data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "") for part in parts if part.get("text")]
    if not texts:
        raise RuntimeError(f"Gemini 응답에 text가 없습니다: {data}")
    return "\n".join(texts)


def ask_openai_vision(image_path: str | Path, prompt: str, model: str = "gpt-4o-mini") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai가 설치되지 않았습니다. pip install -r requirements.txt를 실행하세요.") from exc

    image_b64 = image_to_base64(image_path)
    mime = get_mime_type(image_path)

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
                        "image_url": {
                            "url": f"data:{mime};base64,{image_b64}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""
