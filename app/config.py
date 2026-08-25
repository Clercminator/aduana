from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://aduanera:aduanera@localhost:5432/aduanera"
    openrouter_api_key: str | None = None
    classify_model: str = "google/gemini-3.5-flash-lite"
    extract_model: str = "google/gemini-3.7-flash"
    extract_max_tokens: int = Field(default=12000, ge=1000, le=64000)
    extraction_backend: str = "auto"
    document_root: Path = Path("data/documents")
    artifact_root: Path = Path("data/artifacts")
    fixture_root: Path = Path("fixtures")
    jurisdiction_root: Path = Path("jurisdictions")
    client_root: Path = Path("clients")
    agency_root: Path = Path("agencies")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    demo_fx_rate: str = "963.45"
    demo_fx_source: str = "dólar aduanero mensual ficticio del demo"
    demo_fx_date: str = "2026-08-01"
    demo_din_acceptance_date: str = "2026-08-18"
    demo_org_id: str = "00000000-0000-0000-0000-000000000001"
    poll_seconds: float = Field(default=0.5, gt=0)
    document_concurrency: int = Field(default=4, ge=1, le=12)
    max_upload_files: int = Field(default=60, ge=1, le=500)
    max_upload_file_bytes: int = Field(default=25 * 1024 * 1024, ge=1024)
    max_upload_batch_bytes: int = Field(default=250 * 1024 * 1024, ge=1024)
    max_pdf_pages: int = Field(default=200, ge=1, le=5000)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
