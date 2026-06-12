import json
import os
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prompter_kit import (
    AUTO_BACKUP_DIR,
    AUTO_BACKUP_KEEP,
    LIBRARY_KEY,
    SchemaError,
    auto_backup,
    check_library_schema,
    delete_script,
    edit_script,
    import_script,
    rename_script,
    reindex_scripts,
    restore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_library(tmp_path, scripts):
    """Write a valid library: scripts is a list of (guid, name, chapters, index)."""
    texts_dir = tmp_path / "Texts"
    texts_dir.mkdir(exist_ok=True)
    guids = []
    for guid, name, chapters, index in scripts:
        (texts_dir / f"{guid}.json").write_text(json.dumps({
            "GUID": guid,
            "chapters": chapters,
            "friendlyName": name,
            "index": index,
        }))
        guids.append(guid)
    (tmp_path / "AppSettings.json").write_text(json.dumps({LIBRARY_KEY: guids}))


# ---------------------------------------------------------------------------
# check_library_schema
# ---------------------------------------------------------------------------

def test_schema_ok_on_valid_library(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a", "b"], 0)])
    check_library_schema(base_dir=str(tmp_path))


def test_schema_ok_on_empty_dir(tmp_path):
    check_library_schema(base_dir=str(tmp_path))


def test_schema_ok_when_library_key_absent(tmp_path):
    (tmp_path / "AppSettings.json").write_text(json.dumps({"other.key": 1}))
    check_library_schema(base_dir=str(tmp_path))


def test_schema_rejects_unparseable_appsettings(tmp_path):
    (tmp_path / "AppSettings.json").write_text("not json")
    with pytest.raises(SchemaError):
        check_library_schema(base_dir=str(tmp_path))


def test_schema_rejects_non_list_library(tmp_path):
    (tmp_path / "AppSettings.json").write_text(json.dumps({LIBRARY_KEY: {"G1": 1}}))
    with pytest.raises(SchemaError):
        check_library_schema(base_dir=str(tmp_path))


def test_schema_rejects_non_string_guid(tmp_path):
    (tmp_path / "AppSettings.json").write_text(json.dumps({LIBRARY_KEY: [42]}))
    with pytest.raises(SchemaError):
        check_library_schema(base_dir=str(tmp_path))


def test_schema_rejects_drifted_script_shape(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    # Simulate a Camera Hub format change: chapters become objects.
    (tmp_path / "Texts" / "G1.json").write_text(json.dumps({
        "GUID": "G1",
        "chapters": [{"text": "a", "marker": 0}],
        "friendlyName": "One",
        "index": 0,
    }))
    with pytest.raises(SchemaError):
        check_library_schema(base_dir=str(tmp_path))


def test_schema_tolerates_missing_and_corrupt_script_files(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    settings = json.loads((tmp_path / "AppSettings.json").read_text())
    settings[LIBRARY_KEY].append("G2")  # registered but no file
    (tmp_path / "AppSettings.json").write_text(json.dumps(settings))
    (tmp_path / "Texts" / "G1.json").write_text("not json")  # corrupt, read paths flag it
    check_library_schema(base_dir=str(tmp_path))


def test_write_refused_when_schema_drifted(tmp_path):
    (tmp_path / "AppSettings.json").write_text(json.dumps({LIBRARY_KEY: "drifted"}))
    script_file = tmp_path / "s.txt"
    script_file.write_text("text\n")
    with pytest.raises(SchemaError):
        import_script(str(script_file), "Blocked", 0, base_dir=str(tmp_path))


@pytest.mark.parametrize(
    ("operation", "args"),
    [
        (delete_script, ("DRIFT",)),
        (rename_script, ("DRIFT", "New Name")),
        (reindex_scripts, ()),
        (edit_script, ("DRIFT",)),
    ],
)
def test_mutating_ops_check_schema_before_sorting_drifted_library(tmp_path, operation, args):
    _make_library(tmp_path, [
        ("GOOD", "Good", ["a"], 0),
        ("DRIFT", "Drift", ["b"], 1),
    ])
    (tmp_path / "Texts" / "DRIFT.json").write_text(json.dumps({
        "GUID": "DRIFT",
        "chapters": ["b"],
        "friendlyName": "Drift",
        "index": "1",
    }))

    with pytest.raises(SchemaError):
        operation(*args, base_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# auto_backup
# ---------------------------------------------------------------------------

def test_auto_backup_skipped_on_empty_dir(tmp_path):
    assert auto_backup(base_dir=str(tmp_path)) is None


def test_auto_backup_disabled_by_env(tmp_path, monkeypatch):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    monkeypatch.setenv("PROMPTERKIT_AUTO_BACKUP", "0")
    assert auto_backup(base_dir=str(tmp_path)) is None


def test_auto_backup_writes_snapshot(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    path = auto_backup(base_dir=str(tmp_path))
    assert path is not None and os.path.isfile(path)
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
    assert "AppSettings.json" in names
    assert "Texts/G1.json" in names


def test_auto_backup_rotation(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    backup_dir = tmp_path / AUTO_BACKUP_DIR
    backup_dir.mkdir()
    for i in range(AUTO_BACKUP_KEEP + 5):
        (backup_dir / f"auto_20200101_{i:06d}.zip").write_bytes(b"old")
    auto_backup(base_dir=str(tmp_path))
    remaining = [n for n in os.listdir(backup_dir) if n.startswith("auto_")]
    assert len(remaining) == AUTO_BACKUP_KEEP


def test_write_ops_leave_snapshot_behind(tmp_path):
    _make_library(tmp_path, [("G1", "One", ["a"], 0)])
    rename_script("G1", "Renamed", base_dir=str(tmp_path))
    delete_script("G1", base_dir=str(tmp_path))
    backup_dir = tmp_path / AUTO_BACKUP_DIR
    snapshots = sorted(n for n in os.listdir(backup_dir) if n.startswith("auto_"))
    assert len(snapshots) == 2
    # The first snapshot still holds the pre-rename state.
    with zipfile.ZipFile(backup_dir / snapshots[0]) as zf:
        data = json.loads(zf.read("Texts/G1.json"))
    assert data["friendlyName"] == "One"


def test_restore_proceeds_despite_corrupt_live_library(tmp_path):
    backup_zip = tmp_path / "b.zip"
    with zipfile.ZipFile(backup_zip, "w") as zf:
        zf.writestr("AppSettings.json", json.dumps({LIBRARY_KEY: ["G1"]}))
        zf.writestr("Texts/G1.json", json.dumps({
            "GUID": "G1", "chapters": ["a"], "friendlyName": "One", "index": 0,
        }))
    base = tmp_path / "live"
    base.mkdir()
    (base / "AppSettings.json").write_text("not json")  # corrupt live library
    count = restore(str(backup_zip), base_dir=str(base))
    assert count == 1
    settings = json.loads((base / "AppSettings.json").read_text())
    assert settings[LIBRARY_KEY] == ["G1"]
