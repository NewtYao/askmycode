import io
import os
import sys
from functools import lru_cache

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model():
    # Import and load inside the function so we can suppress all stderr noise
    # (HF Hub unauthenticated warning + tqdm progress bars) in one redirect.
    old_stderr = sys.stderr
    sys.stderr = io.StringIO()
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(MODEL_NAME)
    finally:
        sys.stderr = old_stderr


def embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return model.encode(texts, show_progress_bar=False).tolist()
