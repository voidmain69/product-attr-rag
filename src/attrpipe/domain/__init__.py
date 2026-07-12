"""Domain models shared across layers (raw artifacts, candidate/canonical facts)."""

from attrpipe.domain.facts import CandidateFact, CanonicalFact, EvidenceLocation, Provenance
from attrpipe.domain.raw import RawArtifact

__all__ = [
    "CandidateFact",
    "CanonicalFact",
    "EvidenceLocation",
    "Provenance",
    "RawArtifact",
]
