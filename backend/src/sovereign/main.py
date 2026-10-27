import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from sovereign.ai.embeddings import Embedder, FastEmbedEmbedder
from sovereign.ai.gateway import FakeChatModel, Gateway
from sovereign.api import admin_routes, auth_routes, chat_routes, knowledge_routes, org_routes
from sovereign.api.deps import ApiError, Services
from sovereign.config import Settings, get_settings
from sovereign.db import make_engine, make_sessionmaker
from sovereign.storage import LocalStorage, Storage


def create_app(
    settings: Settings | None = None,
    *,
    sessions=None,
    storage: Storage | None = None,
    embedder: Embedder | None = None,
    fake_model: FakeChatModel | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO)

    app = FastAPI(title="SovereignAI", version="0.1.0")
    app.state.services = Services(
        settings=settings,
        sessions=sessions or make_sessionmaker(make_engine(settings.database_url)),
        storage=storage or LocalStorage(settings.storage_dir),
        embedder=embedder or FastEmbedEmbedder(settings.embedding_model),
        gateway=Gateway(settings, fake=fake_model),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []))
        return _error(422, "invalid_request", f"{where}: {first.get('msg', 'invalid')}")

    for module in (auth_routes, org_routes, knowledge_routes, chat_routes, admin_routes):
        app.include_router(module.router)

    @app.get("/healthz", include_in_schema=False)
    def health() -> dict:
        return {"ok": True}

    return app


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)
