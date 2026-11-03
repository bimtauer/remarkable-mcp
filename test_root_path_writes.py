"""REMARKABLE_ROOT_PATH confines write tools the same way it confines reads (#209)."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from remarkable_mcp import write_tools


def _item(id_, name, parent="", folder=False):
    return SimpleNamespace(
        ID=id_, VissibleName=name, Parent=parent, is_folder=folder, is_cloud_archived=False
    )


# /Claude (root), /Claude/Meetings, a same-named document inside and outside the root,
# plus look-alikes whose *path strings* match the root but whose parent chain does not:
# a trashed "Claude" folder, a top-level folder literally named "Claude/Meetings",
# and a trashed "Old" folder.
COLLECTION = [
    _item("trashed-root", "Claude", parent="trash", folder=True),
    _item("ghost", "Ghost", parent="trashed-root"),
    _item("slash", "Claude/Meetings", folder=True),
    _item("slash-doc", "Slash Doc", parent="slash"),
    _item("root", "Claude", folder=True),
    _item("meet", "Meetings", parent="root", folder=True),
    _item("outside-meet", "Meetings", folder=True),
    _item("probe-out", "Delete Probe"),
    _item("probe-in", "Delete Probe", parent="root"),
    _item("only-out", "Private Notes"),
    _item("old", "Old", parent="trash", folder=True),
]
BY_ID = {i.ID: i for i in COLLECTION}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("REMARKABLE_ROOT_PATH", "/Claude")
    fake = Mock()
    fake.get_meta_items.return_value = COLLECTION
    with patch.object(write_tools, "get_rmapi", return_value=fake):
        yield fake


def test_bare_name_delete_targets_the_copy_inside_root(client):
    data = json.loads(write_tools._cloud_delete("Delete Probe"))
    client.delete.assert_called_once_with("probe-in")
    assert data["path"] == "/Delete Probe"


def test_documents_outside_root_are_unreachable(client):
    for call in (
        lambda: write_tools._cloud_delete("Private Notes"),
        lambda: write_tools._cloud_move("Private Notes", "/Meetings"),
        lambda: write_tools._cloud_rename("Private Notes", "x"),
    ):
        data = json.loads(call())
        assert data["_error"]["type"] == "document_not_found"
        assert "Private Notes" not in json.dumps(data["_error"].get("did_you_mean") or [])
    client.delete.assert_not_called()
    client.move.assert_not_called()


def test_absolute_device_path_is_not_a_back_door(client):
    data = json.loads(write_tools._cloud_delete("/Private Notes"))
    assert data["_error"]["type"] == "document_not_found"
    client.delete.assert_not_called()


def test_root_folder_itself_cannot_be_targeted(client):
    data = json.loads(write_tools._cloud_delete("Claude"))
    assert data["_error"]["type"] == "document_not_found"
    client.delete.assert_not_called()


def test_folder_paths_are_root_relative(client):
    by_id = {i.ID: i for i in COLLECTION}
    assert write_tools._resolve_parent_id("/", by_id, COLLECTION) == "root"
    assert write_tools._resolve_parent_id("/Meetings", by_id, COLLECTION) == "meet"
    assert write_tools._resolve_parent_id("/Claude/Meetings", by_id, COLLECTION) is None


def test_move_reports_root_relative_paths(client):
    data = json.loads(write_tools._cloud_move("/Delete Probe", "/Meetings"))
    client.move.assert_called_once_with("probe-in", "meet")
    assert data["from"] == "/Delete Probe"


def test_unscoped_server_keeps_whole_tablet_access(monkeypatch):
    monkeypatch.delenv("REMARKABLE_ROOT_PATH", raising=False)
    by_id = {i.ID: i for i in COLLECTION}
    assert write_tools._resolve_parent_id("/", by_id, COLLECTION) == ""
    assert write_tools._resolve_document("Private Notes", COLLECTION, by_id).ID == "only-out"


def test_lookalike_paths_outside_root_are_unreachable(client):
    for name in ("Ghost", "/Ghost", "Slash Doc", "/Meetings/Slash Doc"):
        data = json.loads(write_tools._cloud_delete(name))
        assert data["_error"]["type"] == "document_not_found", name
    client.delete.assert_not_called()
    assert write_tools._resolve_parent_id("/", BY_ID, COLLECTION) == "root"
    assert write_tools._resolve_parent_id("/Meetings", BY_ID, COLLECTION) == "meet"


def test_ambiguous_root_fails_closed(monkeypatch):
    monkeypatch.setenv("REMARKABLE_ROOT_PATH", "/Claude")
    collection = COLLECTION + [_item("root2", "claude", folder=True)]
    by_id = {i.ID: i for i in collection}
    assert write_tools._resolve_parent_id("/", by_id, collection) is None
    assert write_tools._resolve_document("Delete Probe", collection, by_id) is None


def test_trashed_folder_is_not_a_move_target(monkeypatch):
    monkeypatch.delenv("REMARKABLE_ROOT_PATH", raising=False)
    fake = Mock()
    fake.get_meta_items.return_value = COLLECTION
    with patch.object(write_tools, "get_rmapi", return_value=fake):
        data = json.loads(write_tools._cloud_move("Private Notes", "/Old"))
    assert data["_error"]["type"] == "folder_not_found"
    fake.move.assert_not_called()
