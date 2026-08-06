"""Security-focused tests for the OpenAI client wrapper."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from llm_client import sanitize_error_message


class SanitizeErrorMessageTest(unittest.TestCase):
    def test_redacts_exact_environment_key(self) -> None:
        previous = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "sk-proj-secret-example-123456"
        try:
            result = sanitize_error_message(
                "Incorrect API key: sk-proj-secret-example-123456"
            )
        finally:
            if previous is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = previous

        self.assertNotIn("sk-proj-secret-example-123456", result)
        self.assertIn("[REDACTED_API_KEY]", result)

    def test_redacts_masked_key_from_api_error(self) -> None:
        result = sanitize_error_message(
            "Incorrect API key provided: key_f2vp********yKID"
        )

        self.assertNotIn("key_f2vp", result)
        self.assertIn("[REDACTED_API_KEY]", result)


if __name__ == "__main__":
    unittest.main()
