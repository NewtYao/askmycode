"""Per-project configuration loaded from .askmycode.toml."""
from pathlib import Path

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

_CONFIG_FILE = ".askmycode.toml"

_DEFAULTS: dict = {
    "provider": "",
    "model": "",
    "n_results": 8,
    "include": [],
    "exclude": [],
}


def load(project_root: Path) -> dict:
    path = project_root / _CONFIG_FILE
    if not path.exists() or tomllib is None:
        return dict(_DEFAULTS)
    try:
        data = tomllib.loads(path.read_text())
        cfg = dict(_DEFAULTS)
        cfg.update(data.get("askmycode", {}))
        return cfg
    except Exception:
        return dict(_DEFAULTS)
