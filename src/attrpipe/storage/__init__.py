"""Storage — canonical fact store, chunking, hybrid indexes (docs/04).

Facts are append-only and versioned (valid_from / superseded_by). Indexes are
derived and rebuildable; the fact store is the single source of truth. Chunks
are self-contained: every chunk carries the product header (brand, model,
category) so retrieval cannot mix up products.
"""
