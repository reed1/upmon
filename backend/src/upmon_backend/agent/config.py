from pydantic import BaseModel


class AgentSite(BaseModel):
    project_id: str
    site_key: str
    agent_url: str
    agent_api_key: str


class AgentConfig(BaseModel):
    sites: list[AgentSite]
