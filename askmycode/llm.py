from typing import Iterator
from google import genai
from google.genai import types

_GEMINI_ROLE = {"user": "user", "model": "model", "assistant": "model"}
_OPENAI_ROLE = {"user": "user", "model": "assistant", "assistant": "assistant"}

_SYSTEM = """\
You are a helpful assistant that answers questions about a software codebase.
You are given relevant code snippets retrieved from the codebase and a question.
- Answer based on the provided snippets.
- Reference specific file paths and line numbers when relevant.
- If the answer cannot be determined from the snippets, say so clearly.
- Keep answers concise and developer-focused.
"""

# ── Gemini (default) ──────────────────────────────────────────────────────────

_GEMINI_MODEL = "gemini-2.5-flash-lite"


def _make_turn(role: str, text: str) -> types.Content:
    return types.Content(role=role, parts=[types.Part(text=text)])


def build_file_tree(file_paths: list[str]) -> str:
    if not file_paths:
        return ""
    lines = ["Project structure:"] + sorted(f"  {p}" for p in file_paths)
    return "\n".join(lines)


def _build_user_turn(question: str, context: str, file_tree: str) -> str:
    tree_section = f"{file_tree}\n\n" if file_tree else ""
    return (
        f"{tree_section}"
        f"Relevant code snippets:\n\n"
        f"{context}\n\n"
        f"Question: {question}"
    )


def _stream_gemini(
    question: str,
    context: str,
    api_key: str,
    history: list[dict] | None,
    file_tree: str,
    model: str,
) -> Iterator[str]:
    client = genai.Client(api_key=api_key)
    user_turn = _build_user_turn(question, context, file_tree)
    contents = [
        _make_turn(_GEMINI_ROLE.get(h["role"], h["role"]), h["content"])
        for h in (history or [])
    ] + [_make_turn("user", user_turn)]
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=_SYSTEM),
    ):
        if chunk.text:
            yield chunk.text


# ── OpenAI ────────────────────────────────────────────────────────────────────

def _stream_openai(
    question: str,
    context: str,
    api_key: str,
    history: list[dict] | None,
    file_tree: str,
    model: str,
) -> Iterator[str]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    user_turn = _build_user_turn(question, context, file_tree)
    messages = [{"role": "system", "content": _SYSTEM}]
    for h in history or []:
        messages.append({"role": _OPENAI_ROLE.get(h["role"], h["role"]), "content": h["content"]})
    messages.append({"role": "user", "content": user_turn})
    with client.chat.completions.create(model=model, messages=messages, stream=True) as stream:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


# ── Anthropic / Claude ────────────────────────────────────────────────────────

def _stream_anthropic(
    question: str,
    context: str,
    api_key: str,
    history: list[dict] | None,
    file_tree: str,
    model: str,
) -> Iterator[str]:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    user_turn = _build_user_turn(question, context, file_tree)
    messages = []
    for h in history or []:
        messages.append({"role": _OPENAI_ROLE.get(h["role"], h["role"]), "content": h["content"]})
    messages.append({"role": "user", "content": user_turn})
    with client.messages.stream(
        model=model,
        max_tokens=2048,
        system=_SYSTEM,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


# ── Ollama (local) ────────────────────────────────────────────────────────────

def _stream_ollama(
    question: str,
    context: str,
    history: list[dict] | None,
    file_tree: str,
    model: str,
    base_url: str,
) -> Iterator[str]:
    import requests, json
    user_turn = _build_user_turn(question, context, file_tree)
    messages = [{"role": "system", "content": _SYSTEM}]
    for h in history or []:
        messages.append({"role": _OPENAI_ROLE.get(h["role"], h["role"]), "content": h["content"]})
    messages.append({"role": "user", "content": user_turn})
    resp = requests.post(
        f"{base_url}/api/chat",
        json={"model": model, "messages": messages, "stream": True},
        stream=True,
        timeout=120,
    )
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line:
            data = json.loads(line)
            text = data.get("message", {}).get("content", "")
            if text:
                yield text


# ── Public interface ──────────────────────────────────────────────────────────

def answer_stream(
    question: str,
    context: str,
    api_key: str,
    history: list[dict] | None = None,
    file_tree: str = "",
    provider: str = "gemini",
    model: str = "",
    ollama_url: str = "http://localhost:11434",
) -> Iterator[str]:
    """Stream an answer from the configured provider."""
    if provider == "gemini":
        yield from _stream_gemini(
            question, context, api_key, history, file_tree,
            model=model or _GEMINI_MODEL,
        )
    elif provider == "openai":
        yield from _stream_openai(
            question, context, api_key, history, file_tree,
            model=model or "gpt-4o-mini",
        )
    elif provider == "anthropic":
        yield from _stream_anthropic(
            question, context, api_key, history, file_tree,
            model=model or "claude-sonnet-4-6",
        )
    elif provider == "ollama":
        yield from _stream_ollama(
            question, context, history, file_tree,
            model=model or "llama3",
            base_url=ollama_url,
        )
    else:
        raise ValueError(f"Unknown provider: {provider!r}. Choose: gemini, openai, anthropic, ollama")
