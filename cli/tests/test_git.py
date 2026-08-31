import subprocess

import pytest

from ltel._git import (
    GitError,
    has_uncommitted_changes,
    current_branch,
    local_branches,
    remote_origin_branches,
    checkout,
    merge,
    push,
    fetch,
    get_upstream_branch,
    create_branch,
    delete_branch,
    push_and_set_upstream,
)


class TestHasUncommittedChanges:
    def test_no_changes(self, mock_subprocess):
        mock_subprocess(stdout="")
        assert not has_uncommitted_changes()

    def test_unstaged_changes(self, mock_subprocess):
        mock_subprocess(stdout=" M src/file.py\n?? new.py\n")
        assert has_uncommitted_changes()

    def test_staged_changes(self, mock_subprocess):
        mock_subprocess(stdout="M  src/file.py\n")
        assert has_uncommitted_changes()


class TestCurrentBranch:
    def test_returns_branch_name(self, mock_subprocess):
        mock_subprocess(stdout="main\n")
        assert current_branch() == "main"

    def test_strips_whitespace(self, mock_subprocess):
        mock_subprocess(stdout="  feature/foo  \n")
        assert current_branch() == "feature/foo"


class TestLocalBranches:
    def test_returns_list(self, mock_subprocess):
        mock_subprocess(stdout="main\ndevelop\nfeature/foo\n")
        assert local_branches() == ["main", "develop", "feature/foo"]

    def test_empty(self, mock_subprocess):
        mock_subprocess(stdout="")
        assert local_branches() == []


class TestRemoteOriginBranches:
    def test_filters_origin_prefix(self, mock_subprocess):
        mock_subprocess(
            stdout="origin/HEAD\norigin/main\norigin/develop\norigin/feat/x\n"
        )
        assert remote_origin_branches() == ["main", "develop", "feat/x"]

    def test_empty(self, mock_subprocess):
        mock_subprocess(stdout="")
        assert remote_origin_branches() == []


class TestCheckout:
    def test_calls_without_capture(self, mocker):
        mock = mocker.patch("subprocess.run")
        checkout("develop")
        assert "capture_output" not in mock.call_args.kwargs


class TestMerge:
    def test_calls_with_origin_prefix(self, mocker):
        mock = mocker.patch("subprocess.run")
        merge("develop")
        cmd = mock.call_args[0][0]
        assert cmd == ["git", "merge", "origin/develop"]


class TestPush:
    def test_calls_interactive(self, mocker):
        mock = mocker.patch("subprocess.run")
        push()
        assert mock.call_args[0][0] == ["git", "push"]


class TestFetch:
    def test_calls_correct_args(self, mock_subprocess):
        mock_run = mock_subprocess()
        fetch()
        assert mock_run.call_args[0][0] == ["git", "fetch", "origin"]


class TestGetUpstreamBranch:
    def test_returns_stripped(self, mock_subprocess):
        mock_subprocess(stdout="origin/develop\n")
        assert get_upstream_branch() == "develop"

    def test_no_upstream(self, mocker):
        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, ["git"]))
        assert get_upstream_branch() is None


class TestCreateBranch:
    def test_calls_correct_args(self, mock_subprocess):
        mock_run = mock_subprocess()
        create_branch("feat", "develop")
        assert mock_run.call_args[0][0] == ["git", "branch", "feat", "develop"]


class TestDeleteBranch:
    def test_calls_force_delete(self, mock_subprocess):
        mock_run = mock_subprocess()
        delete_branch("feat")
        assert mock_run.call_args[0][0] == ["git", "branch", "-D", "feat"]


class TestPushAndSetUpstream:
    def test_calls_interactive(self, mocker):
        mock = mocker.patch("subprocess.run")
        push_and_set_upstream("feat")
        assert mock.call_args[0][0] == ["git", "push", "--set-upstream", "origin", "feat"]


class TestGitError:
    def test_raises_on_file_not_found(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        with pytest.raises(GitError, match="git is not installed"):
            current_branch()

    def test_raises_on_nonzero_exit(self, mocker):
        mocker.patch("subprocess.run", side_effect=subprocess.CalledProcessError(128, ["git"], stderr="fatal: not a git repository"))
        with pytest.raises(GitError, match="not a git repository"):
            current_branch()