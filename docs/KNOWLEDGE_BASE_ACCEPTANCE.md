# Knowledge Base Acceptance Mapping

This document records the currently implemented scope of `p4-knowledge-base`.

## Current Scope

Primary implementation paths:
- `kronos/research/knowledge_base/store.py`
- `kronos/research/knowledge_base/__init__.py`

Primary verification path:
- `tests/unit/research/knowledge_base/test_knowledge_base.py`

## Requirement Mapping

### Research Memory Persistence

- Implemented through SQLite-backed knowledge entries for:
  - experiment memories
  - failure memories

### SQLite + FTS Search

- Implemented through:
  - `init_knowledge_base(...)`
  - `add_experiment_entry(...)`
  - `add_failure_entry(...)`
  - `search_entries(...)`

### Upgrade Path Reservation

- Structured entries already preserve metadata JSON fields, leaving a clear
  future extension point for embedding-based retrieval.

## Known Limitations

- The current implementation is strictly SQLite + FTS and does not yet provide
  semantic retrieval.

- The knowledge base is not yet automatically fed by every experiment path;
  the current implementation provides the core storage and retrieval layer.
