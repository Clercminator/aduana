from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.schemas.domain import ClassificationResponse

T = TypeVar("T", bound=BaseModel)
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured")
        self.settings = settings
        self.http = httpx.Client(
            base_url="https://openrouter.ai/api/v1",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            timeout=120,
        )

    def close(self) -> None:
        self.http.close()

    def __enter__(self) -> "OpenRouterClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _completion(self, payload: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        """Retry transient provider failures without changing the requested model."""
        last_problem = "respuesta inválida"
        for attempt in range(5):
            response = self.http.post("/chat/completions", json=payload)
            if response.status_code in RETRYABLE_STATUS_CODES:
                last_problem = f"HTTP {response.status_code}"
            else:
                response.raise_for_status()
                body = response.json()
                choices = body.get("choices")
                if choices and isinstance(choices, list):
                    return body, choices[0].get("message", {}).get("content", "")
                error = body.get("error")
                last_problem = (
                    str(error.get("message"))
                    if isinstance(error, dict) and error.get("message")
                    else "respuesta sin choices"
                )
            if attempt < 4:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = min(float(retry_after), 60.0) if retry_after else 2**attempt
                except ValueError:
                    delay = 2**attempt
                time.sleep(delay)
        raise RuntimeError(f"OpenRouter no respondió después de 5 intentos: {last_problem}")

    def extract_pdf(
        self, path: Path, prompt: str, schema: type[T], ocr: bool = False
    ) -> tuple[T, dict]:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = {
            "model": self.settings.extract_model,
            "max_tokens": self.settings.extract_max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "file",
                            "file": {
                                "filename": path.name,
                                "file_data": f"data:application/pdf;base64,{encoded}",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "plugins": [
                {"id": "file-parser", "pdf": {"engine": "mistral-ocr" if ocr else "native"}}
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
            "provider": {"require_parameters": True},
        }
        body, content = self._completion(payload)
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            parsed = schema.model_validate_json(content)
        except ValidationError as first_error:
            payload["messages"].append({"role": "assistant", "content": content})
            payload["messages"].append(
                {
                    "role": "user",
                    "content": f"Corrige solamente el JSON. Error de validación: {first_error}",
                }
            )
            body, corrected_content = self._completion(payload)
            parsed = schema.model_validate_json(corrected_content)
        return parsed, body

    def classify_document(
        self, text: str, path: Path | None = None
    ) -> tuple[ClassificationResponse, dict]:
        prompt = (
            "Clasifica el contenido, sin usar el nombre del archivo. Responde con uno de: "
            "dispatch_instruction, bill_of_lading, commercial_invoice, packing_list, "
            "insurance_certificate, certificate_of_origin, unknown. confidence debe ser "
            "una cadena decimal y evidence una cita literal breve del contenido."
        )
        if path is None:
            content: str | list[dict] = f"{prompt}\n\nCONTENIDO:\n{text[:50000]}"
            plugins = None
        else:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            content = [
                {
                    "type": "file",
                    "file": {
                        "filename": "document.pdf",
                        "file_data": f"data:application/pdf;base64,{encoded}",
                    },
                },
                {"type": "text", "text": prompt},
            ]
            plugins = [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}]
        payload = {
            "model": self.settings.classify_model,
            "max_tokens": 300,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "document_classification",
                    "strict": True,
                    "schema": ClassificationResponse.model_json_schema(),
                },
            },
            "provider": {"require_parameters": True},
        }
        if plugins:
            payload["plugins"] = plugins
        body, content_value = self._completion(payload)
        if isinstance(content_value, list):
            content_value = "".join(
                part.get("text", "") for part in content_value if isinstance(part, dict)
            )
        return ClassificationResponse.model_validate_json(content_value), body

    @staticmethod
    def usage(body: dict) -> dict:
        usage = body.get("usage", {})
        return {
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "cost_usd": str(usage.get("cost", body.get("usage_cost", 0)) or 0),
            "provider": body.get("provider"),
            "model": body.get("model"),
            "raw": body,
        }
