from pydantic import BaseModel


class AccessLogSite(BaseModel):
    ssh_host: str
    db_path: str


class AccessLogsConfig(BaseModel):
    sites: dict[str, AccessLogSite]
