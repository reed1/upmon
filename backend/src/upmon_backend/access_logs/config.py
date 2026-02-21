from pydantic import BaseModel


class AccessLogSite(BaseModel):
    project_id: str
    site_key: str
    ssh_host: str
    db_path: str


class AccessLogsConfig(BaseModel):
    sites: list[AccessLogSite]
