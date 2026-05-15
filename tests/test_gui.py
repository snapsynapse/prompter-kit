import io
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import prompter_kit_gui
from prompter_kit import LIBRARY_KEY, list_scripts, load_script_json


@pytest.fixture()
def client():
    prompter_kit_gui.app.config.update(TESTING=True, PROMPTERKIT_BASE_DIR=None)
    with prompter_kit_gui.app.test_client() as client:
        yield client
    prompter_kit_gui.app.config.update(PROMPTERKIT_BASE_DIR=None)


@pytest.fixture()
def configured_client(tmp_path):
    prompter_kit_gui.app.config.update(
        TESTING=True,
        PROMPTERKIT_BASE_DIR=str(tmp_path),
    )
    with prompter_kit_gui.app.test_client() as client:
        yield client, tmp_path
    prompter_kit_gui.app.config.update(PROMPTERKIT_BASE_DIR=None)


def _make_script(tmp_path, guid, name, chapters, index=0):
    texts_dir = tmp_path / "Texts"
    texts_dir.mkdir(exist_ok=True)
    data = {"GUID": guid, "friendlyName": name, "chapters": chapters, "index": index}
    (texts_dir / f"{guid}.json").write_text(json.dumps(data), encoding="utf-8")
    settings_path = tmp_path / "AppSettings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings.setdefault(LIBRARY_KEY, [])
    if guid not in settings[LIBRARY_KEY]:
        settings[LIBRARY_KEY].append(guid)
    settings_path.write_text(json.dumps(settings), encoding="utf-8")


def test_export_all_uses_unique_names_for_duplicate_friendly_names(client, monkeypatch):
    monkeypatch.setattr(
        prompter_kit_gui,
        "list_scripts",
        lambda base_dir=None: [
            {"guid": "GUID-ONE", "friendlyName": "Same Name", "index": 0, "path": "/tmp/1", "missing": False},
            {"guid": "GUID-TWO", "friendlyName": "Same Name", "index": 1, "path": "/tmp/2", "missing": False},
        ],
    )
    payloads = {
        "GUID-ONE": {"chapters": ["one"]},
        "GUID-TWO": {"chapters": ["two"]},
    }
    monkeypatch.setattr(prompter_kit_gui, "load_script_json", lambda guid, base_dir=None: payloads[guid])

    response = client.get("/export-all")
    assert response.status_code == 200

    archive = io.BytesIO(response.data)
    with zipfile.ZipFile(archive) as zf:
        assert sorted(zf.namelist()) == ["Same_Name.txt", "Same_Name_GUID-TWO.txt"]
        assert zf.read("Same_Name.txt").decode("utf-8") == "one\n"
        assert zf.read("Same_Name_GUID-TWO.txt").decode("utf-8") == "two\n"


def test_export_all_skips_missing_and_empty_scripts(client, monkeypatch):
    monkeypatch.setattr(
        prompter_kit_gui,
        "list_scripts",
        lambda base_dir=None: [
            {"guid": "GUID-ONE", "friendlyName": "Alpha", "index": 0, "path": "/tmp/1", "missing": False},
            {"guid": "GUID-TWO", "friendlyName": "Ghost", "index": 1, "path": "/tmp/2", "missing": True},
            {"guid": "GUID-THREE", "friendlyName": "Empty", "index": 2, "path": "/tmp/3", "missing": False},
        ],
    )
    payloads = {
        "GUID-ONE": {"chapters": ["one"]},
        "GUID-THREE": {"chapters": []},
    }
    monkeypatch.setattr(prompter_kit_gui, "load_script_json", lambda guid, base_dir=None: payloads[guid])

    response = client.get("/export-all")
    assert response.status_code == 200

    archive = io.BytesIO(response.data)
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == ["Alpha.txt"]
        assert zf.read("Alpha.txt").decode("utf-8") == "one\n"


def test_import_uses_configured_base_dir(configured_client):
    client, tmp_path = configured_client

    response = client.post(
        "/import",
        data={
            "name": "GUI Import",
            "index": "2",
            "file": (io.BytesIO(b"One\nTwo\n"), "script.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    scripts = list_scripts(base_dir=str(tmp_path))
    assert len(scripts) == 1
    assert scripts[0]["friendlyName"] == "GUI Import"
    data = load_script_json(scripts[0]["guid"], base_dir=str(tmp_path))
    assert data["chapters"] == ["One", "Two"]
    assert data["index"] == 2


def test_import_rejects_invalid_index_before_writing(configured_client):
    client, tmp_path = configured_client

    response = client.post(
        "/import",
        data={
            "name": "Bad Index",
            "index": "not-a-number",
            "file": (io.BytesIO(b"One\n"), "script.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Index must be a whole number." in response.data
    assert list_scripts(base_dir=str(tmp_path)) == []


def test_import_rejects_negative_index_before_writing(configured_client):
    client, tmp_path = configured_client

    response = client.post(
        "/import",
        data={
            "name": "Negative Index",
            "index": "-1",
            "file": (io.BytesIO(b"One\n"), "script.txt"),
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Index must be zero or greater." in response.data
    assert list_scripts(base_dir=str(tmp_path)) == []


def test_rename_uses_configured_base_dir(configured_client):
    client, tmp_path = configured_client
    _make_script(tmp_path, "GUID-ONE", "Old Name", ["line"], index=0)

    response = client.post(
        "/rename/GUID-ONE",
        data={"new_name": "New Name"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert load_script_json("GUID-ONE", base_dir=str(tmp_path))["friendlyName"] == "New Name"


def test_delete_uses_configured_base_dir(configured_client):
    client, tmp_path = configured_client
    _make_script(tmp_path, "GUID-ONE", "Delete Me", ["line"], index=0)

    response = client.post("/delete/GUID-ONE", follow_redirects=True)

    assert response.status_code == 200
    assert list_scripts(base_dir=str(tmp_path)) == []
    assert not (tmp_path / "Texts" / "GUID-ONE.json").exists()


def test_reindex_uses_configured_base_dir(configured_client):
    client, tmp_path = configured_client
    _make_script(tmp_path, "GUID-A", "Alpha", ["a"], index=10)
    _make_script(tmp_path, "GUID-B", "Beta", ["b"], index=3)

    response = client.post("/reindex", follow_redirects=True)

    assert response.status_code == 200
    alpha = load_script_json("GUID-A", base_dir=str(tmp_path))
    beta = load_script_json("GUID-B", base_dir=str(tmp_path))
    assert beta["index"] == 0
    assert alpha["index"] == 1


def test_export_uses_configured_base_dir(configured_client):
    client, tmp_path = configured_client
    _make_script(tmp_path, "GUID-ONE", "Export Me", ["one", "two"], index=0)

    response = client.get("/export/GUID-ONE")

    assert response.status_code == 200
    assert response.data == b"one\ntwo\n"
    assert response.headers["Content-Disposition"].startswith("attachment;")
