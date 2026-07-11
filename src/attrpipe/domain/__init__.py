"""Domain models shared across layers (candidate facts, canonical facts, provenance)."""

from attrpipe.domain.facts import CandidateFact, CanonicalFact, EvidenceLocation, Provenance

__all__ = ["CandidateFact", "CanonicalFact", "EvidenceLocation", "Provenance"]
