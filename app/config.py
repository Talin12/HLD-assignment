from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "typeahead"
    db_user: str = "typeahead"
    db_password: str = "typeahead_secret"

    # Redis nodes — comma-separated host:port pairs read from individual env vars
    redis_node_1: str = "localhost:6379"
    redis_node_2: str = "localhost:6380"
    redis_node_3: str = "localhost:6381"

    # Cache TTL in seconds
    cache_ttl: int = 300

    # Batch writer settings
    batch_max_size: int = 500
    batch_flush_interval: int = 5  # seconds

    # Recency scoring: exponential decay lambda (higher = faster decay)
    decay_lambda: float = 0.0001

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_nodes(self) -> List[str]:
        return [self.redis_node_1, self.redis_node_2, self.redis_node_3]

    class Config:
        env_file = ".env"


settings = Settings()
