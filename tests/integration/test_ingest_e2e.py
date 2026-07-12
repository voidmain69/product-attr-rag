"""End-to-end ingestion against real infrastructure (docs/09 §4).

Drives the full pipeline with a mocked fetcher (no live site, CLAUDE.md §6) but
real Raw Store (MinIO), fact store and product repository (Postgres). Requires
``python tools/dev.py up``; excluded from default CI.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import httpx
import psycopg
import pytest
from psycopg.rows import dict_row

from attrpipe.extraction import StructuredDataExtractor
from attrpipe.fetch import PerDomainRateLimiter, StaticFetcher
from attrpipe.normalization import Normalizer
from attrpipe.pipeline import IngestPipeline
from attrpipe.storage import FactRepository, ProductRef, ProductRepository
from attrpipe.storage.raw_store import RawStore

pytestmark = pytest.mark.integration

BUCKET = "raw-artifacts"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


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
def env() -> Iterator[tuple[IngestPipeline, psycopg.Connection[dict[str, Any]], Any, list[str]]]:
    try:
        conn = psycopg.connect(_dsn(), row_factory=dict_row, connect_timeout=3)
    except psycopg.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"Postgres not available: {exc}")
    s3 = _s3()
    try:
        s3.head_bucket(Bucket=BUCKET)
    except Exception as exc:
        conn.close()
        pytest.skip(f"MinIO not available: {exc}")

    html = (FIXTURES / "jsonld__example-vendor.com__acme-model-x.html").read_text(encoding="utf-8")
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, text=html, headers={"content-type": "text/html"})
    )
    fetcher = StaticFetcher(
        httpx.Client(transport=transport),
        PerDomainRateLimiter(0.0, clock=lambda: 0.0, sleep=lambda _: None),
    )
    pipeline = IngestPipeline(
        fetcher=fetcher,
        raw_store=RawStore(s3, BUCKET, conn),
        extractors=[StructuredDataExtractor()],
        normalizer=Normalizer(),
        products=ProductRepository(conn),
        facts=FactRepository(conn),
    )
    artifact_ids: list[str] = []
    yield pipeline, conn, s3, artifact_ids

    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "DELETE FROM facts WHERE provenance->>'raw_artifact_id' = ANY(%s)", (artifact_ids,)
        )
        cur.execute("DELETE FROM raw_artifacts WHERE raw_artifact_id = ANY(%s)", (artifact_ids,))
    for artifact_id in artifact_ids:
        s3.delete_object(Bucket=BUCKET, Key=artifact_id)
    conn.close()


def test_ingest_persists_facts_end_to_end(
    env: tuple[IngestPipeline, psycopg.Connection[dict[str, Any]], Any, list[str]],
) -> None:
    pipeline, conn, s3, artifact_ids = env
    url = "https://example-vendor.com/products/acme-model-x?utm_source=nl"

    result = pipeline.ingest(
        url,
        ProductRef(brand="AcmeE2E", model="Model X E2E", category_path=("electronics", "audio")),
        valid_from=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
    )
    artifact_ids.append(result.raw_artifact_id)

    assert result.facts_written == 6

    # raw artifact really landed in the object store
    obj = s3.get_object(Bucket=BUCKET, Key=result.raw_artifact_id)
    assert b"Acme Model X" in obj["Body"].read()

    # canonical facts really landed in the fact store
    facts = FactRepository(conn).get_effective_facts(result.product_id)
    by_key = {f.attribute_key: f for f in facts}
    assert by_key["net_weight"].canonical_value == 2300.0
    assert by_key["net_weight"].canonical_unit == "g"

    # cleanup depends on product_id too
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("DELETE FROM facts WHERE product_id = %s", (result.product_id,))
        cur.execute("DELETE FROM products WHERE product_id = %s", (result.product_id,))
