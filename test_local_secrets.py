"""The device token and cached library content stay private to the local user."""

import os
import stat
from unittest.mock import patch

import pytest

from remarkable_mcp import api
from remarkable_mcp.sync import RemarkableClient


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(api.Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_registered_token_is_owner_only_even_over_existing_file(home):
    token_file = home / ".rmapi"
    token_file.write_text("old")
    token_file.chmod(0o644)
    with patch("remarkable_mcp.sync.register_device", return_value={"devicetoken": "t"}):
        api.register_and_get_token("code")
    assert _mode(token_file) == 0o600
    assert "devicetoken" in token_file.read_text()


def test_register_refuses_to_follow_symlinked_token_file(home):
    target = home / "elsewhere"
    target.write_text("keep")
    (home / ".rmapi").symlink_to(target)
    with patch("remarkable_mcp.sync.register_device", return_value={"devicetoken": "t"}):
        with pytest.raises(RuntimeError):
            api.register_and_get_token("code")
    assert target.read_text() == "keep"


@pytest.mark.parametrize("bad", ["/etc/passwd", "../../.ssh/id_ed25519", "a/b", ".hidden"])
@patch("remarkable_mcp.sync._http_request_with_retry")
def test_index_hashes_cannot_address_local_files(mock_request, bad):
    client = RemarkableClient(user_token="user-token")
    with pytest.raises(ValueError):
        client._get_file(bad, "doc.pdf")
    mock_request.assert_not_called()


@patch("remarkable_mcp.sync._http_request_with_retry")
def test_blob_cache_directory_is_owner_only(mock_request, tmp_path, monkeypatch):
    cache = tmp_path / "blobs"
    monkeypatch.setenv("REMARKABLE_CACHE_DIR", str(cache))
    monkeypatch.delenv("REMARKABLE_DISABLE_CACHE", raising=False)
    mock_request.return_value.status_code = 200
    mock_request.return_value.content = b"page"
    RemarkableClient(user_token="user-token")._get_file("a" * 64, "doc.rm")
    assert _mode(cache) == 0o700
