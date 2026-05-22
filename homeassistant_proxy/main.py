from fastapi import FastAPI

from homeassistant_proxy.api.audit import router as audit_router
from homeassistant_proxy.api.capabilities import router as capabilities_router
from homeassistant_proxy.api.drafts import router as drafts_router
from homeassistant_proxy.api.files import router as files_router
from homeassistant_proxy.api.ha_read import router as ha_read_router
from homeassistant_proxy.api.health import router as health_router
from homeassistant_proxy.api.reload import router as reload_router
from homeassistant_proxy.core.errors import install_error_handlers
from homeassistant_proxy.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Home Assistant GPT Proxy API",
        version="0.1.0",
        description="Narrow proxy between GPT Actions and Home Assistant.",
    )
    install_error_handlers(app)
    app.include_router(health_router)
    app.include_router(capabilities_router)
    app.include_router(ha_read_router)
    app.include_router(files_router)
    app.include_router(drafts_router)
    app.include_router(reload_router)
    app.include_router(audit_router)
    return app


app = create_app()
