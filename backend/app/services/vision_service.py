from __future__ import annotations

import json
import os
from typing import Any, Dict

import httpx

from app.models.schemas import AnalyzeRequest, VisionAnalysisResult

OPENAI_BASE_URL = "https://api.openai.com/v1/responses"


class VisionService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.timeout_seconds = int(os.getenv("OPENAI_TIMEOUT_SECONDS", "25"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))

    async def analyze(self, payload: AnalyzeRequest) -> VisionAnalysisResult:
        if not self.api_key:
            return self._fallback_result()

        content: list[Dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Analyze the clothing in this image and return strict JSON with keys: "
                    "category, colors_hex, material, pattern, formality, style_tags, confidence."
                ),
            }
        ]

        if payload.image_url:
            content.append({"type": "input_image", "image_url": str(payload.image_url)})
        elif payload.image_base64:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{payload.image_base64}",
                }
            )
        else:
            return self._fallback_result()

        body = {
            "model": self.model,
            "input": [{"role": "user", "content": content}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "clothing_analysis",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "category": {"type": "string"},
                            "colors_hex": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "material": {"type": ["string", "null"]},
                            "pattern": {"type": ["string", "null"]},
                            "formality": {"type": ["string", "null"]},
                            "style_tags": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "confidence": {"type": "number"},
                        },
                        "required": [
                            "category",
                            "colors_hex",
                            "material",
                            "pattern",
                            "formality",
                            "style_tags",
                            "confidence",
                        ],
                    },
                    "strict": True,
                }
            },
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}

        for _ in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(OPENAI_BASE_URL, json=body, headers=headers)
                    resp.raise_for_status()
                    parsed = self._extract_json(resp.json())
                    if parsed:
                        return VisionAnalysisResult(**parsed)
            except Exception:
                continue

        return self._fallback_result()

    def _extract_json(self, response_json: Dict[str, Any]) -> Dict[str, Any] | None:
        output = response_json.get("output", [])
        for block in output:
            for item in block.get("content", []):
                if item.get("type") == "output_text":
                    try:
                        return json.loads(item.get("text", "{}"))
                    except json.JSONDecodeError:
                        return None
        return None

    def _fallback_result(self) -> VisionAnalysisResult:
        return VisionAnalysisResult(
            category="unknown",
            colors_hex=[],
            material=None,
            pattern=None,
            formality="casual",
            style_tags=["manual-review"],
            confidence=0.0,
        )
