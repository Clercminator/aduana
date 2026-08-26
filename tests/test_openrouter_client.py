import json

import httpx

from app.config import Settings
from app.llm.client import OpenRouterClient
from app.schemas.domain import ClassificationResponse


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


def test_scanned_pdf_reuses_classification_ocr_annotations(tmp_path):
    requests = []
    responses = [
        {
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
                        ),
                        "annotations": [
                            {
                                "type": "file",
                                "file": {
                                    "hash": "ocr-hash",
                                    "name": "document.pdf",
                                    "content": "OCR CONTENT",
                                },
                            }
                        ],
                    }
                }
            ],
        },
        {
            "model": "google/gemini-3.7-flash",
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
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        response = httpx.Response(200, json=responses.pop(0))
        response.request = request
        return response

    pdf_path = tmp_path / "scan.pdf"
    pdf_path.write_bytes(b"synthetic-pdf")
    client = OpenRouterClient(Settings(openrouter_api_key="test-key"))
    client.http.close()
    client.http = httpx.Client(
        base_url="https://openrouter.ai/api/v1", transport=httpx.MockTransport(handler)
    )

    _, classification_body = client.classify_document("", path=pdf_path)
    client.extract_pdf(
        pdf_path,
        "Extract",
        ClassificationResponse,
        ocr=True,
        classification_body=classification_body,
    )

    assert requests[0]["plugins"][0]["pdf"]["engine"] == "mistral-ocr"
    assert "plugins" not in requests[1]
    assert requests[1]["messages"][1]["annotations"][0]["file"]["hash"] == "ocr-hash"
