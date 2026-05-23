# askmycode

**Ask questions about any codebase in plain English. Your code never leaves your machine.**

```
$ askmycode ask "how does authentication work?"

Authentication is handled in src/auth/middleware.py (lines 12–45).
The require_auth decorator validates a JWT from the Authorization header,
looks up the user in the session store (Redis), and attaches the user object
to the request context. Unauthenticated requests are rejected with a 401...
```

[![PyPI version](https://img.shields.io/pypi/v/askmycode.svg)](https://pypi.org/project/askmycode/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Why askmycode?

Most AI coding tools send your entire codebase to a remote server. **askmycode doesn't.**

- **Your code stays local.** Only the question + a few relevant snippets reach the AI.
- **Works on any codebase** — Python, Go, TypeScript, Rust, Java, and more.
- **No more grepping.** Ask "where is the rate limiter?" instead of `grep -r "rate" .`
- **Onboarding superpower.** New to a repo? Ask questions instead of reading every file.
- **Multi-provider.** Gemini (free tier), OpenAI, Claude, or fully offline via Ollama.

---

## How it works

```
Your code  ──►  chunked locally  ──►  embedded locally  ──►  stored in local vector DB
                                                                        │
Your question ──► embed locally ──► find top chunks ──► send to AI ──► Answer
                                         ↑
                           only ~500 lines of relevant code
                           travel to the AI, not your whole repo
```

Embeddings run on your machine via `sentence-transformers`. Only the retrieved snippets and your question are sent to the LLM.

---

## Install

```bash
pip install askmycode
```

Or from source:
```bash
git clone https://github.com/NewtYao/askmycode
cd askmycode
pip install -e .
```

---

## Quick start

**1. Set your API key**
```bash
askmycode config set-key YOUR_GEMINI_KEY   # get a free key at aistudio.google.com
```

**2. Initialise your project** *(optional — sets up .gitignore and suggests starter questions)*
```bash
cd your-project/
askmycode init .
```

**3. Index your codebase** *(run once; re-run after big changes)*
```bash
askmycode index .
```

**4. Ask questions**
```bash
askmycode ask "where is the database connection configured?"
askmycode ask "how does the retry logic work?"
askmycode ask "what does UserService do?"
```

---

## Commands

### `askmycode ask`
```bash
askmycode ask "your question"
  --sources, -s       Show which files and lines were used to answer
  --results, -n INT   Chunks to retrieve (default: 8)
  --provider TEXT     gemini | openai | anthropic | ollama
  --model TEXT        Model name override
  --project, -p PATH  Path to indexed project (default: .)
```

```bash
# Show sources alongside the answer
askmycode ask "how is caching implemented?" --sources

# Use a different provider for one question
askmycode ask "what does this codebase do?" --provider openai
```

### `askmycode chat`
Multi-turn conversation — follow-up questions remember previous answers.
```bash
askmycode chat

You: how does auth work?
Assistant: ...

You: what about the refresh token flow?   # remembers the previous answer
Assistant: ...
```

### `askmycode index`
```bash
askmycode index .                 # index current directory
askmycode index /path/to/project  # index a specific path
```

Re-indexing is **incremental** — only changed files are re-embedded.

### `askmycode stats`
```bash
askmycode stats

Files indexed:  42
Total chunks:   187
Last indexed:   2026-05-23 14:30:01
Index location: /your/project/.askmycode
```

### `askmycode init`
```bash
askmycode init .
```
Detects your project type (Python, Go, Node, Rust...), adds `.askmycode/` to `.gitignore`, and prints suggested first questions.

### `askmycode config`
```bash
askmycode config set-key   YOUR_API_KEY
askmycode config set-provider  gemini      # gemini | openai | anthropic | ollama
askmycode config set-model     gpt-4o      # optional model override
askmycode config show
```

---

## Multiple providers

| Provider | Command | Notes |
|---|---|---|
| **Gemini** (default) | `config set-provider gemini` | Free tier at aistudio.google.com |
| **OpenAI** | `config set-provider openai` | Requires `OPENAI_API_KEY` |
| **Claude** | `config set-provider anthropic` | Requires `ANTHROPIC_API_KEY` |
| **Ollama** | `config set-provider ollama` | 100% offline, no API key |

### Fully offline with Ollama
```bash
# 1. Install Ollama: https://ollama.com
# 2. Pull a model
ollama pull llama3

# 3. Use it
askmycode config set-provider ollama
askmycode config set-model llama3
askmycode ask "how does this work?"   # zero internet required
```

---

## Per-project config

Commit an `.askmycode.toml` to share settings with your team:

```toml
[askmycode]
provider = "gemini"
model = "gemini-2.5-flash-lite"
n_results = 10
```

---

## GitHub Action

Add AI-powered Q&A directly to your pull requests. Team members comment `/ask <question>` and get an instant answer.

**Setup:**
1. Add your API key as a repository secret: `GEMINI_API_KEY`
2. Create `.github/workflows/askmycode.yml` (see [example](.github/workflows/askmycode.yml))

**Usage in a PR:**
```
/ask where is error handling for the payment flow?
```

The bot replies with the answer + source file references, inline in the PR.

---

## Privacy

| What happens | Where it goes |
|---|---|
| Your full codebase | **Stays on your machine** |
| Embeddings (vector index) | **Stored in `.askmycode/` in your project** |
| Your question + ~500 lines of relevant code | Sent to the LLM API |

Use `--provider ollama` for zero data leaving your machine.

---

## Supported file types

Python · JavaScript · TypeScript · Go · Rust · Java · C/C++ · Ruby · PHP · Swift · Kotlin · Scala · Shell · SQL · YAML · JSON · TOML · Markdown · HTML · CSS · Vue · Svelte

Python files are chunked at **function and class boundaries** using AST parsing, giving higher-quality retrieval than fixed-size splitting.

---

## How retrieval works (technical)

1. **Index:** Files are chunked (AST-aware for Python, sliding window for others), embedded with `all-MiniLM-L6-v2`, and stored in a local ChromaDB.
2. **Query:** Your question is embedded. The top `n × 3` candidates are fetched by cosine similarity, then re-ranked with a cross-encoder (`ms-marco-MiniLM-L-6-v2`) for higher precision.
3. **Answer:** The top N chunks + a project file tree are sent to the LLM with a developer-focused system prompt. The answer streams back in real time.

---

## Roadmap

- [ ] VS Code extension
- [ ] Watch mode (auto re-index on file save)
- [ ] Semantic diff Q&A (`askmycode ask` about uncommitted changes)
- [ ] Kotlin / Swift AST chunking
- [ ] Web UI

---

## Contributing

PRs welcome. Run the tool against itself to test:
```bash
askmycode index .
askmycode ask "how does the indexer work?"
```

---

## License

MIT
