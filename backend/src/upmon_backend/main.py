import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from . import db
from .access_logs.config import AccessLogsConfig
from .access_logs.routes import router as access_logs_router
from .access_logs.ssh_session import SSHSessionManager
from .auth import require_api_key
from .config import Settings
from .models import HourlySummary, MonitorStatus
from .spa import SPAStaticFiles

logger = logging.getLogger("upmon_backend")

SCALAR_HTML = """\
<!doctype html>
<html>
<head>
<title>Upmon API</title>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>:root { --scalar-font: system-ui, sans-serif !important; }</style>
</head>
<body>
<script id="api-reference" data-url="/openapi.json"></script>
<script src="https://cdn.jsdelivr.net/npm/@scalar/api-reference"></script>
</body>
</html>"""


def _load_access_logs_config(path: str) -> AccessLogsConfig | None:
    config_path = Path(path)
    if not config_path.exists():
        logger.info("Access logs config not found at %s, feature disabled", path)
        return None
    with open(config_path) as f:
        return AccessLogsConfig.model_validate(json.load(f))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pool = await db.create_pool(app.state.settings.database_url)
    logger.info("database ready")

    access_logs_config = _load_access_logs_config(
        app.state.settings.access_logs_config
    )
    if access_logs_config:
        app.state.access_logs_config = access_logs_config
        app.state.ssh_session_manager = SSHSessionManager()
        logger.info(
            "Access logs enabled with %d site(s)", len(access_logs_config.sites)
        )

    yield

    if hasattr(app.state, "ssh_session_manager"):
        await app.state.ssh_session_manager.close_all()
    await app.state.pool.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Upmon API",
        summary="Uptime monitoring API",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.settings = settings

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/frontend", status_code=308)

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "UP"}

    @app.get("/docs", include_in_schema=False)
    async def docs():
        return HTMLResponse(SCALAR_HTML)

    @app.get(
        "/api/v1/status",
        response_model=list[MonitorStatus],
        dependencies=[Depends(require_api_key)],
    )
    async def status(
        request: Request,
        project_id: str | None = Query(None),
    ) -> list[dict]:
        rows = await db.get_monitor_statuses(
            request.app.state.pool, project_id
        )
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
        return await db.get_hourly_summary(
            request.app.state.pool, project_id, days
        )

    app.include_router(access_logs_router)

    app.mount(
        "/frontend",
        SPAStaticFiles(directory=settings.frontend_dir),
        name="frontend",
    )

    return app


def main():
    settings = Settings()
    logging.basicConfig(level=logging.INFO)
    logger.info("HTTP server listening on port %d", settings.listen_port)
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",
        port=settings.listen_port,
        log_level="info",
    )
