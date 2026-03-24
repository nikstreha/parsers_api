from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MONGO_HOST: str
    MONGO_PORT: int
    MONGO_ROOT_USER: str
    MONGO_ROOT_PASSWORD: str
    MONGO_DB_NAME: str

    MIN_DELAY: int = 1
    MAX_DELAY: int = 2
    SESSION_DIR: str = "parser_api/infrastructure/web/camoufox_session"
    HEADLESS: bool = False

    PROXY_SERVER: str
    PROXY_USERNAME: str
    PROXY_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="allow"
    )

    @cached_property
    def mongo_url(self) -> str:
        return f"mongodb://{self.MONGO_ROOT_USER}:{self.MONGO_ROOT_PASSWORD}@{self.MONGO_HOST}:{self.MONGO_PORT}/?authSource=admin"

    @cached_property
    def proxy(self) -> dict:
        return {
            "server": self.PROXY_SERVER,
            "username": self.PROXY_USERNAME,
            "password": self.PROXY_PASSWORD,
        }
