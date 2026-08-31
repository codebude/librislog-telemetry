"""Backend dev commands: run the server, run migrations, seed sample data."""

import subprocess
from pathlib import Path

import typer
from ltel._interactive import console

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND = _PROJECT_ROOT / "backend"


def _run_uv(args: list[str]) -> int:
    return subprocess.call(["uv", "run", *args], cwd=str(_BACKEND))


def cmd_run(*, reload: bool, port: int) -> None:
    console.print(f"[bold]Starting backend on http://127.0.0.1:{port}[/bold]")
    args = ["uvicorn", "app.main:app", "--port", str(port), "--use-colors"]
    if reload:
        args.append("--reload")
    code = _run_uv(args)
    if code != 0:
        raise typer.Exit(code=code)


def cmd_migrate() -> None:
    console.print("[bold]Applying database migrations...[/bold]")
    code = _run_uv(["alembic", "upgrade", "head"])
    if code != 0:
        raise typer.Exit(code=code)


def cmd_seed(count: int) -> None:
    """Insert *count* fake installations with plausible values."""
    console.print(f"[bold]Seeding {count} fake installations...[/bold]")
    code = _run_uv(["python", "scripts/seed.py", str(count)])
    if code != 0:
        raise typer.Exit(code=code)