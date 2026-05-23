from pathlib import Path

from askmycode import embedder, reranker, store

_FETCH_MULTIPLIER = 3  # fetch this many extra candidates for re-ranking


def retrieve(
    question: str,
    project_root: Path,
    n_results: int = 8,
) -> tuple[str, list[dict]]:
    """Return (context_string, sources) where sources is a list of metadata dicts."""
    client = store.get_client(project_root)
    collection = store.get_collection(client)

    fetch_n = min(n_results * _FETCH_MULTIPLIER, collection.count())
    if fetch_n == 0:
        return "", []

    query_embedding = embedder.embed([question])[0]
    results = store.search(collection, query_embedding, n_results=fetch_n)

    documents: list[str] = results.get("documents", [[]])[0]
    metadatas: list[dict] = results.get("metadatas", [[]])[0]

    if not documents:
        return "", []

    # Re-rank candidates and keep the top n_results
    top_indices = reranker.rerank(question, documents, top_k=n_results)
    documents = [documents[i] for i in top_indices]
    metadatas = [metadatas[i] for i in top_indices]

    return "\n\n---\n\n".join(documents), metadatas
