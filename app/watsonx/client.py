"""watsonx.ai REST client — ST-08.

Never raises from public methods. Returns None on any failure.
"""
from __future__ import annotations

import base64
import sys
import time
from typing import Optional

import httpx

from app.config import settings

# ---------------------------------------------------------------------------
# Prohibited fields that must never appear in vision responses
# ---------------------------------------------------------------------------

PROHIBITED_VISION_FIELDS = {
    "speed", "speed_mph", "speed_kmh",
    "distance_m", "distance_ft", "distance_km",
    "gps", "lat", "lon", "latitude", "longitude",
    "lane_number", "lane_id",
    "ttc", "time_to_conflict", "time_to_collision",
    "eta", "arrival_time",
}

_IAM_URL = "https://iam.cloud.ibm.com/identity/token"
_GENERATION_PATH = "/ml/v1/text/generation?version=2023-05-29"


class WatsonxClient:
    """REST client for IBM watsonx.ai.

    Provides:
    - generate_text(prompt, system_prompt) → str | None
    - analyze_image(image_path, prompt) → dict | None
    - is_text_available() → bool  (cached after first check)
    - is_vision_available() → bool

    Never raises exceptions — returns None on any failure.
    Logs failures to stderr.
    """

    def __init__(self) -> None:
        self._text_available: Optional[bool] = None  # None = not yet checked
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    # ------------------------------------------------------------------
    # IAM token
    # ------------------------------------------------------------------

    def _get_access_token(self) -> Optional[str]:
        """Exchange IBM API key for IAM access token.

        Caches token until 60 s before expiry. Returns None on failure.
        """
        if not settings.watsonx_api_key:
            return None

        now = time.monotonic()
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token

        try:
            resp = httpx.post(
                _IAM_URL,
                data={
                    "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                    "apikey": settings.watsonx_api_key,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10.0,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._access_token = payload["access_token"]
            self._token_expiry = now + float(payload.get("expires_in", 3600))
            return self._access_token
        except Exception as exc:  # noqa: BLE001
            print(f"[watsonx] IAM token error: {exc}", file=sys.stderr)
            return None

    # ------------------------------------------------------------------
    # Text generation
    # ------------------------------------------------------------------

    def generate_text(
        self,
        prompt: str,
        system_prompt: str = "",
        max_new_tokens: int = 300,
    ) -> Optional[str]:
        """Call watsonx.ai text generation.

        Returns generated text string or None if unavailable/failed.
        """
        if not settings.watsonx_api_key or not settings.watsonx_project_id:
            return None

        token = self._get_access_token()
        if token is None:
            return None

        input_text = (
            f"<|system|>\n{system_prompt}\n<|user|>\n{prompt}\n<|assistant|>"
            if system_prompt
            else prompt
        )

        body = {
            "model_id": settings.watsonx_text_model,
            "project_id": settings.watsonx_project_id,
            "input": input_text,
            "parameters": {
                "max_new_tokens": max_new_tokens,
                "temperature": 0.1,
            },
        }

        try:
            resp = httpx.post(
                settings.watsonx_url + _GENERATION_PATH,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            generated = data["results"][0]["generated_text"]
            # Mark as reachable on first successful call
            self._text_available = True
            return generated.strip()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            print(f"[watsonx] generate_text HTTP error: {exc}", file=sys.stderr)
            self._text_available = False
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[watsonx] generate_text error: {exc}", file=sys.stderr)
            return None

    # ------------------------------------------------------------------
    # Vision / image analysis
    # ------------------------------------------------------------------

    def analyze_image(
        self,
        image_path: str,
        prompt: str,
    ) -> Optional[dict]:
        """Call watsonx Vision model with image + prompt.

        Returns parsed JSON dict or None if unavailable/failed/vision not enabled.
        """
        if not self.is_vision_available():
            return None

        if not settings.watsonx_api_key or not settings.watsonx_project_id:
            return None

        token = self._get_access_token()
        if token is None:
            return None

        # Encode image as base64 data URI
        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            b64 = base64.b64encode(img_bytes).decode("ascii")
            # Guess mime type from extension
            ext = image_path.rsplit(".", 1)[-1].lower()
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
            data_uri = f"data:{mime};base64,{b64}"
        except Exception as exc:  # noqa: BLE001
            print(f"[watsonx] analyze_image file error: {exc}", file=sys.stderr)
            return None

        body = {
            "model_id": settings.watsonx_vision_model,
            "project_id": settings.watsonx_project_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "parameters": {
                "max_new_tokens": 512,
                "temperature": 0.1,
            },
        }

        try:
            resp = httpx.post(
                settings.watsonx_url + _GENERATION_PATH,
                json=body,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=45.0,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["results"][0]["generated_text"].strip()
            return self._parse_json_response(raw_text)
        except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            print(f"[watsonx] analyze_image HTTP error: {exc}", file=sys.stderr)
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"[watsonx] analyze_image error: {exc}", file=sys.stderr)
            return None

    # ------------------------------------------------------------------
    # Availability checks
    # ------------------------------------------------------------------

    def is_text_available(self) -> bool:
        """Check if text generation is configured and reachable.

        Uses cached result after first successful/failed call; otherwise returns
        True when credentials are present (optimistic until first failure).
        """
        if self._text_available is not None:
            return self._text_available
        # If credentials are present, assume available until proven otherwise
        return bool(settings.watsonx_api_key and settings.watsonx_project_id)

    def is_vision_available(self) -> bool:
        """Returns True only if vision is enabled AND vision model is configured."""
        return (
            settings.watsonx_vision_enabled
            and bool(settings.watsonx_vision_model)
            and bool(settings.watsonx_api_key)
            and bool(settings.watsonx_project_id)
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_response(text: str) -> Optional[dict]:
        """Parse a JSON string, stripping markdown code fences if present."""
        import json

        # Strip ```json ... ``` fences
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Remove first and last fence lines
            inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            stripped = "\n".join(inner)

        try:
            result = json.loads(stripped)
            if isinstance(result, dict):
                return result
            print(f"[watsonx] JSON response is not a dict: {type(result)}", file=sys.stderr)
            return None
        except json.JSONDecodeError as exc:
            print(f"[watsonx] JSON parse error: {exc}", file=sys.stderr)
            return None


# Module-level singleton
watsonx_client = WatsonxClient()
