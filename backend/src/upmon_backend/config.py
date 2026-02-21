from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    api_key: str
    frontend_dir: str = "../frontend/dist"
    access_logs_config: str = "access_logs.json"
