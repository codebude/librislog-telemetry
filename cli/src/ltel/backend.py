"""Backend dev commands: run the server, run migrations, seed/clean sample data."""

import subprocess
from pathlib import Path

import typer
from ltel._interactive import confirm, console

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND = _PROJECT_ROOT / "backend"


def _run_uv(args: list[str]) -> int:
    return subprocess.call(["uv", "run", *args], cwd=str(_BACKEND))


def _run_clean_script(script_args: list[str]) -> str:
    """Run the clean script, returning its captured stdout."""
    proc = subprocess.run(
        ["uv", "run", "python", "scripts/clean.py", *script_args],
        cwd=str(_BACKEND),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        console.print(f"[red]Clean script failed: {proc.stderr.strip()}[/red]")
        raise typer.Exit(code=1)
    return proc.stdout


def _parse_count(stdout: str, key: str) -> int:
    """Parse ``key=NN`` from the clean script's --status output."""
    for line in stdout.splitlines():
        name, _, value = line.partition("=")
        if name == key:
            return int(value)
    return 0


def cmd_run(*, reload: bool, port: int) -> None:
    console.print(f"[bold]Starting backend on http://127.0.0.1:{port}[/bold]")
    args = ["uvicorn", "app.main:app", "--port", str(port), "--use-colors", "--no-access-log"]
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
    """Insert *count* fake installations with plausible values.

    Applies pending migrations first (idempotent) so seeding works on a
    freshly-cloned checkout without requiring a manual ``ltel migrate``.
    """
    code = _run_uv(["alembic", "upgrade", "head"])
    if code != 0:
        console.print("[red]Migrations failed — seed aborted.[/red]")
        raise typer.Exit(code=code)
    console.print(f"[bold]Seeding {count} fake installations...[/bold]")
    code = _run_uv(["python", "scripts/seed.py", str(count)])
    if code != 0:
        raise typer.Exit(code=code)


def cmd_clean() -> None:
    """Remove seeded test data.

    Seed rows are identified by their ``seed-`` installation-id prefix. If no
    seed rows exist but the database still contains data (seed rows can't be
    identified uniquely), the user is offered a full wipe instead.
    """
    stdout = _run_clean_script(["--status"])
    seed_count = _parse_count(stdout, "seed_rows")
    total_count = _parse_count(stdout, "total_rows")

    if seed_count == 0 and total_count == 0:
        console.print("[yellow]Database is already empty — nothing to clean.[/yellow]")
        raise typer.Exit()

    if seed_count > 0:
        console.print(
            f"[yellow]Found {seed_count} seeded installation(s) "
            f"(installation_id prefix 'seed-').[/yellow]"
        )
        if not confirm("Delete the seeded test data?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit()
        _run_clean_script(["--seed"])
        console.print(f"[green]Deleted {seed_count} seeded installation(s).[/green]")
        return

    console.print(
        f"[yellow]No seed rows found, but the database contains {total_count} "
        f"installation row(s) that cannot be identified as test data.[/yellow]"
    )
    if not confirm(
        "No seed data can be identified. Wipe the ENTIRE database "
        f"(all {total_count} rows)?",
        default=False,
    ):
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()
    _run_clean_script(["--all"])
    console.print(f"[green]Wiped the entire database ({total_count} rows).[/green]")


def cmd_prune(days: int | None = None) -> None:
    """Move stale installations (not seen for *days*) to the pruned table.

    Keeps their IDs and event counts, so all-time totals stay exact. Defaults
    to ``PRUNE_AFTER_DAYS`` (365).
    """
    args = ["python", "scripts/prune.py"]
    if days is not None:
        args.append(str(days))
    code = _run_uv(args)
    if code != 0:
        raise typer.Exit(code=code)