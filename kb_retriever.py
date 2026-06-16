"""
DEPRECATED: This module has been moved to server/services/kb_retriever.py.
Please update imports to use the new location.
"""
import warnings

warnings.warn(
    "kb_retriever.py has moved to server/services/kb_retriever.py. "
    "Please update your imports.",
    DeprecationWarning,
    stacklevel=2,
)

# Forward all imports — including private names tests depend on
from server.services.kb_retriever import (  # noqa: F401,E402
    _ZX_TRIGGERS,
    GROUP_TRIGGERS,
    Chunk,
    KbRetriever,
    KeywordOnlyEmbedding,
    QuoteEntry,
    RetrievalResult,
    create_embedding_provider,
    keyword_match_score,
    load_all_groups,
    split_group,
)
