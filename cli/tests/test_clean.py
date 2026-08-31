from ltel.main import app


def _run_clean(runner, status_output, confirm_value, mocker):
    """Invoke `ltel clean` with mocked script output and confirmation."""
    mocker.patch("ltel.backend.confirm", return_value=confirm_value)
    fake = mocker.patch("ltel.backend._run_clean_script")
    fake.side_effect = lambda args: status_output if "--status" in args else ""
    result = runner.invoke(app, ["clean"])
    calls = [c.args for c in fake.call_args_list]
    return result, calls


class TestClean:
    def test_empty_db(self, runner, mocker):
        result, calls = _run_clean(runner, "seed_rows=0\ntotal_rows=0\n", True, mocker)
        assert result.exit_code == 0
        assert "already empty" in result.stdout
        assert calls == [(["--status"],)]

    def test_seed_data_deleted_on_confirm(self, runner, mocker):
        result, calls = _run_clean(runner, "seed_rows=3\ntotal_rows=3\n", True, mocker)
        assert result.exit_code == 0
        assert "Deleted 3 seeded" in result.stdout
        assert calls == [(["--status"],), (["--seed"],)]

    def test_seed_data_cancelled(self, runner, mocker):
        result, calls = _run_clean(runner, "seed_rows=3\ntotal_rows=3\n", False, mocker)
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        assert calls == [(["--status"],)]

    def test_no_seed_offers_full_wipe_on_confirm(self, runner, mocker):
        result, calls = _run_clean(runner, "seed_rows=0\ntotal_rows=7\n", True, mocker)
        assert result.exit_code == 0
        assert "Wiped the entire database (7 rows)" in result.stdout
        assert calls == [(["--status"],), (["--all"],)]

    def test_no_seed_offers_full_wipe_on_decline(self, runner, mocker):
        result, calls = _run_clean(runner, "seed_rows=0\ntotal_rows=7\n", False, mocker)
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout
        assert calls == [(["--status"],)]

    def test_seed_rows_kept_others(self, runner, mocker):
        """When seed rows exist alongside real data, only seed rows are targeted."""
        result, calls = _run_clean(runner, "seed_rows=2\ntotal_rows=10\n", True, mocker)
        assert result.exit_code == 0
        assert "Deleted 2 seeded" in result.stdout
        assert calls == [(["--status"],), (["--seed"],)]