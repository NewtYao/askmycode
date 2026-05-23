from pathlib import Path
import chromadb

_INDEX_DIR = ".askmycode/chroma"


def get_client(project_root: Path) -> chromadb.PersistentClient:
    index_path = project_root / _INDEX_DIR
    index_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(index_path))


def get_collection(client: chromadb.PersistentClient) -> chromadb.Collection:
    return client.get_or_create_collection(
        name="codebase",
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(
    collection: chromadb.Collection,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    collection.upsert(
        ids=[c["id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["content"] for c in chunks],
        metadatas=[
            {k: v for k, v in c.items() if k not in ("id", "content")}
            for c in chunks
        ],
    )


def delete_by_files(collection: chromadb.Collection, file_paths: list[str]) -> None:
    """Remove all chunks belonging to the given relative file paths."""
    for file_path in file_paths:
        results = collection.get(where={"file_path": file_path}, include=[])
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)


def search(
    collection: chromadb.Collection,
    query_embedding: list[float],
    n_results: int = 8,
) -> dict:
    return collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
