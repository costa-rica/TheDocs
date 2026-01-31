import json
import re
from typing import Dict, Optional

from loguru import logger
from openai import OpenAI


class OpenAIService:
    def __init__(self, api_key: Optional[str], model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(api_key=api_key) if api_key else None

    def generate_metadata(self, prompt: str) -> Optional[Dict[str, str]]:
        if not self.client:
            logger.warning("OpenAI API key missing; skipping metadata generation")
            return None

        try:
            response = self.client.responses.create(model=self.model, input=prompt)
            output_text = response.output_text
        except Exception as exc:  # pragma: no cover - network
            logger.error(f"OpenAI request failed: {exc}")
            return None

        if not output_text:
            return None

        parsed = _parse_metadata_output(output_text)
        if not parsed:
            logger.warning("OpenAI response did not contain metadata")
        return parsed


def _parse_metadata_output(text: str) -> Optional[Dict[str, str]]:
    json_block = _extract_json(text)
    if json_block:
        try:
            data = json.loads(json_block)
            title = str(data.get("title", "")).strip()
            description = str(data.get("description", "")).strip()
            if title or description:
                return {"title": title, "description": description}
        except json.JSONDecodeError:
            pass

    title_match = re.search(r"title\s*:\s*(.+)", text, re.IGNORECASE)
    description_match = re.search(r"description\s*:\s*(.+)", text, re.IGNORECASE)
    if title_match or description_match:
        return {
            "title": title_match.group(1).strip() if title_match else "",
            "description": description_match.group(1).strip() if description_match else "",
        }
    return None


def _extract_json(text: str) -> Optional[str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group(0) if match else None
