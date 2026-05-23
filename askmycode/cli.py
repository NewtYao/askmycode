import os
from pathlib import Path

import typer
from google.genai.errors import ClientError, ServerError
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from askmycode import config, indexer, llm, manifest, project_config, retriever, store

app = typer.Typer(
    name="askmycode",
    help="Ask questions about any codebase using AI — your code stays private.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command()
def index(
    path: Path = typer.Argument(Path("."), help="Path to the codebase to index"),
) -> None:
    """Scan and index a codebase so you can ask questions about it."""
    path = path.resolve()
    if not path.exists():
        console.print(f"[red]Path does not exist:[/red] {path}")
        raise typer.Exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Starting...", total=None)

        def on_progress(msg: str) -> None:
            progress.update(task, description=msg)

        n_files, n_chunks = indexer.index_directory(path, progress_callback=on_progress)

    if n_files == 0:
        console.print("[yellow]No supported files found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[green]Indexed {n_files} files → {n_chunks} chunks[/green]  (.askmycode/)")
    console.print('[dim]Now run:  askmycode ask "your question"[/dim]')


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question about your codebase"),
    project: Path = typer.Option(Path("."), "--project", "-p", help="Path to the indexed project"),
    n_results: int = typer.Option(8, "--results", "-n", help="Chunks to retrieve"),
    sources: bool = typer.Option(False, "--sources", "-s", help="Show source files used to answer"),
    provider: str = typer.Option("", "--provider", help="LLM provider: gemini, openai, anthropic, ollama"),
    model: str = typer.Option("", "--model", help="Model name override"),
) -> None:
    """Ask a question about your indexed codebase."""
    project = project.resolve()
    pcfg = project_config.load(project)
    provider = provider or pcfg["provider"] or config.get_provider()
    model = model or pcfg["model"] or config.get_model()
    n_results = n_results if n_results != 8 else pcfg["n_results"]

    api_key = config.get_api_key(provider)
    if not api_key and provider != "ollama":
        console.print(f"[red]No API key found for provider '{provider}'.[/red]")
        console.print(f"  [bold]export {provider.upper()}_API_KEY=your-key[/bold]")
        console.print("  [bold]askmycode config set-key YOUR_KEY[/bold]")
        raise typer.Exit(1)

    if not (project / ".askmycode").exists():
        console.print(f"[red]No index found.[/red]  Run first:")
        console.print(f"  [bold]askmycode index {project}[/bold]")
        raise typer.Exit(1)

    with console.status("Searching codebase..."):
        context, metadatas = retriever.retrieve(question, project, n_results=n_results)

    if not context:
        console.print("[yellow]No relevant code found for that question.[/yellow]")
        raise typer.Exit(0)

    file_tree = llm.build_file_tree(list(manifest.load(project).keys()))

    console.print()
    try:
        for chunk in llm.answer_stream(
            question, context, api_key or "", file_tree=file_tree,
            provider=provider, model=model,
        ):
            console.print(chunk, end="")
        console.print("\n")
    except ClientError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            console.print("\n[red]Quota exceeded.[/red] Your API key has no free tier quota.")
            console.print("Get a fresh key at [bold]aistudio.google.com[/bold] → Get API key → Create API key in new project")
            console.print("Then run: [bold]askmycode config set-key YOUR_NEW_KEY[/bold]")
        elif "401" in str(e) or "API_KEY_INVALID" in str(e):
            console.print("\n[red]Invalid API key.[/red] Run: [bold]askmycode config set-key YOUR_KEY[/bold]")
        else:
            console.print(f"\n[red]API error:[/red] {e}")
        raise typer.Exit(1)
    except ServerError as e:
        console.print(f"\n[red]Gemini server error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if sources and metadatas:
        seen: set = set()
        console.print("[dim]─── Sources ────────────────────────────[/dim]")
        for m in metadatas:
            key = (m.get("file_path", ""), m.get("start_line", ""))
            if key in seen:
                continue
            seen.add(key)
            console.print(f"[dim]  {m.get('file_path')}:{m.get('start_line')}–{m.get('end_line')}[/dim]")


@app.command()
def init(
    path: Path = typer.Argument(Path("."), help="Project root to initialise"),
) -> None:
    """Set up askmycode for a project: update .gitignore and suggest first steps."""
    path = path.resolve()

    # Detect project type from marker files
    markers: dict[str, list[str]] = {
        "Python":     ["pyproject.toml", "setup.py", "requirements.txt"],
        "Node/TS":    ["package.json"],
        "Go":         ["go.mod"],
        "Rust":       ["Cargo.toml"],
        "Java/Kotlin":["pom.xml", "build.gradle", "build.gradle.kts"],
        "Ruby":       ["Gemfile"],
    }
    detected = "Unknown"
    for lang, files in markers.items():
        if any((path / f).exists() for f in files):
            detected = lang
            break

    # Ensure .askmycode/ is in .gitignore
    gitignore = path / ".gitignore"
    entry = ".askmycode/"
    if gitignore.exists():
        content = gitignore.read_text()
        if entry not in content:
            gitignore.write_text(content.rstrip() + f"\n{entry}\n")
            console.print(f"[green]Added {entry} to .gitignore[/green]")
        else:
            console.print(f"[dim]{entry} already in .gitignore[/dim]")
    else:
        gitignore.write_text(f"{entry}\n")
        console.print(f"[green]Created .gitignore with {entry}[/green]")

    console.print(f"\n[bold]Detected project type:[/bold] {detected}")

    # Suggested starter questions per language
    suggestions: dict[str, list[str]] = {
        "Python":     ["how is the project structured?", "where is the entry point?", "how are dependencies managed?"],
        "Node/TS":    ["what does the main script do?", "how is routing handled?", "what testing framework is used?"],
        "Go":         ["what is the main package?", "how is error handling done?", "where are the HTTP handlers?"],
        "Rust":       ["what does the main function do?", "how are errors propagated?", "what external crates are used?"],
        "Java/Kotlin":["what is the application entry point?", "how is the project layered?", "where are the models defined?"],
        "Ruby":       ["what does the application do?", "how is routing set up?", "where is business logic?"],
        "Unknown":    ["how is the project structured?", "what does this codebase do?", "where is the main entry point?"],
    }
    console.print("\n[bold]Suggested first questions:[/bold]")
    for q in suggestions.get(detected, suggestions["Unknown"]):
        console.print(f'  askmycode ask "{q}"')

    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  1. askmycode index {path}")
    console.print(f'  2. askmycode ask "how is the project structured?"')


@app.command()
def chat(
    project: Path = typer.Option(Path("."), "--project", "-p", help="Path to the indexed project"),
    n_results: int = typer.Option(8, "--results", "-n", help="Chunks to retrieve per turn"),
    provider: str = typer.Option("", "--provider", help="LLM provider: gemini, openai, anthropic, ollama"),
    model: str = typer.Option("", "--model", help="Model name override"),
) -> None:
    """Start an interactive multi-turn chat session about your codebase."""
    project = project.resolve()
    pcfg = project_config.load(project)
    provider = provider or pcfg["provider"] or config.get_provider()
    model = model or pcfg["model"] or config.get_model()
    n_results = n_results if n_results != 8 else pcfg["n_results"]

    api_key = config.get_api_key(provider)
    if not api_key and provider != "ollama":
        console.print(f"[red]No API key found for provider '{provider}'.[/red]  Run: [bold]askmycode config set-key YOUR_KEY[/bold]")
        raise typer.Exit(1)

    if not (project / ".askmycode").exists():
        console.print(f"[red]No index found.[/red]  Run: [bold]askmycode index {project}[/bold]")
        raise typer.Exit(1)

    console.print("[bold]askmycode chat[/bold] — type your question, [dim]exit[/dim] or Ctrl+C to quit.\n")

    history: list[dict] = []
    file_tree = llm.build_file_tree(list(manifest.load(project).keys()))

    while True:
        try:
            question = console.input("[bold cyan]You:[/bold cyan] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye.[/dim]")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            console.print("[dim]Bye.[/dim]")
            break

        with console.status("Searching codebase..."):
            context, _ = retriever.retrieve(question, project, n_results=n_results)

        if not context:
            console.print("[yellow]No relevant code found for that question.[/yellow]\n")
            continue

        console.print("[bold green]Assistant:[/bold green] ", end="")
        answer_parts: list[str] = []
        try:
            for chunk in llm.answer_stream(
                question, context, api_key or "", history=history,
                file_tree=file_tree, provider=provider, model=model,
            ):
                console.print(chunk, end="")
                answer_parts.append(chunk)
            console.print("\n")
        except (ClientError, ServerError) as e:
            console.print(f"\n[red]Error:[/red] {e}\n")
            continue
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}\n")
            continue

        # Append this turn to history for follow-up context
        user_turn = f"Context:\n{context}\n\nQuestion: {question}"
        history.append({"role": "user", "content": user_turn})
        history.append({"role": "model", "content": "".join(answer_parts)})


@app.command()
def stats(
    project: Path = typer.Option(Path("."), "--project", "-p", help="Path to the indexed project"),
) -> None:
    """Show index statistics for a project."""
    import datetime
    project = project.resolve()
    index_path = project / ".askmycode"

    if not index_path.exists():
        console.print(f"[red]No index found.[/red]  Run: [bold]askmycode index {project}[/bold]")
        raise typer.Exit(1)

    mf = manifest.load(project)
    client = store.get_client(project)
    collection = store.get_collection(client)
    n_chunks = collection.count()

    last_modified = max((e["mtime"] for e in mf.values()), default=None)
    last_indexed = (
        datetime.datetime.fromtimestamp(last_modified).strftime("%Y-%m-%d %H:%M:%S")
        if last_modified else "unknown"
    )

    console.print(f"[bold]Files indexed:[/bold]  {len(mf)}")
    console.print(f"[bold]Total chunks:[/bold]   {n_chunks}")
    console.print(f"[bold]Last indexed:[/bold]   {last_indexed}")
    console.print(f"[bold]Index location:[/bold] {index_path}")


_config_app = typer.Typer(help="Manage configuration.")
app.add_typer(_config_app, name="config")


@_config_app.command("set-key")
def config_set_key(
    api_key: str = typer.Argument(..., help="Your API key"),
    provider: str = typer.Option("", "--provider", "-p", help="Provider this key is for (default: current provider)"),
) -> None:
    """Save your API key to ~/.config/askmycode/config.json."""
    prov = provider or config.get_provider()
    config.set_api_key(api_key, prov)
    console.print(f"[green]API key saved for provider '{prov}'.[/green]")


@_config_app.command("set-provider")
def config_set_provider(
    provider: str = typer.Argument(..., help="Provider: gemini, openai, anthropic, ollama"),
) -> None:
    """Set the default LLM provider."""
    valid = {"gemini", "openai", "anthropic", "ollama"}
    if provider not in valid:
        console.print(f"[red]Unknown provider.[/red] Choose: {', '.join(sorted(valid))}")
        raise typer.Exit(1)
    config.set_provider(provider)
    console.print(f"[green]Provider set to '{provider}'.[/green]")


@_config_app.command("set-model")
def config_set_model(
    model: str = typer.Argument(..., help="Model name, e.g. gpt-4o, llama3, claude-opus-4-7"),
) -> None:
    """Set the default model name."""
    config.set_model(model)
    console.print(f"[green]Model set to '{model}'.[/green]")


@_config_app.command("show")
def config_show() -> None:
    """Show current configuration."""
    console.print(f"[bold]Provider:[/bold] {config.get_provider()}")
    console.print(f"[bold]Model:[/bold]    {config.get_model() or '(default for provider)'}")
    key = config.get_api_key(config.get_provider())
    masked = (key[:8] + "..." + key[-4:]) if key and len(key) > 12 else ("(not set)" if not key else key)
    console.print(f"[bold]API key:[/bold]  {masked}")


if __name__ == "__main__":
    app()
