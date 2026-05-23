import json
import os
from pathlib import Path

_CONFIG_DIR = Path.home() / ".config" / "askmycode"
_CONFIG_FILE = _CONFIG_DIR / "config.json"

_ENV_KEYS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _load() -> dict:
    if _CONFIG_FILE.exists():
        return json.loads(_CONFIG_FILE.read_text())
    return {}


def _save(data: dict) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(data, indent=2))


def get_api_key(provider: str = "gemini") -> str | None:
    env_var = _ENV_KEYS.get(provider, f"{provider.upper()}_API_KEY")
    if key := os.environ.get(env_var):
        return key
    return _load().get("api_key")


def set_api_key(key: str) -> None:
    data = _load()
    data["api_key"] = key
    _save(data)


def get_provider() -> str:
    return os.environ.get("ASKMYCODE_PROVIDER") or _load().get("provider", "gemini")


def set_provider(provider: str) -> None:
    data = _load()
    data["provider"] = provider
    _save(data)


def get_model() -> str:
    return os.environ.get("ASKMYCODE_MODEL") or _load().get("model", "")


def set_model(model: str) -> None:
    data = _load()
    data["model"] = model
    _save(data)
