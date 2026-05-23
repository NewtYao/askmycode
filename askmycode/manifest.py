import json
from pathlib import Path

_MANIFEST_FILE = ".askmycode/manifest.json"


def _path(project_root: Path) -> Path:
    return project_root / _MANIFEST_FILE


def load(project_root: Path) -> dict:
    p = _path(project_root)
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save(project_root: Path, manifest: dict) -> None:
    p = _path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2))


def file_key(path: Path) -> dict:
    stat = path.stat()
    return {"mtime": stat.st_mtime, "size": stat.st_size}


def is_changed(path: Path, manifest: dict, relative: str) -> bool:
    if relative not in manifest:
        return True
    entry = manifest[relative]
    stat = path.stat()
    return stat.st_mtime != entry["mtime"] or stat.st_size != entry["size"]
