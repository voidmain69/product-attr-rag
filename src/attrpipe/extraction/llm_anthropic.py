"""Concrete Anthropic-backed structured extraction model (docs/02 §5.2).

Implements ``StructuredExtractionModel`` with the Claude Messages API using
structured outputs (``messages.parse``): the model fills a closed schema of
target attributes and quotes a verbatim ``source_span`` for each, which the
Tier 4 extractor then grounds. Requires the ``llm`` extra (``anthropic``);
``anthropic`` is imported lazily so importing this module never forces the
dependency. Not exercised by unit tests — real model calls are golden-eval only
(docs/09 §2).
"""

from typing import Any

from pydantic import BaseModel

from attrpipe.extraction.tier4_llm import ExtractedFact

DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM = (
    "You extract product attributes from text. Fill only the requested attribute "
    "keys; use null for any that are absent. For every fact, quote the exact "
    "verbatim sentence or phrase from the source as `source_span` — do not "
    "paraphrase. Never invent values that are not supported by the text."
)


class _LlmFacts(BaseModel):
    facts: list[ExtractedFact]


class AnthropicStructuredModel:
    def __init__(self, client: Any = None, model: str = DEFAULT_MODEL) -> None:
        self._client = client
        self._model = model

    def extract(
        self, *, text: str, attribute_keys: list[str], product_hint: str | None = None
    ) -> list[ExtractedFact]:
        # Lazy import keeps the anthropic dependency optional (see the `llm` extra).
        import anthropic

        client = self._client or anthropic.Anthropic()
        keys = ", ".join(attribute_keys)
        hint = f"\nProduct: {product_hint}" if product_hint else ""
        prompt = (
            f"Target attributes: {keys}.{hint}\n\n"
            f"Extract the attributes from the text below.\n\n---\n{text}\n---"
        )
        response = client.messages.parse(
            model=self._model,
            max_tokens=4096,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
            output_format=_LlmFacts,
        )
        parsed = response.parsed_output
        if parsed is None:
            return []
        return [ExtractedFact.model_validate(fact) for fact in parsed.facts]
