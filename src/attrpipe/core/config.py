"""Central application settings, loaded from environment / .env.

Every worker and service builds its config from this single class so that
docker-compose, CI and local runs stay consistent.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Postgres — Canonical Fact Store
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "attrpipe"
    postgres_user: str = "attrpipe"
    postgres_password: str = ""

    # RabbitMQ — queues between pipeline layers
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "attrpipe"
    rabbitmq_password: str = ""

    # MinIO / S3 — Raw Store
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket_raw: str = "raw-artifacts"

    # OpenSearch — lexical index
    opensearch_url: str = "http://localhost:9200"

    # LLM
    anthropic_api_key: str = ""

    # Telemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "attrpipe"
    log_level: str = "INFO"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def rabbitmq_url(self) -> str:
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:{self.rabbitmq_port}/"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
