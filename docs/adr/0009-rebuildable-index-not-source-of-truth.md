# ADR 0009: The metadata index is rebuildable, not authoritative

PlanGuard stores canonical evidence as immutable JSON artifacts. SQLite is used only as a searchable
projection over those documents. Index rows may be deleted, migrated, or rebuilt without changing
artifact identity or analysis meaning. API reads that require search use the index; artifact detail
and integrity always resolve from canonical storage.
