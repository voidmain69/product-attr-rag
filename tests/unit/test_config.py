from attrpipe.core.config import Settings


def test_postgres_dsn_assembly() -> None:
    s = Settings(
        postgres_host="db",
        postgres_port=5433,
        postgres_db="facts",
        postgres_user="u",
        postgres_password="p",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.postgres_dsn == "postgresql://u:p@db:5433/facts"


def test_rabbitmq_url_assembly() -> None:
    s = Settings(
        rabbitmq_user="u",
        rabbitmq_password="p",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert s.rabbitmq_url == "amqp://u:p@localhost:5672/"
