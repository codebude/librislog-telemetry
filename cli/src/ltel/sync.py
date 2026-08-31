import typer
import ltel._git
import ltel._interactive
from ltel._interactive import console


def cmd_sync() -> None:
    try:
        ltel._git.fetch()
    except Exception:
        console.print("[red]Failed to fetch from origin.[/red]")
        raise typer.Exit(code=1)

    cur = ltel._git.current_branch()
    console.print(f"Current branch: [bold]{cur}[/bold]")

    try:
        remotes = ltel._git.remote_origin_branches()
    except Exception:
        console.print("[red]Failed to list remote branches.[/red]")
        raise typer.Exit(code=1)

    candidates = [b for b in remotes if b != cur]
    upstream = ltel._git.get_upstream_branch()
    preselect = upstream if upstream in candidates else None

    target = ltel._interactive.select_from_list(
        candidates,
        title="Select origin branch to merge into current",
        preselect=preselect,
    )
    if target is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    try:
        console.print(f"Merging [bold]origin/{target}[/bold] into [bold]{cur}[/bold]...")
        ltel._git.merge(target)
        ltel._git.push()
        console.print(f"[green]Branch {cur} synced with origin/{target}![/green]")
    except Exception as exc:
        console.print(f"[red]Sync failed: {exc}[/red]")
        raise typer.Exit(code=1)