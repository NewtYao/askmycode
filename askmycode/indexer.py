import ast
from pathlib import Path
from typing import Callable, Optional

import pathspec

from askmycode import embedder, manifest, store

_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".swift", ".kt",
    ".scala", ".sh", ".bash", ".yaml", ".yml", ".toml", ".json",
    ".md", ".sql", ".css", ".html", ".vue", ".svelte",
}
_MAX_FILE_BYTES = 1024 * 1024  # 1 MB
_CHUNK_LINES = 60
_OVERLAP_LINES = 15
_EMBED_BATCH = 64

_DEFAULT_IGNORES = [
    ".git", ".askmycode", "__pycache__", "node_modules",
    ".venv", "venv", "dist", "build", ".next", "coverage",
]


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    patterns = list(_DEFAULT_IGNORES)
    gitignore = root / ".gitignore"
    if gitignore.exists():
        patterns += gitignore.read_text().splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def _scan_files(root: Path) -> list[Path]:
    spec = _load_gitignore(root)
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _CODE_EXTENSIONS:
            continue
        if path.stat().st_size > _MAX_FILE_BYTES:
            continue
        if spec.match_file(str(path.relative_to(root))):
            continue
        files.append(path)
    return sorted(files)


def _ast_chunks(content: str, lines: list[str], relative: str) -> list[dict] | None:
    """Split a Python file at top-level function/class boundaries using AST.
    Returns None if parsing fails (falls back to sliding window)."""
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None

    top_nodes = [
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not top_nodes:
        return None

    # Sort by line number and build boundary ranges
    top_nodes.sort(key=lambda n: n.lineno)
    boundaries: list[tuple[int, int]] = []
    for i, node in enumerate(top_nodes):
        start = node.lineno - 1
        end = (top_nodes[i + 1].lineno - 2) if i + 1 < len(top_nodes) else len(lines)
        boundaries.append((start, end))

    # Module-level code before the first definition
    if boundaries and boundaries[0][0] > 0:
        boundaries.insert(0, (0, boundaries[0][0]))

    chunks = []
    for start, end in boundaries:
        body = "\n".join(lines[start:end]).strip()
        if body:
            chunks.append({
                "id": f"{relative}:{start}",
                "content": f"# {relative}  (lines {start + 1}–{end})\n\n{body}",
                "file_path": relative,
                "start_line": start + 1,
                "end_line": end,
            })
    return chunks or None


def _sliding_chunks(lines: list[str], relative: str) -> list[dict]:
    chunks = []
    i = 0
    while i < len(lines):
        end = min(i + _CHUNK_LINES, len(lines))
        body = "\n".join(lines[i:end]).strip()
        if body:
            chunks.append({
                "id": f"{relative}:{i}",
                "content": f"# {relative}  (lines {i + 1}–{end})\n\n{body}",
                "file_path": relative,
                "start_line": i + 1,
                "end_line": end,
            })
        i += _CHUNK_LINES - _OVERLAP_LINES
    return chunks


def _chunk_file(path: Path, root: Path) -> list[dict]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    lines = content.splitlines()
    relative = str(path.relative_to(root))

    if path.suffix == ".py":
        result = _ast_chunks(content, lines, relative)
        if result is not None:
            return result

    return _sliding_chunks(lines, relative)


def index_directory(
    root: Path,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> tuple[int, int]:
    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    log("Scanning files...")
    files = _scan_files(root)
    current_relatives = {str(p.relative_to(root)) for p in files}

    mf = manifest.load(root)
    client = store.get_client(root)
    collection = store.get_collection(client)

    # Remove chunks for files that were deleted since last index
    deleted = [rel for rel in mf if rel not in current_relatives]
    if deleted:
        log(f"Removing {len(deleted)} deleted file(s)...")
        store.delete_by_files(collection, deleted)
        for rel in deleted:
            del mf[rel]

    # Only process files that are new or changed
    changed_files = [p for p in files if manifest.is_changed(p, mf, str(p.relative_to(root)))]
    skipped = len(files) - len(changed_files)

    if not changed_files:
        log(f"Nothing changed — {len(files)} files already up to date.")
        return len(files), 0

    if skipped:
        log(f"Skipping {skipped} unchanged file(s)...")

    all_chunks: list[dict] = []
    for i, path in enumerate(changed_files):
        log(f"Reading ({i + 1}/{len(changed_files)})  {path.name}")
        all_chunks.extend(_chunk_file(path, root))

    if all_chunks:
        for i in range(0, len(all_chunks), _EMBED_BATCH):
            batch = all_chunks[i: i + _EMBED_BATCH]
            log(f"Embedding chunks {i + 1}–{min(i + _EMBED_BATCH, len(all_chunks))} / {len(all_chunks)}")
            embeddings = embedder.embed([c["content"] for c in batch])
            store.upsert_chunks(collection, batch, embeddings)

    # Update manifest for changed files
    for path in changed_files:
        rel = str(path.relative_to(root))
        mf[rel] = manifest.file_key(path)
    manifest.save(root, mf)

    return len(files), len(all_chunks)
