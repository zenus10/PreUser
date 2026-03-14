from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # LLM
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "deepseek/deepseek-chat"
    llm_fallback_model: str = "deepseek/deepseek-chat"
    llm_max_retries: int = 2
    llm_temperature: float = 0.7

    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "vul"
    db_user: str = "postgres"
    db_password: str = "changeme_in_production"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    max_upload_size_mb: int = 10
    max_concurrent_analyses: int = 3

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
