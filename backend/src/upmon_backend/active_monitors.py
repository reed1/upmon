import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("upmon_backend.active_monitors")


@dataclass
class _Cache:
    active: set[tuple[str, str]] | None = None
    mtime: float | None = None
    missing_logged: bool = False


_cache = _Cache()


def load_active_monitors(path: str) -> set[tuple[str, str]] | None:
    """Set of (project_id, site_key) currently defined in the collector's config.json.

    The collector keeps historical rows for removed monitors in the database; this set
    is what the frontend should actually display. Returns None when the config file is
    absent, in which case filtering is disabled and every row is shown (fail-open, as in
    access.py) rather than blanking the dashboard on a transient issue.
    """
    file = Path(path)
    if not file.exists():
        if not _cache.missing_logged:
            logger.warning(
                "Monitors config %s not found; monitor filtering DISABLED (all rows shown)", path
            )
            _cache.missing_logged = True
        _cache.active = None
        _cache.mtime = None
        return None

    _cache.missing_logged = False
    mtime = file.stat().st_mtime
    if _cache.active is not None and mtime == _cache.mtime:
        return _cache.active

    with open(file) as f:
        config = json.load(f)
    active = {
        (project["id"], monitor["site_key"])
        for project in config["projects"]
        for monitor in project["monitors"]
    }
    _cache.active = active
    _cache.mtime = mtime
    logger.info("Loaded active monitors from %s (%d monitors)", path, len(active))
    return active
