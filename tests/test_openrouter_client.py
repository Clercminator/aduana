import json

import httpx

from app.config import Settings
from app.llm.client import OpenRouterClient


def test_classification_retries_transient_and_malformed_responses(monkeypatch):
    responses = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"error": {"message": "provider response incomplete"}}),
        httpx.Response(
            200,
            json={
                "model": "google/gemini-3.5-flash-lite",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "doc_type": "commercial_invoice",
                                    "confidence": "0.99",
                                    "evidence": "COMMERCIAL INVOICE",
                                }
                            )
                        }
                    }
                ],
            },
        ),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        response = responses.pop(0)
        response.request = request
        return response

    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    client.http.close()
    client.http = httpx.Client(
        base_url="https://openrouter.ai/api/v1", transport=httpx.MockTransport(handler)
    )
    monkeypatch.setattr("app.llm.client.time.sleep", lambda _: None)

    result, body = client.classify_document("COMMERCIAL INVOICE")

    assert result.doc_type.value == "commercial_invoice"
    assert body["model"] == "google/gemini-3.5-flash-lite"
    assert responses == []
