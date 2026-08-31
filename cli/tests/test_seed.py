from ltel.main import app


class TestSeed:
    def test_runs_migrations_then_seeds(self, runner, mocker):
        mock_uv = mocker.patch("ltel.backend._run_uv", return_value=0)
        result = runner.invoke(app, ["seed", "--count", "10"])
        assert result.exit_code == 0
        assert "Seeding 10 fake installations" in result.stdout
        calls = [c.args[0] for c in mock_uv.call_args_list]
        assert calls == [
            ["alembic", "upgrade", "head"],
            ["python", "scripts/seed.py", "10"],
        ]

    def test_migration_failure_aborts_seed(self, runner, mocker):
        mock_uv = mocker.patch("ltel.backend._run_uv", return_value=1)
        result = runner.invoke(app, ["seed", "--count", "10"])
        assert result.exit_code == 1
        assert "Migrations failed" in result.stdout
        assert "seed.py" not in [c.args[0] for c in mock_uv.call_args_list]