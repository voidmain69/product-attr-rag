"""Raw Store integration tests (docs/09 §4). Require MinIO + Postgres:
``python tools/dev.py up``. Excluded from default CI.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import boto3
import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.domain import RawArtifact
from attrpipe.storage.raw_store import RawStore

pytestmark = pytest.mark.integration

BUCKET = "raw-artifacts"


def _dsn() -> str:
    password = os.environ.get("POSTGRES_PASSWORD", "attrpipe-local")
    return f"postgresql://attrpipe:{password}@localhost:5432/attrpipe"


def _s3() -> Any:
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "attrpipe"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "attrpipe-local"),
        region_name="us-east-1",
    )


@pytest.fixture
def store() -> Iterator[tuple[RawStore, list[str]]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover - infra-dependent
        pytest.skip(f"Postgres not available: {exc}")
    s3 = _s3()
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception as exc:
        conn.close()
        pytest.skip(f"MinIO/bucket not available: {exc}")

    created: list[str] = []
    yield RawStore(s3, BUCKET, conn), created

    with conn.transaction(), conn.cursor() as cur:
        for artifact_id in created:
            cur.execute("DELETE FROM raw_artifacts WHERE raw_artifact_id = %s", (artifact_id,))
            s3.delete_object(Bucket=BUCKET, Key=artifact_id)
    conn.close()


def make_artifact(artifact_id: str, content: str) -> RawArtifact:
    return RawArtifact(
        raw_artifact_id=artifact_id,
        url="https://example-vendor.com/products/acme-model-x?utm_source=x",
        canonical_url="https://example-vendor.com/products/acme-model-x",
        content=content,
        content_type="text/html",
        fetched_at=datetime(2026, 7, 12, 10, 0, tzinfo=UTC),
        detected_engine="custom",
    )


class TestRawStore:
    def test_put_then_get_roundtrip(self, store: tuple[RawStore, list[str]]) -> None:
        raw_store, created = store
        artifact_id = "raw/example-vendor.com/test-roundtrip"
        created.append(artifact_id)
        content = "<html><body>Acme Model X · 2.3 kg</body></html>"

        raw_store.put(make_artifact(artifact_id, content))
        fetched = raw_store.get(artifact_id)

        assert fetched is not None
        assert fetched.content == content
        assert fetched.canonical_url == "https://example-vendor.com/products/acme-model-x"
        assert fetched.detected_engine == "custom"

    def test_exists(self, store: tuple[RawStore, list[str]]) -> None:
        raw_store, created = store
        artifact_id = "raw/example-vendor.com/test-exists"
        assert raw_store.exists(artifact_id) is False
        created.append(artifact_id)
        raw_store.put(make_artifact(artifact_id, "<html></html>"))
        assert raw_store.exists(artifact_id) is True

    def test_put_is_idempotent(self, store: tuple[RawStore, list[str]]) -> None:
        raw_store, created = store
        artifact_id = "raw/example-vendor.com/test-idem"
        created.append(artifact_id)
        artifact = make_artifact(artifact_id, "<html>v1</html>")

        h1 = raw_store.put(artifact)
        h2 = raw_store.put(artifact)
        assert h1 == h2  # content hash is stable

        with psycopg.connect(_dsn(), row_factory=dict_row) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM raw_artifacts WHERE raw_artifact_id = %s",
                (artifact_id,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row["n"] == 1  # no duplicate metadata row

    def test_missing_artifact_returns_none(self, store: tuple[RawStore, list[str]]) -> None:
        raw_store, _ = store
        assert raw_store.get("raw/example-vendor.com/does-not-exist") is None
