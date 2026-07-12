"""Raw Store — S3-compatible object storage for raw artifacts (docs/01 §7).

Persists the fetched body to MinIO/S3 and its fetch provenance to the
``raw_artifacts`` table, keyed by ``raw_artifact_id``. Writes are idempotent
(``ON CONFLICT DO NOTHING``): re-fetching the same artifact does not duplicate
it. Extraction reads artifacts from here, never from live sites, which is what
makes re-extraction reproducible (CLAUDE.md §2.3).
"""

import hashlib
from typing import Any

import boto3
import psycopg

from attrpipe.core.config import get_settings
from attrpipe.domain import RawArtifact


def s3_client() -> Any:
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1",
    )


class RawStore:
    def __init__(
        self,
        s3: Any,
        bucket: str,
        conn: psycopg.Connection[dict[str, Any]],
    ) -> None:
        self._s3 = s3
        self._bucket = bucket
        self._conn = conn

    def put(
        self,
        artifact: RawArtifact,
        *,
        http_status: int = 200,
        proxy_region: str | None = None,
        robots_allowed: bool = True,
    ) -> str:
        """Store the artifact body and metadata; return its content hash."""
        body = artifact.content.encode("utf-8")
        content_hash = hashlib.sha256(body).hexdigest()
        self._s3.put_object(
            Bucket=self._bucket,
            Key=artifact.raw_artifact_id,
            Body=body,
            ContentType=artifact.content_type,
        )
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO raw_artifacts (raw_artifact_id, url, canonical_url, fetched_at,"
                " http_status, content_type, content_hash, render_mode, detected_engine,"
                " proxy_region, robots_allowed)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                " ON CONFLICT (raw_artifact_id) DO NOTHING",
                (
                    artifact.raw_artifact_id,
                    artifact.url,
                    artifact.source_url,
                    artifact.fetched_at,
                    http_status,
                    artifact.content_type,
                    content_hash,
                    artifact.render_mode,
                    artifact.detected_engine,
                    proxy_region,
                    robots_allowed,
                ),
            )
        return content_hash

    def exists(self, raw_artifact_id: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM raw_artifacts WHERE raw_artifact_id = %s", (raw_artifact_id,)
            )
            return cur.fetchone() is not None

    def get(self, raw_artifact_id: str) -> RawArtifact | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT raw_artifact_id, url, canonical_url, fetched_at, content_type,"
                " render_mode, detected_engine FROM raw_artifacts WHERE raw_artifact_id = %s",
                (raw_artifact_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        obj = self._s3.get_object(Bucket=self._bucket, Key=raw_artifact_id)
        content: str = obj["Body"].read().decode("utf-8")
        return RawArtifact(
            raw_artifact_id=row["raw_artifact_id"],
            url=row["url"],
            canonical_url=row["canonical_url"],
            content=content,
            content_type=row["content_type"],
            fetched_at=row["fetched_at"],
            detected_engine=row["detected_engine"],
            render_mode=row["render_mode"],
        )
