import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import prompter_kit
from prompter_kit import (
    LIBRARY_KEY,
    diagnose_camerahub,
    export_script,
    import_script,
    list_scripts,
    verify_script_absent,
    verify_script_registered,
)


def _script_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompter_kit.py")


def _fixture_path():
    return os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "camerahub",
        "current",
    )


def _make_script(base, guid, name, chapters, index=0):
    texts_dir = base / "Texts"
    texts_dir.mkdir(exist_ok=True)
    data = {"GUID": guid, "friendlyName": name, "chapters": chapters, "index": index}
    (texts_dir / f"{guid}.json").write_text(json.dumps(data), encoding="utf-8")
    settings_path = base / "AppSettings.json"
    settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
    settings.setdefault(LIBRARY_KEY, [])
    if guid not in settings[LIBRARY_KEY]:
        settings[LIBRARY_KEY].append(guid)
    settings_path.write_text(json.dumps(settings), encoding="utf-8")


def test_verify_script_registered_detects_missing_appsettings_entry(tmp_path):
    (tmp_path / "Texts").mkdir()
    (tmp_path / "Texts" / "G1.json").write_text(
        json.dumps({"GUID": "G1", "friendlyName": "Script", "chapters": ["line"], "index": 0}),
        encoding="utf-8",
    )
    (tmp_path / "AppSettings.json").write_text(json.dumps({LIBRARY_KEY: []}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="not registered"):
        verify_script_registered("G1", base_dir=str(tmp_path))


def test_verify_script_absent_detects_leftover_json(tmp_path):
    _make_script(tmp_path, "G1", "Script", ["line"])
    settings = json.loads((tmp_path / "AppSettings.json").read_text(encoding="utf-8"))
    settings[LIBRARY_KEY] = []
    (tmp_path / "AppSettings.json").write_text(json.dumps(settings), encoding="utf-8")

    with pytest.raises(RuntimeError, match="still exists"):
        verify_script_absent("G1", base_dir=str(tmp_path))


def test_diagnose_reports_missing_and_duplicate_names(tmp_path, monkeypatch):
    monkeypatch.setattr(prompter_kit, "camerahub_is_running", lambda: False)
    _make_script(tmp_path, "G1", "Same", ["one"], index=0)
    _make_script(tmp_path, "G2", "Same", ["two"], index=1)
    settings = json.loads((tmp_path / "AppSettings.json").read_text(encoding="utf-8"))
    settings[LIBRARY_KEY].append("GHOST")
    (tmp_path / "AppSettings.json").write_text(json.dumps(settings), encoding="utf-8")

    rows = diagnose_camerahub(str(tmp_path))
    by_check = {row["check"]: row for row in rows}

    assert by_check["Camera Hub process"]["status"] == "OK"
    assert by_check["Missing or corrupt scripts"]["status"] == "WARN"
    assert by_check["Duplicate friendly names"]["status"] == "WARN"


def test_fixture_camera_hub_data_lists_exports_and_preserves_unknown_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(prompter_kit, "camerahub_is_running", lambda: False)
    shutil.copytree(_fixture_path(), tmp_path, dirs_exist_ok=True)

    scripts = list_scripts(base_dir=str(tmp_path))
    assert [script["friendlyName"] for script in scripts] == ["Fixture Beta", "Fixture Alpha"]

    rows = diagnose_camerahub(str(tmp_path))
    by_check = {row["check"]: row for row in rows}
    assert by_check["Data directory"]["status"] == "OK"
    assert by_check["Missing or corrupt scripts"]["status"] == "OK"

    exported = tmp_path / "alpha.txt"
    export_script("FIXTURE-ALPHA", str(exported), base_dir=str(tmp_path))
    assert exported.read_text(encoding="utf-8") == "Alpha line one\nAlpha line two\n"

    prompter_kit.rename_script("FIXTURE-ALPHA", "Fixture Alpha Renamed", base_dir=str(tmp_path))
    data = json.loads((tmp_path / "Texts" / "FIXTURE-ALPHA.json").read_text(encoding="utf-8"))
    assert data["friendlyName"] == "Fixture Alpha Renamed"
    assert data["cameraHubUnknownField"]["scrollSpeed"] == 4


def test_import_export_delete_round_trip_with_base_dir(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("One\nTwo\n", encoding="utf-8")

    script_path, _ = import_script(str(source), "Round Trip", 3, base_dir=str(tmp_path))
    guid = json.loads(open(script_path, encoding="utf-8").read())["GUID"]
    verify_script_registered(
        guid,
        expected_name="Round Trip",
        expected_chapters=["One", "Two"],
        expected_index=3,
        base_dir=str(tmp_path),
    )

    out = tmp_path / "pulled.txt"
    export_script(guid, str(out), base_dir=str(tmp_path))
    assert out.read_text(encoding="utf-8") == "One\nTwo\n"

    prompter_kit.delete_script(guid, base_dir=str(tmp_path))
    assert list_scripts(base_dir=str(tmp_path)) == []


def test_cli_push_pull_aliases_honor_base_dir(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("CLI one\nCLI two\n", encoding="utf-8")

    push = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "push",
            "--base-dir",
            str(tmp_path),
            str(source),
            "--name",
            "CLI Round Trip",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert push.returncode == 0, push.stderr
    assert "Verification:" in push.stdout

    scripts = list_scripts(base_dir=str(tmp_path))
    assert len(scripts) == 1

    pulled = tmp_path / "pulled.txt"
    pull = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "pull",
            "--base-dir",
            str(tmp_path),
            "--guid",
            scripts[0]["guid"],
            "--output",
            str(pulled),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert pull.returncode == 0, pull.stderr
    assert pulled.read_text(encoding="utf-8") == "CLI one\nCLI two\n"


def test_cli_doctor_exits_nonzero_on_missing_base_dir(tmp_path):
    missing = tmp_path / "missing"
    result = subprocess.run(
        [sys.executable, _script_path(), "doctor", "--base-dir", str(missing)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "FAIL" in result.stdout


def test_import_fails_loudly_and_rolls_back_when_appsettings_is_overwritten(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("line\n", encoding="utf-8")
    original_update = prompter_kit.update_appsettings

    def overwritten_update(guid, base_dir=None):
        settings_path = original_update(guid, base_dir)
        settings = json.loads(open(settings_path, encoding="utf-8").read())
        settings[LIBRARY_KEY].remove(guid)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f)
        return settings_path

    monkeypatch.setattr(prompter_kit, "update_appsettings", overwritten_update)

    with pytest.raises(RuntimeError, match="not registered"):
        import_script(str(source), "Overwritten", 0, base_dir=str(tmp_path))
    assert list((tmp_path / "Texts").glob("*.json")) == []


def test_import_rolls_back_when_appsettings_atomic_write_fails(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    source.write_text("line\n", encoding="utf-8")
    original_atomic_write = prompter_kit._atomic_write_json

    def failing_atomic_write(path, data):
        if os.path.basename(path) == "AppSettings.json":
            raise OSError("simulated AppSettings write failure")
        return original_atomic_write(path, data)

    monkeypatch.setattr(prompter_kit, "_atomic_write_json", failing_atomic_write)

    with pytest.raises(OSError, match="Could not write AppSettings"):
        import_script(str(source), "Atomic Failure", 0, base_dir=str(tmp_path))
    assert list((tmp_path / "Texts").glob("*.json")) == []


def test_cli_base_dir_works_for_mutating_commands_and_backup_restore(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("one\ntwo\n", encoding="utf-8")
    restored = tmp_path / "restored"

    push = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "push",
            "--base-dir",
            str(tmp_path),
            str(source),
            "--name",
            "CLI Mutable",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert push.returncode == 0, push.stderr
    guid = list_scripts(base_dir=str(tmp_path))[0]["guid"]

    rename = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "rename",
            "--base-dir",
            str(tmp_path),
            guid,
            "CLI Renamed",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert rename.returncode == 0, rename.stderr

    reindex = subprocess.run(
        [sys.executable, _script_path(), "reindex", "--base-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert reindex.returncode == 0, reindex.stderr

    archive = tmp_path / "backup.zip"
    backup_cmd = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "backup",
            "--base-dir",
            str(tmp_path),
            "--output",
            str(archive),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert backup_cmd.returncode == 0, backup_cmd.stderr

    restore_cmd = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "restore",
            "--base-dir",
            str(restored),
            str(archive),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert restore_cmd.returncode == 0, restore_cmd.stderr
    assert list_scripts(base_dir=str(restored))[0]["friendlyName"] == "CLI Renamed"

    delete = subprocess.run(
        [
            sys.executable,
            _script_path(),
            "delete",
            "--base-dir",
            str(tmp_path),
            guid,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert delete.returncode == 0, delete.stderr
    assert list_scripts(base_dir=str(tmp_path)) == []
