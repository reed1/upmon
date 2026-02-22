import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import RedirectResponse

from . import db
from .agent.config import AgentConfig
from .agent.routes import router as agent_router
from .auth import require_api_key
from .config import Settings
from .models import HourlySummary, MonitorStatus
from .spa import SPAStaticFiles

logger = logging.getLogger("upmon_backend")


def _load_agent_config(path: str) -> AgentConfig | None:
    config_path = Path(path)
    if not config_path.exists():
        logger.info("Agent config not found at %s, feature disabled", path)
        return None
    with open(config_path) as f:
        return AgentConfig.model_validate(json.load(f))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await db.create_pool(app.state.settings.database_url)
    logger.info("database ready")

    agent_config = _load_agent_config(app.state.settings.agent_config)
    if agent_config:
        app.state.agent_config = agent_config
        logger.info("Agent enabled with %d site(s)", len(agent_config.sites))

    yield

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
        return RedirectResponse(url="/frontend", status_code=308)

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "UP"}

    @app.get(
        "/api/v1/status",
        response_model=list[MonitorStatus],
        dependencies=[Depends(require_api_key)],
    )
    async def status(
        request: Request,
        project_id: str | None = Query(None),
    ) -> list[dict]:
        rows = await db.get_monitor_statuses(request.app.state.pool, project_id)
        return [dict(r) for r in rows]

    @app.get(
        "/api/v1/daily-summary",
        response_model=HourlySummary,
        dependencies=[Depends(require_api_key)],
    )
    async def daily_summary(
        request: Request,
        project_id: str | None = Query(None),
        days: int = Query(7),
    ) -> HourlySummary:
        days = max(1, min(days, 90))
        return await db.get_hourly_summary(request.app.state.pool, project_id, days)

    app.include_router(agent_router)

    app.mount(
        "/frontend",
        SPAStaticFiles(directory=settings.frontend_dir),
        name="frontend",
    )

    return app


app = create_app()
