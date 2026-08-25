from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db.session import session_factory
from app.services.bootstrap import ensure_demo_records


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.document_root.mkdir(parents=True, exist_ok=True)
    with session_factory()() as db:
        ensure_demo_records(db, settings)
    yield


settings = get_settings()
app = FastAPI(title="Automatización Aduanera Demo", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
