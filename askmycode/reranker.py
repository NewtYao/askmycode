import io
import os
import sys
from functools import lru_cache

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


@lru_cache(maxsize=1)
def _get_cross_encoder():
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from sentence_transformers.cross_encoder import CrossEncoder
        return CrossEncoder(_RERANK_MODEL)
    finally:
        sys.stderr = old_stderr


def rerank(question: str, documents: list[str], top_k: int) -> list[int]:
    """Return indices of the top_k documents sorted by relevance to question."""
    model = _get_cross_encoder()
    pairs = [(question, doc) for doc in documents]
    scores = model.predict(pairs)
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return ranked[:top_k]
