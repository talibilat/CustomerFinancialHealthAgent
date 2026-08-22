from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from customer_financial_health_api.api.routers import health, overview
from customer_financial_health_api.settings import get_settings


def create_app() -> FastAPI:
    app = FastAPI(title="Customer Financial Health API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[get_settings().frontend_origin],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(overview.router)
    return app


app = create_app()
