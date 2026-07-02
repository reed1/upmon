import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import RedirectResponse

from . import db
from .access import require_pangolin_user, require_service_key
from .config import Settings
from .routes.agent_cleanup import router as agent_cleanup_router
from .routes.agent_site_summary import router as agent_site_summary_router
from .routes.agent_errors import router as agent_errors_router
from .routes.agent_logs import router as agent_logs_router
from .routes.health import router as health_router
from .routes.monitors import router as monitors_router
from .scheduler import create_scheduler
from .spa import SPAStaticFiles

logger = logging.getLogger("upmon_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = app.state.settings
    app.state.pool = await db.create_pool(settings.database_url)
    await db.run_init(app.state.pool)
    logger.info("schema ready")

    scheduler = create_scheduler(app.state.pool, settings.agent_config)
    scheduler.start()
    logger.info("scheduler started")

    yield

    scheduler.shutdown(wait=False)
    await app.state.pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Upmon API",
        summary="Uptime monitoring API",
        lifespan=lifespan,
        redoc_url=None,
    )
    app.state.settings = settings

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/frontend/", status_code=302)

    app.include_router(health_router)

    # Same handlers on two mounts: /api is SSO-gated (identity from Pangolin's
    # remote-email header), /api-public bypasses Pangolin and authenticates with
    # the private API key (used by background services).
    api_routers = (
        monitors_router,
        agent_logs_router,
        agent_errors_router,
        agent_cleanup_router,
        agent_site_summary_router,
    )
    for router in api_routers:
        app.include_router(router, prefix="/api/v1", dependencies=[Depends(require_pangolin_user)])
        app.include_router(
            router,
            prefix="/api-public/v1",
            dependencies=[Depends(require_service_key)],
            include_in_schema=False,
        )

    app.mount(
        "/frontend",
        SPAStaticFiles(directory=settings.frontend_dir),
        name="frontend",
    )

    return app


app = create_app()
