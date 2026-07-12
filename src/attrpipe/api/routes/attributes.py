"""Canonical attribute ontology route (docs/03 §1). Served from the in-code
ontology; no database required."""

from fastapi import APIRouter

from attrpipe.api.schemas import AttributeOut
from attrpipe.normalization.ontology import ONTOLOGY

router = APIRouter(prefix="/v1", tags=["attributes"])


@router.get("/attributes")
def list_attributes() -> list[AttributeOut]:
    return [AttributeOut.from_attribute(attr) for attr in ONTOLOGY.values()]
