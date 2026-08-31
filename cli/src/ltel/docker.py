import subprocess
from pathlib import Path

import typer
from ltel._interactive import console

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_COMPOSE = _PROJECT_ROOT / "docker-compose.yml"
_COMPOSE_DEV = _PROJECT_ROOT / "docker-compose.dev.yml"


def _compose_file(*, dev: bool) -> str:
    return str(_COMPOSE_DEV if dev else _COMPOSE)


def cmd_up(service: str | None = None) -> None:
    console.print("[bold]Building and starting containers...[/bold]")
    cmd = ["docker", "compose", "-f", _compose_file(dev=True), "up", "-d", "--build"]
    if service:
        cmd.append(service)
    code = subprocess.call(cmd, cwd=str(_PROJECT_ROOT))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_down() -> None:
    console.print("[bold]Stopping and removing containers...[/bold]")
    code = subprocess.call(
        ["docker", "compose", "-f", _compose_file(dev=True), "down"],
        cwd=str(_PROJECT_ROOT),
    )
    if code != 0:
        raise typer.Exit(code=code)


def cmd_logs(*, follow: bool, service: str | None = None) -> None:
    cmd = ["docker", "compose", "-f", _compose_file(dev=True), "logs"]
    if follow:
        cmd.append("--follow")
    if service:
        cmd.append(service)
    code = subprocess.call(cmd, cwd=str(_PROJECT_ROOT))
    if code != 0:
        raise typer.Exit(code=code)


def cmd_status() -> None:
    console.print("[bold]Container status:[/bold]")
    code = subprocess.call(
        ["docker", "compose", "-f", _compose_file(dev=True), "ps"],
        cwd=str(_PROJECT_ROOT),
    )
    if code != 0:
        raise typer.Exit(code=code)