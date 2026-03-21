from fastapi import FastAPI

from app.api.routes import api_router
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="NoteMesh API", version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
