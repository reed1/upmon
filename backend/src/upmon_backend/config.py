from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    api_key_secret: str
    frontend_dir: str = "../frontend/dist"
    agent_config: str = "agents.json"
    users_config: str = "users.yaml"
    monitors_config: str = "../collector-bin/config.json"
