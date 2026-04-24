import io
import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import prompter_kit_gui


@pytest.fixture()
def client():
    prompter_kit_gui.app.config.update(TESTING=True)
    with prompter_kit_gui.app.test_client() as client:
        yield client


def test_export_all_uses_unique_names_for_duplicate_friendly_names(client, monkeypatch):
    monkeypatch.setattr(
        prompter_kit_gui,
        "list_scripts",
        lambda: [
            {"guid": "GUID-ONE", "friendlyName": "Same Name", "index": 0, "path": "/tmp/1", "missing": False},
            {"guid": "GUID-TWO", "friendlyName": "Same Name", "index": 1, "path": "/tmp/2", "missing": False},
        ],
    )
    payloads = {
        "GUID-ONE": {"chapters": ["one"]},
        "GUID-TWO": {"chapters": ["two"]},
    }
    monkeypatch.setattr(prompter_kit_gui, "load_script_json", lambda guid: payloads[guid])

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
        lambda: [
            {"guid": "GUID-ONE", "friendlyName": "Alpha", "index": 0, "path": "/tmp/1", "missing": False},
            {"guid": "GUID-TWO", "friendlyName": "Ghost", "index": 1, "path": "/tmp/2", "missing": True},
            {"guid": "GUID-THREE", "friendlyName": "Empty", "index": 2, "path": "/tmp/3", "missing": False},
        ],
    )
    payloads = {
        "GUID-ONE": {"chapters": ["one"]},
        "GUID-THREE": {"chapters": []},
    }
    monkeypatch.setattr(prompter_kit_gui, "load_script_json", lambda guid: payloads[guid])

    response = client.get("/export-all")
    assert response.status_code == 200

    archive = io.BytesIO(response.data)
    with zipfile.ZipFile(archive) as zf:
        assert zf.namelist() == ["Alpha.txt"]
        assert zf.read("Alpha.txt").decode("utf-8") == "one\n"
