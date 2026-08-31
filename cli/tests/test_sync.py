from ltel.main import app


class TestSync:
    def test_basic_sync(self, runner, mocker):
        mocker.patch("ltel._git.fetch")
        mocker.patch("ltel._git.current_branch", return_value="my-feature")
        mocker.patch("ltel._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("ltel._git.get_upstream_branch", return_value="develop")
        mocker.patch("ltel._interactive.select_from_list", return_value="develop")
        mock_merge = mocker.patch("ltel._git.merge")
        mock_push = mocker.patch("ltel._git.push")

        result = runner.invoke(app, ["branch", "sync"])
        assert result.exit_code == 0
        mock_merge.assert_called_once_with("develop")
        mock_push.assert_called_once()

    def test_cancelled(self, runner, mocker):
        mocker.patch("ltel._git.fetch")
        mocker.patch("ltel._git.current_branch", return_value="my-feature")
        mocker.patch("ltel._git.remote_origin_branches", return_value=["main", "develop"])
        mocker.patch("ltel._interactive.select_from_list", return_value=None)

        result = runner.invoke(app, ["branch", "sync"])
        assert result.exit_code == 0