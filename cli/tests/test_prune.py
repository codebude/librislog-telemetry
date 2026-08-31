from ltel.main import app


class TestPrune:
    def test_prune_default(self, runner, mocker):
        mock_uv = mocker.patch("ltel.backend._run_uv", return_value=0)
        result = runner.invoke(app, ["prune"])
        assert result.exit_code == 0
        calls = [c.args[0] for c in mock_uv.call_args_list]
        assert calls == [["python", "scripts/prune.py"]]

    def test_prune_with_days(self, runner, mocker):
        mock_uv = mocker.patch("ltel.backend._run_uv", return_value=0)
        result = runner.invoke(app, ["prune", "--days", "45"])
        assert result.exit_code == 0
        calls = [c.args[0] for c in mock_uv.call_args_list]
        assert calls == [["python", "scripts/prune.py", "45"]]

    def test_prune_failure_exits_nonzero(self, runner, mocker):
        mocker.patch("ltel.backend._run_uv", return_value=1)
        result = runner.invoke(app, ["prune"])
        assert result.exit_code == 1