"""Conflict resolution between competing facts (docs/03 §5).

When the same canonical attribute of the same product gets different values, we
do not silently overwrite. A weighted priority picks the *effective* value while
all competing variants are retained with their provenance:

1. source authority — feed/API > structured (Tier 1) > CMS (Tier 2) > DOM
   (Tier 3) > LLM prose (Tier 4);
2. freshness — newer ``fetched_at`` wins;
3. confidence — higher wins.

Same-source-over-time is versioning, not conflict: a newer fetch of the same URL
supersedes the older value. Genuine disagreement between roughly equal-authority
sources is flagged ``disputed`` so the answer layer can show both (docs/05 §5).
"""

from pydantic import BaseModel

from attrpipe.domain import CanonicalFact

# Lower rank = higher authority.
_SOURCE_AUTHORITY: dict[str, int] = {
    "feed": 0,
    "api": 0,
    "json_ld": 1,
    "cms_adapter": 2,
    "dom": 3,
    "llm_text": 4,
    "llm_vision": 4,
}


def _authority(fact: CanonicalFact) -> int:
    return _SOURCE_AUTHORITY.get(fact.provenance.source_type, 5)


class Decision(BaseModel):
    effective_is_candidate: bool  # does the incoming fact become the effective one?
    disputed: bool  # do equal-authority sources genuinely disagree?
    supersede: bool  # same-source revalidation (time-versioning), not a conflict


class ConflictResolver:
    def decide(self, current: CanonicalFact, candidate: CanonicalFact) -> Decision:
        if current.provenance.source_url == candidate.provenance.source_url:
            # same page re-fetched -> newer version replaces the older one
            return Decision(effective_is_candidate=True, disputed=False, supersede=True)

        rank_current = _authority(current)
        rank_candidate = _authority(candidate)
        values_differ = (
            current.canonical_value != candidate.canonical_value
            or current.canonical_unit != candidate.canonical_unit
        )

        if rank_candidate != rank_current:
            effective_is_candidate = rank_candidate < rank_current
        elif candidate.provenance.fetched_at != current.provenance.fetched_at:
            effective_is_candidate = candidate.provenance.fetched_at > current.provenance.fetched_at
        else:
            effective_is_candidate = candidate.confidence >= current.confidence

        disputed = values_differ and rank_candidate == rank_current
        return Decision(
            effective_is_candidate=effective_is_candidate,
            disputed=disputed,
            supersede=False,
        )
