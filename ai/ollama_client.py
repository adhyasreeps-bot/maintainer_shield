"""
ai/ollama_client.py - Local Ollama LLM Client with Fallback Handling
Member 3 Deliverable: AI & Security Lead.

Handles local inference via Ollama HTTP API (e.g. llama3.2:3b, mistral:7b, qwen2.5-coder).
Ensures zero data is transmitted off the maintainer's host machine.
Includes timeout handling and graceful deterministic fallback if Ollama is unreachable.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
import urllib.request
import urllib.error

from core.schemas import AIReviewResult

logger = logging.getLogger("maintainer_shield.ai.ollama")


class OllamaClient:
    """Client for local Ollama instance with structured JSON generation and fallback."""

    def __init__(
        self,
        host: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: int = 25,
    ):
        self.host = (host or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout_seconds = int(os.environ.get("OLLAMA_TIMEOUT", str(timeout_seconds)))

    def is_available(self) -> bool:
        """Checks if the local Ollama daemon is reachable and responding."""
        try:
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> List[str]:
        """Returns names of models currently available in local Ollama instance."""
        try:
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.debug(f"Failed to fetch Ollama models: {e}")
        return []

    def generate_json(self, prompt: str, system: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Sends prompt to Ollama with format='json' and returns parsed JSON dict.
        Returns None if generation fails or times out.
        """
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,  # Low temperature for deterministic analysis
                "num_predict": 512,
            }
        }
        if system:
            payload["system"] = system

        url = f"{self.host}/api/generate"
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    raw_body = resp.read().decode("utf-8")
                    parsed_resp = json.loads(raw_body)
                    response_text = parsed_resp.get("response", "").strip()

                    # Handle markdown codeblock wrapper if LLM included it
                    if response_text.startswith("```"):
                        lines = response_text.splitlines()
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        response_text = "\n".join(lines).strip()

                    return json.loads(response_text)
        except urllib.error.URLError as e:
            logger.warning(f"Ollama connection error at {self.host}: {e}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Ollama JSON response: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error calling Ollama: {e}")

        return None
