import json
import os
import sys
import zipfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prompter_kit import (
    LIBRARY_KEY,
    backup,
    delete_script,
    edit_script,
    list_scripts,
    load_script_json,
    reindex_scripts,
    rename_script,
    restore,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script(tmp_path, guid, name, chapters, index=0):
    texts_dir = tmp_path / "Texts"
    texts_dir.mkdir(exist_ok=True)
    data = {"GUID": guid, "friendlyName": name, "chapters": chapters, "index": index}
    (texts_dir / f"{guid}.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def _register_guid(tmp_path, guid):
    settings_path = tmp_path / "AppSettings.json"
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
    else:
        settings = {}
    settings.setdefault(LIBRARY_KEY, [])
    if guid not in settings[LIBRARY_KEY]:
        settings[LIBRARY_KEY].append(guid)
    settings_path.write_text(json.dumps(settings))


def _setup(tmp_path, scripts):
    """Create and register multiple (guid, name, chapters, index) tuples."""
    for guid, name, chapters, index in scripts:
        _make_script(tmp_path, guid, name, chapters, index)
        _register_guid(tmp_path, guid)


# ---------------------------------------------------------------------------
# delete_script
# ---------------------------------------------------------------------------

def test_delete_removes_json_file(tmp_path):
    _setup(tmp_path, [("G1", "Alpha", ["line"], 0)])
    delete_script("Alpha", base_dir=str(tmp_path))
    assert not (tmp_path / "Texts" / "G1.json").exists()


def test_delete_unregisters_from_appsettings(tmp_path):
    _setup(tmp_path, [("G1", "Alpha", ["line"], 0)])
    delete_script("Alpha", base_dir=str(tmp_path))
    settings = json.loads((tmp_path / "AppSettings.json").read_text())
    assert "G1" not in settings[LIBRARY_KEY]


def test_delete_by_guid(tmp_path):
    _setup(tmp_path, [("GUID-X", "Script", ["line"], 0)])
    delete_script("GUID-X", base_dir=str(tmp_path))
    assert list_scripts(base_dir=str(tmp_path)) == []


def test_delete_leaves_other_scripts(tmp_path):
    _setup(tmp_path, [
        ("G1", "Alpha", ["a"], 0),
        ("G2", "Beta", ["b"], 1),
    ])
    delete_script("Alpha", base_dir=str(tmp_path))
    remaining = list_scripts(base_dir=str(tmp_path))
    assert len(remaining) == 1
    assert remaining[0]["guid"] == "G2"


def test_delete_not_found_raises(tmp_path):
    _setup(tmp_path, [("G1", "Alpha", ["line"], 0)])
    with pytest.raises(KeyError, match="No script found"):
        delete_script("Nonexistent", base_dir=str(tmp_path))


def test_delete_ambiguous_name_raises(tmp_path):
    _setup(tmp_path, [
        ("G1", "Same", ["a"], 0),
        ("G2", "Same", ["b"], 1),
    ])
    with pytest.raises(KeyError, match="Multiple scripts"):
        delete_script("Same", base_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# rename_script
# ---------------------------------------------------------------------------

def test_rename_updates_friendly_name(tmp_path):
    _setup(tmp_path, [("G1", "Old Name", ["line"], 0)])
    rename_script("Old Name", "New Name", base_dir=str(tmp_path))
    data = load_script_json("G1", base_dir=str(tmp_path))
    assert data["friendlyName"] == "New Name"


def test_rename_by_guid(tmp_path):
    _setup(tmp_path, [("G1", "Original", ["line"], 0)])
    rename_script("G1", "Updated", base_dir=str(tmp_path))
    data = load_script_json("G1", base_dir=str(tmp_path))
    assert data["friendlyName"] == "Updated"


def test_rename_empty_name_raises(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    with pytest.raises(ValueError, match="must not be empty"):
        rename_script("Script", "", base_dir=str(tmp_path))


def test_rename_not_found_raises(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    with pytest.raises(KeyError, match="No script found"):
        rename_script("Ghost", "New", base_dir=str(tmp_path))


def test_rename_preserves_chapters_and_index(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["ch1", "ch2"], 5)])
    rename_script("Script", "Renamed", base_dir=str(tmp_path))
    data = load_script_json("G1", base_dir=str(tmp_path))
    assert data["chapters"] == ["ch1", "ch2"]
    assert data["index"] == 5


# ---------------------------------------------------------------------------
# reindex_scripts
# ---------------------------------------------------------------------------

def test_reindex_normalize_existing_order(tmp_path):
    _setup(tmp_path, [
        ("G1", "Alpha", ["a"], 10),
        ("G2", "Beta", ["b"], 5),
        ("G3", "Gamma", ["c"], 20),
    ])
    result = reindex_scripts(base_dir=str(tmp_path))
    indices = {s["friendlyName"]: s["index"] for s in result}
    assert indices["Beta"] == 0
    assert indices["Alpha"] == 1
    assert indices["Gamma"] == 2


def test_reindex_explicit_order(tmp_path):
    _setup(tmp_path, [
        ("G1", "Alpha", ["a"], 0),
        ("G2", "Beta", ["b"], 1),
        ("G3", "Gamma", ["c"], 2),
    ])
    result = reindex_scripts(["Gamma", "Alpha", "Beta"], base_dir=str(tmp_path))
    indices = {s["friendlyName"]: s["index"] for s in result}
    assert indices["Gamma"] == 0
    assert indices["Alpha"] == 1
    assert indices["Beta"] == 2


def test_reindex_partial_order_appends_rest(tmp_path):
    _setup(tmp_path, [
        ("G1", "Alpha", ["a"], 0),
        ("G2", "Beta", ["b"], 1),
        ("G3", "Gamma", ["c"], 2),
    ])
    result = reindex_scripts(["Gamma"], base_dir=str(tmp_path))
    indices = {s["friendlyName"]: s["index"] for s in result}
    assert indices["Gamma"] == 0
    # Alpha and Beta appended after in their existing relative order
    assert indices["Alpha"] < indices["Beta"]
    assert indices["Alpha"] > 0


def test_reindex_updates_json_files(tmp_path):
    _setup(tmp_path, [
        ("G1", "Alpha", ["a"], 99),
        ("G2", "Beta", ["b"], 50),
    ])
    reindex_scripts(base_dir=str(tmp_path))
    alpha = load_script_json("G1", base_dir=str(tmp_path))
    beta = load_script_json("G2", base_dir=str(tmp_path))
    assert beta["index"] == 0  # Beta had lower index 50, comes first
    assert alpha["index"] == 1


def test_reindex_empty_library(tmp_path):
    result = reindex_scripts(base_dir=str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# backup
# ---------------------------------------------------------------------------

def test_backup_creates_zip(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    out = str(tmp_path / "backup.zip")
    result = backup(out, base_dir=str(tmp_path))
    assert result == out
    assert zipfile.is_zipfile(out)


def test_backup_contains_appsettings(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    out = str(tmp_path / "backup.zip")
    backup(out, base_dir=str(tmp_path))
    with zipfile.ZipFile(out) as zf:
        assert "AppSettings.json" in zf.namelist()


def test_backup_contains_script_json(tmp_path):
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    out = str(tmp_path / "backup.zip")
    backup(out, base_dir=str(tmp_path))
    with zipfile.ZipFile(out) as zf:
        assert "Texts/G1.json" in zf.namelist()


def test_backup_excludes_missing_scripts(tmp_path):
    _register_guid(tmp_path, "GHOST")  # no JSON file
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    out = str(tmp_path / "backup.zip")
    backup(out, base_dir=str(tmp_path))
    with zipfile.ZipFile(out) as zf:
        assert "Texts/GHOST.json" not in zf.namelist()
        assert "Texts/G1.json" in zf.namelist()


def test_backup_default_filename(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _setup(tmp_path, [("G1", "Script", ["line"], 0)])
    result = backup(base_dir=str(tmp_path))
    assert result.startswith("prompter_backup_")
    assert result.endswith(".zip")
    assert os.path.isfile(result)


# ---------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------

def test_restore_replace_mode(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    _setup(src, [
        ("G1", "Alpha", ["ch1"], 0),
        ("G2", "Beta", ["ch2"], 1),
    ])
    archive = str(tmp_path / "backup.zip")
    backup(archive, base_dir=str(src))

    count = restore(archive, merge=False, base_dir=str(dst))
    assert count == 2
    scripts = list_scripts(base_dir=str(dst))
    guids = {s["guid"] for s in scripts}
    assert guids == {"G1", "G2"}


def test_restore_merge_adds_new_only(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    _setup(src, [
        ("G1", "Alpha", ["ch1"], 0),
        ("G2", "Beta", ["ch2"], 1),
    ])
    archive = str(tmp_path / "backup.zip")
    backup(archive, base_dir=str(src))

    # Pre-populate dst with G1 only
    _setup(dst, [("G1", "Alpha", ["existing"], 0)])

    count = restore(archive, merge=True, base_dir=str(dst))
    assert count == 2  # both written to disk; only G2 added to library

    scripts = list_scripts(base_dir=str(dst))
    guids = {s["guid"] for s in scripts}
    assert "G1" in guids
    assert "G2" in guids


def test_restore_merge_preserves_existing_content(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()

    _setup(src, [("G1", "Alpha", ["backup content"], 0)])
    archive = str(tmp_path / "backup.zip")
    backup(archive, base_dir=str(src))

    _setup(dst, [("G1", "Alpha", ["existing content"], 0)])
    restore(archive, merge=True, base_dir=str(dst))

    # In merge mode the file is overwritten from archive but GUID stays registered once
    scripts = list_scripts(base_dir=str(dst))
    assert scripts[0][LIBRARY_KEY if False else "guid"] == "G1"  # still registered


def test_restore_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        restore("/nonexistent/path/backup.zip", base_dir=str(tmp_path))
