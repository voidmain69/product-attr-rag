"""Extractor contract shared by every tier (docs/02).

An extractor turns one RawArtifact into candidate facts. Tiers are tried
cheapest-first (docs/02 §1); each is pure and deterministic — same artifact and
same method version yield the same candidates (idempotency, docs/00).
"""

from typing import Protocol, runtime_checkable

from attrpipe.domain import CandidateFact, RawArtifact
from attrpipe.domain.facts import ExtractionTier


@runtime_checkable
class Extractor(Protocol):
    """Contract for a single extraction tier."""

    tier: ExtractionTier
    method: str  # versioned method id recorded in provenance, e.g. "jsonld_v1"

    def extract(self, artifact: RawArtifact) -> list[CandidateFact]:
        """Return candidate facts found in ``artifact`` (possibly empty)."""
        ...
