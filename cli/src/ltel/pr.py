import typer
import ltel._git
import ltel._gh
import ltel._interactive
from ltel._interactive import console


def cmd_create() -> None:
    try:
        ltel._git.current_branch()
    except Exception:
        console.print("[red]Not inside a git repository.[/red]")
        raise typer.Exit(code=1)

    try:
        ltel._gh.check_gh()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    try:
        if ltel._git.has_uncommitted_changes():
            if ltel._interactive.confirm("Uncommitted changes found. Commit first?", default=True):
                console.print("[yellow]Please commit your changes manually, then re-run.[/yellow]")
                raise typer.Exit()
    except typer.Exit:
        raise
    except Exception:
        console.print("[red]Failed to check for uncommitted changes.[/red]")
        raise typer.Exit(code=1)

    try:
        branches = ltel._git.remote_origin_branches()
        cur = ltel._git.current_branch()
    except Exception:
        console.print("[red]Failed to list remote branches.[/red]")
        raise typer.Exit(code=1)

    if cur not in branches:
        branches.append(cur)

    head = ltel._interactive.select_from_list(branches, title="Select head branch", preselect=cur)
    if head is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    base_candidates = [b for b in branches if b != head]
    base_preselect = "main" if head == "develop" else "develop"
    base = ltel._interactive.select_from_list(base_candidates, title="Select base branch", preselect=base_preselect)
    if base is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    console.print(f"Creating PR: [bold]{head}[/bold] → [bold]{base}[/bold]")
    try:
        ltel._gh.create_pr(base=base, head=head)
        console.print("[green]PR created successfully![/green]")
    except Exception as exc:
        console.print(f"[red]PR creation failed: {exc}[/red]")
        raise typer.Exit(code=1)


def cmd_merge() -> None:
    try:
        ltel._gh.check_gh()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    try:
        prs = ltel._gh.list_open_prs()
    except Exception as exc:
        console.print(f"[red]Failed to list PRs: {exc}[/red]")
        raise typer.Exit(code=1)

    if not prs:
        console.print("[yellow]No open pull requests.[/yellow]")
        raise typer.Exit()

    pr_lines = [f"#{pr['number']} — {pr['title']} ({pr['headRefName']} → {pr['baseRefName']})" for pr in prs]
    selected_line = ltel._interactive.select_from_list(pr_lines, title="Open Pull Requests")
    if selected_line is None:
        console.print("[yellow]Cancelled.[/yellow]")
        raise typer.Exit()

    idx = pr_lines.index(selected_line)
    selected_pr = prs[idx]
    pr_number = selected_pr["number"]

    console.print(f"Merging PR #[bold]{pr_number}[/bold]: {selected_pr['title']}")
    try:
        ltel._gh.merge_pr(pr_number)
        console.print(f"[green]PR #{pr_number} merged![/green]")
    except Exception as exc:
        console.print(f"[red]PR merge failed: {exc}[/red]")
        raise typer.Exit(code=1)


def cmd_list() -> None:
    try:
        ltel._gh.check_gh()
    except Exception as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    try:
        prs = ltel._gh.list_open_prs()
    except Exception as exc:
        console.print(f"[red]Failed to list PRs: {exc}[/red]")
        raise typer.Exit(code=1)

    if not prs:
        console.print("[yellow]No open pull requests.[/yellow]")
        raise typer.Exit()

    for pr in prs:
        author = pr.get("author", {}).get("login", "?")
        console.print(f"  #[bold]{pr['number']}[/bold] — {pr['title']} ({author})")