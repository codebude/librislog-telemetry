import typer
from ltel._interactive import console

app = typer.Typer(
    name="ltel",
    help="LibrisLog Telemetry developer CLI",
    rich_markup_mode="rich",
    pretty_exceptions_show_locals=False,
)

test_app = typer.Typer(
    name="test",
    help="Run test suites",
    rich_markup_mode="rich",
)
docker_app = typer.Typer(
    name="docker",
    help="Manage Docker containers (up, down, logs, status)",
    rich_markup_mode="rich",
)
pr_app = typer.Typer(
    name="pr",
    help="Manage pull requests (create, merge, list)",
    rich_markup_mode="rich",
)
branch_app = typer.Typer(
    name="branch",
    help="Manage branches (create, delete, sync)",
    rich_markup_mode="rich",
)
app.add_typer(test_app)
app.add_typer(docker_app)
app.add_typer(pr_app)
app.add_typer(branch_app)


@app.command("run")
def run_backend(
    reload: bool = typer.Option(True, "--no-reload", help="Disable auto-reload"),
    port: int = typer.Option(8001, "--port", help="Port to listen on"),
):
    """Run the backend API server."""
    from ltel.backend import cmd_run
    cmd_run(reload=reload, port=port)


@app.command("migrate")
def migrate():
    """Apply database migrations (alembic upgrade head)."""
    from ltel.backend import cmd_migrate
    cmd_migrate()


@app.command("seed")
def seed(
    count: int = typer.Option(25, "--count", help="Number of fake installations to seed"),
):
    """Seed the database with fake telemetry data for local dashboard development."""
    from ltel.backend import cmd_seed
    cmd_seed(count)


@app.command("clean")
def clean():
    """Remove seeded test data (or wipe the DB if seed rows can't be identified)."""
    from ltel.backend import cmd_clean
    cmd_clean()


@test_app.command("backend")
def test_backend():
    """Run backend pytest with coverage."""
    from ltel.test import cmd_backend
    cmd_backend()


@test_app.command("all")
def test_all():
    """Run all test suites and print a summary."""
    from ltel.test import cmd_all
    cmd_all()


@docker_app.command("up")
def docker_up(
    service: str | None = typer.Argument(None, help="Service to build and start (default: all)"),
):
    """Build and start containers (optionally a single service)."""
    from ltel.docker import cmd_up
    cmd_up(service)


@docker_app.command("down")
def docker_down():
    """Stop and remove containers."""
    from ltel.docker import cmd_down
    cmd_down()


@docker_app.command("logs")
def docker_logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    service: str | None = typer.Argument(None, help="Service name"),
):
    """View container logs."""
    from ltel.docker import cmd_logs
    cmd_logs(follow=follow, service=service)


@docker_app.command("status")
def docker_status():
    """Show container status."""
    from ltel.docker import cmd_status
    cmd_status()


@pr_app.command("list")
def pr_list():
    """List open pull requests."""
    from ltel.pr import cmd_list
    cmd_list()


@pr_app.command("create")
def pr_create():
    """Create a pull request with interactive branch selection."""
    from ltel.pr import cmd_create
    cmd_create()


@pr_app.command("merge")
def pr_merge():
    """Merge an open pull request."""
    from ltel.pr import cmd_merge
    cmd_merge()


@branch_app.command("create")
def branch_create():
    """Create a new branch from a base branch."""
    from ltel.branch import cmd_create
    cmd_create()


@branch_app.command("delete")
def branch_delete():
    """Delete a local branch."""
    from ltel.branch import cmd_delete
    cmd_delete()


@branch_app.command("sync")
def branch_sync():
    """Sync current branch with an origin branch."""
    from ltel.sync import cmd_sync
    cmd_sync()