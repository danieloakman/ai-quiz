"""Minimal OpenAI-compatible chat completions client."""

from __future__ import annotations

import json
from typing import Any

import httpx

from quiz_host.errors import QuizHostError


class OpenAICompatClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.4,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(
                timeout=self.timeout, transport=self._transport
            ) as client:
                resp = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise QuizHostError(f"LLM HTTP error: {exc}") from exc

        if resp.status_code >= 400:
            raise QuizHostError(
                f"LLM request failed ({resp.status_code}): {resp.text[:400]}"
            )
        try:
            payload = resp.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise QuizHostError(
                "LLM response missing choices[0].message.content."
            ) from exc
        if not isinstance(content, str):
            raise QuizHostError("LLM content was not a string.")
        return content
