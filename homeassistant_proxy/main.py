from fastapi import FastAPI

from homeassistant_proxy.api.capabilities import router as capabilities_router
from homeassistant_proxy.api.ha_read import router as ha_read_router
from homeassistant_proxy.api.health import router as health_router
from homeassistant_proxy.core.errors import install_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="Home Assistant GPT Proxy API",
        version="0.1.0",
        description="Narrow proxy between GPT Actions and Home Assistant.",
    )
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(ha_read_router)
    return app


app = create_app()
