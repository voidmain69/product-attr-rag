"""Storage — canonical fact store, chunking, hybrid indexes (docs/04).

Facts are append-only and versioned (valid_from / superseded_by). Indexes are
derived and rebuildable; the fact store is the single source of truth. Chunks
are self-contained: every chunk carries the product header (brand, model,
category) so retrieval cannot mix up products.
"""

from attrpipe.storage.db import connect, generate_id
from attrpipe.storage.fact_repository import Constraint, FactRepository, FilterOp
from attrpipe.storage.hitl_repository import HitlItem, HitlQueue, HitlRepository
from attrpipe.storage.product_repository import ProductRecord, ProductRef, ProductRepository

__all__ = [
    "Constraint",
    "FactRepository",
    "FilterOp",
    "HitlItem",
    "HitlQueue",
    "HitlRepository",
    "ProductRecord",
    "ProductRef",
    "ProductRepository",
    "connect",
    "generate_id",
]
