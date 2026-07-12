from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from attrpipe.api.app import create_app
from attrpipe.api.deps import get_hitl_repository, get_mapping_repository
from attrpipe.storage import HitlItem


class FakeHitl:
    def __init__(self) -> None:
        self.items = {
            "hitl_map": HitlItem(
                item_id="hitl_map",
                queue="attribute_mapping",
                payload={"raw_attribute": "Загальна маса", "source_url": "https://v/x"},
                priority=100,
                status="open",
            ),
            "hitl_anom": HitlItem(
                item_id="hitl_anom",
                queue="value_anomaly",
                payload={"raw_attribute": "weight", "raw_value": "9e9"},
                priority=100,
                status="open",
            ),
        }
        self.resolved: list[str] = []

    def get(self, item_id: str) -> HitlItem | None:
        return self.items.get(item_id)

    def resolve(self, item_id: str, resolution: dict[str, Any], *, resolved_by: str) -> bool:
        self.resolved.append(item_id)
        return True


class FakeMapping:
    def __init__(self) -> None:
        self.upserts: list[tuple[str, str, str]] = []

    def upsert(
        self,
        raw_attribute: str,
        attribute_key: str,
        *,
        language: str = "und",
        category_path: tuple[str, ...] = (),
        confirmed_by: str = "hitl",
    ) -> None:
        self.upserts.append((raw_attribute, attribute_key, confirmed_by))


@pytest.fixture
def parts() -> Iterator[tuple[TestClient, FakeMapping]]:
    app = create_app()
    mapping = FakeMapping()
    app.dependency_overrides[get_hitl_repository] = FakeHitl
    app.dependency_overrides[get_mapping_repository] = lambda: mapping
    with TestClient(app) as client:
        yield client, mapping
    app.dependency_overrides.clear()


class TestResolveWritesMapping:
    def test_attribute_mapping_resolution_writes_dictionary(
        self, parts: tuple[TestClient, FakeMapping]
    ) -> None:
        client, mapping = parts
        resp = client.post(
            "/v1/hitl/hitl_map/resolve",
            json={"resolution": {"attribute_key": "net_weight"}, "resolved_by": "mod"},
        )
        body = resp.json()
        assert body["status"] == "resolved"
        assert body["learned"] == {"raw_attribute": "Загальна маса", "attribute_key": "net_weight"}
        assert mapping.upserts == [("Загальна маса", "net_weight", "mod")]

    def test_value_anomaly_resolution_does_not_write_mapping(
        self, parts: tuple[TestClient, FakeMapping]
    ) -> None:
        client, mapping = parts
        resp = client.post(
            "/v1/hitl/hitl_anom/resolve",
            json={"resolution": {"decision": "reject"}, "resolved_by": "mod"},
        )
        assert resp.json()["learned"] is None
        assert mapping.upserts == []

    def test_unknown_item_404(self, parts: tuple[TestClient, FakeMapping]) -> None:
        client, _ = parts
        assert client.post("/v1/hitl/nope/resolve", json={}).status_code == 404
