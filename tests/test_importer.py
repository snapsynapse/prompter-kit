import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from prompter_kit import (
    LIBRARY_KEY,
    _slugify,
    convert_text_file,
    export_all,
    export_script,
    generate_json_data,
    import_script,
    list_scripts,
    load_script_json,
    save_json_to_texts,
    strip_markdown,
    update_appsettings,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_script(tmp_path, guid, name, chapters, index=0):
    """Write a script JSON directly into tmp_path/Texts/."""
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


# ---------------------------------------------------------------------------
# convert_text_file
# ---------------------------------------------------------------------------

def test_convert_text_file_basic(tmp_path):
    f = tmp_path / "script.txt"
    f.write_text("Line one\nLine two\nLine three\n", encoding="utf-8")
    assert convert_text_file(str(f)) == ["Line one", "Line two", "Line three"]


def test_convert_text_file_strips_whitespace(tmp_path):
    f = tmp_path / "script.txt"
    f.write_text("  hello  \n  world  \n", encoding="utf-8")
    assert convert_text_file(str(f)) == ["hello", "world"]


def test_convert_text_file_skips_blank_lines(tmp_path):
    f = tmp_path / "script.txt"
    f.write_text("a\n\n\nb\n", encoding="utf-8")
    assert convert_text_file(str(f)) == ["a", "b"]


def test_convert_text_file_empty_raises(tmp_path):
    f = tmp_path / "empty.txt"
    f.write_text("   \n\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no text"):
        convert_text_file(str(f))


def test_convert_text_file_missing_raises():
    with pytest.raises(OSError, match="Could not read"):
        convert_text_file("/nonexistent/path/script.txt")


# ---------------------------------------------------------------------------
# generate_json_data
# ---------------------------------------------------------------------------

def test_generate_json_data_structure():
    data = generate_json_data(["chapter 1", "chapter 2"], "GUID-ABC", "My Script", 3)
    assert data == {
        "GUID": "GUID-ABC",
        "chapters": ["chapter 1", "chapter 2"],
        "friendlyName": "My Script",
        "index": 3,
    }


# ---------------------------------------------------------------------------
# save_json_to_texts
# ---------------------------------------------------------------------------

def test_save_json_to_texts_creates_file(tmp_path):
    data = {"GUID": "TEST-GUID", "chapters": ["a"], "friendlyName": "Test", "index": 0}
    path = save_json_to_texts(data, "TEST-GUID", base_dir=str(tmp_path))
    assert os.path.isfile(path)
    saved = json.loads(open(path).read())
    assert saved["GUID"] == "TEST-GUID"
    assert saved["chapters"] == ["a"]


def test_save_json_to_texts_creates_texts_subdir(tmp_path):
    data = {"GUID": "G", "chapters": [], "friendlyName": "n", "index": 0}
    path = save_json_to_texts(data, "G", base_dir=str(tmp_path))
    assert "Texts" in path


# ---------------------------------------------------------------------------
# update_appsettings
# ---------------------------------------------------------------------------

def test_update_appsettings_creates_settings(tmp_path):
    update_appsettings("GUID-1", base_dir=str(tmp_path))
    settings_path = tmp_path / "AppSettings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    assert "GUID-1" in settings[LIBRARY_KEY]


def test_update_appsettings_appends_to_existing(tmp_path):
    settings_path = tmp_path / "AppSettings.json"
    settings_path.write_text(json.dumps({LIBRARY_KEY: ["OLD-GUID"]}))
    update_appsettings("NEW-GUID", base_dir=str(tmp_path))
    settings = json.loads(settings_path.read_text())
    assert "OLD-GUID" in settings[LIBRARY_KEY]
    assert "NEW-GUID" in settings[LIBRARY_KEY]


def test_update_appsettings_no_duplicates(tmp_path):
    update_appsettings("GUID-X", base_dir=str(tmp_path))
    update_appsettings("GUID-X", base_dir=str(tmp_path))
    settings_path = tmp_path / "AppSettings.json"
    settings = json.loads(settings_path.read_text())
    assert settings[LIBRARY_KEY].count("GUID-X") == 1


def test_update_appsettings_invalid_json_raises(tmp_path):
    settings_path = tmp_path / "AppSettings.json"
    settings_path.write_text("not json at all")
    with pytest.raises(ValueError, match="not valid JSON"):
        update_appsettings("G", base_dir=str(tmp_path))


def test_update_appsettings_repairs_non_list_key(tmp_path):
    settings_path = tmp_path / "AppSettings.json"
    settings_path.write_text(json.dumps({LIBRARY_KEY: "wrong-type"}))
    update_appsettings("GUID-Y", base_dir=str(tmp_path))
    settings = json.loads(settings_path.read_text())
    assert isinstance(settings[LIBRARY_KEY], list)
    assert "GUID-Y" in settings[LIBRARY_KEY]


# ---------------------------------------------------------------------------
# import_script (full pipeline + rollback)
# ---------------------------------------------------------------------------

def test_import_script_end_to_end(tmp_path):
    script_file = tmp_path / "script.txt"
    script_file.write_text("Chapter one\nChapter two\n")
    script_path, settings_path = import_script(
        str(script_file), "My Show", 0, base_dir=str(tmp_path)
    )
    assert os.path.isfile(script_path)
    data = json.loads(open(script_path).read())
    assert data["friendlyName"] == "My Show"
    assert data["chapters"] == ["Chapter one", "Chapter two"]
    assert len(data["GUID"]) == 36

    settings = json.loads(open(settings_path).read())
    assert data["GUID"] in settings[LIBRARY_KEY]


def test_import_script_empty_name_raises(tmp_path):
    script_file = tmp_path / "s.txt"
    script_file.write_text("text\n")
    with pytest.raises(ValueError, match="friendly_name"):
        import_script(str(script_file), "", 0, base_dir=str(tmp_path))


def test_import_script_rollback_on_appsettings_failure(tmp_path):
    script_file = tmp_path / "s.txt"
    script_file.write_text("text\n")

    settings_path = tmp_path / "AppSettings.json"
    settings_path.write_text("not json")

    texts_dir = tmp_path / "Texts"
    with pytest.raises(ValueError):
        import_script(str(script_file), "Rollback Test", 0, base_dir=str(tmp_path))

    remaining = list(texts_dir.glob("*.json")) if texts_dir.exists() else []
    assert remaining == [], f"Orphaned files found: {remaining}"


# ---------------------------------------------------------------------------
# list_scripts
# ---------------------------------------------------------------------------

def test_list_scripts_empty_when_no_settings(tmp_path):
    assert list_scripts(base_dir=str(tmp_path)) == []


def test_list_scripts_returns_metadata(tmp_path):
    _make_script(tmp_path, "GUID-A", "Alpha", ["line 1"], index=1)
    _make_script(tmp_path, "GUID-B", "Beta", ["line 2"], index=0)
    _register_guid(tmp_path, "GUID-A")
    _register_guid(tmp_path, "GUID-B")

    scripts = list_scripts(base_dir=str(tmp_path))
    assert len(scripts) == 2
    names = [s["friendlyName"] for s in scripts]
    assert "Alpha" in names
    assert "Beta" in names


def test_list_scripts_sorted_by_index(tmp_path):
    _make_script(tmp_path, "GUID-Z", "Zeta", ["z"], index=2)
    _make_script(tmp_path, "GUID-A", "Alpha", ["a"], index=0)
    _make_script(tmp_path, "GUID-M", "Mu", ["m"], index=1)
    for g in ["GUID-Z", "GUID-A", "GUID-M"]:
        _register_guid(tmp_path, g)

    scripts = list_scripts(base_dir=str(tmp_path))
    assert [s["friendlyName"] for s in scripts] == ["Alpha", "Mu", "Zeta"]


def test_list_scripts_flags_missing_file(tmp_path):
    _register_guid(tmp_path, "GHOST-GUID")
    scripts = list_scripts(base_dir=str(tmp_path))
    assert len(scripts) == 1
    assert scripts[0]["missing"] is True
    assert scripts[0]["guid"] == "GHOST-GUID"


# ---------------------------------------------------------------------------
# load_script_json
# ---------------------------------------------------------------------------

def test_load_script_json_returns_data(tmp_path):
    _make_script(tmp_path, "GUID-1", "Test", ["chapter a", "chapter b"])
    data = load_script_json("GUID-1", base_dir=str(tmp_path))
    assert data["friendlyName"] == "Test"
    assert data["chapters"] == ["chapter a", "chapter b"]


def test_load_script_json_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="No script file"):
        load_script_json("NONEXISTENT", base_dir=str(tmp_path))


def test_load_script_json_corrupt_raises(tmp_path):
    texts_dir = tmp_path / "Texts"
    texts_dir.mkdir()
    (texts_dir / "BAD.json").write_text("not json")
    with pytest.raises(ValueError, match="corrupt"):
        load_script_json("BAD", base_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# export_script
# ---------------------------------------------------------------------------

def test_export_script_writes_chapters(tmp_path):
    _make_script(tmp_path, "GUID-EX", "Export Test", ["First line", "Second line"])
    out = tmp_path / "out.txt"
    export_script("GUID-EX", str(out), base_dir=str(tmp_path))
    content = out.read_text(encoding="utf-8")
    assert content == "First line\nSecond line\n"


def test_export_script_creates_parent_dirs(tmp_path):
    _make_script(tmp_path, "GUID-EX2", "Nested", ["text"])
    out = tmp_path / "subdir" / "nested" / "out.txt"
    export_script("GUID-EX2", str(out), base_dir=str(tmp_path))
    assert out.exists()


def test_export_script_empty_chapters_raises(tmp_path):
    _make_script(tmp_path, "GUID-EMPTY", "Empty", [])
    with pytest.raises(ValueError, match="no chapters"):
        export_script("GUID-EMPTY", str(tmp_path / "out.txt"), base_dir=str(tmp_path))


def test_export_script_missing_guid_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        export_script("NO-SUCH-GUID", str(tmp_path / "out.txt"), base_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# export_all
# ---------------------------------------------------------------------------

def test_export_all_exports_every_script(tmp_path):
    for i, (guid, name) in enumerate([("G1", "Alpha"), ("G2", "Beta"), ("G3", "Gamma")]):
        _make_script(tmp_path, guid, name, [f"chapter {i}"], index=i)
        _register_guid(tmp_path, guid)

    out_dir = tmp_path / "exported"
    exported = export_all(str(out_dir), base_dir=str(tmp_path))
    assert len(exported) == 3
    assert out_dir.exists()
    for _, path in exported:
        assert os.path.isfile(path)


def test_export_all_skips_missing(tmp_path):
    _make_script(tmp_path, "G-OK", "Good", ["line"])
    _register_guid(tmp_path, "G-OK")
    _register_guid(tmp_path, "G-MISSING")  # no JSON file

    out_dir = tmp_path / "exported"
    exported = export_all(str(out_dir), base_dir=str(tmp_path))
    assert len(exported) == 1
    assert exported[0][0] == "G-OK"


def test_export_all_deduplicates_filenames(tmp_path):
    for guid in ["G1", "G2"]:
        _make_script(tmp_path, guid, "Same Name", ["text"])
        _register_guid(tmp_path, guid)

    out_dir = tmp_path / "exported"
    exported = export_all(str(out_dir), base_dir=str(tmp_path))
    paths = [p for _, p in exported]
    assert len(set(paths)) == 2, "Duplicate output paths -- collision not resolved"


def test_export_all_empty_returns_empty(tmp_path):
    assert export_all(str(tmp_path / "out"), base_dir=str(tmp_path)) == []


# ---------------------------------------------------------------------------
# strip_markdown
# ---------------------------------------------------------------------------

def test_strip_markdown_headings():
    assert strip_markdown("# Title") == "Title"
    assert strip_markdown("## Section") == "Section"
    assert strip_markdown("### Sub") == "Sub"


def test_strip_markdown_bold_italic():
    assert strip_markdown("**bold**") == "bold"
    assert strip_markdown("*italic*") == "italic"
    assert strip_markdown("***both***") == "both"
    assert strip_markdown("__bold__") == "bold"
    assert strip_markdown("_italic_") == "italic"


def test_strip_markdown_links():
    assert strip_markdown("[click here](https://example.com)") == "click here"


def test_strip_markdown_images():
    assert strip_markdown("![alt text](image.png)") == "alt text"


def test_strip_markdown_inline_code():
    assert strip_markdown("`code`") == "code"


def test_strip_markdown_list_bullets():
    assert strip_markdown("- item one") == "item one"
    assert strip_markdown("* item two") == "item two"
    assert strip_markdown("+ item three") == "item three"
    assert strip_markdown("1. ordered") == "ordered"


def test_strip_markdown_blockquote():
    assert strip_markdown("> quoted text") == "quoted text"


def test_strip_markdown_strikethrough():
    assert strip_markdown("~~removed~~") == "removed"


def test_strip_markdown_no_markdown():
    assert strip_markdown("Plain sentence.") == "Plain sentence."


def test_strip_markdown_mixed():
    assert strip_markdown("## Welcome to **the show**") == "Welcome to the show"


def test_convert_text_file_strips_markdown(tmp_path):
    f = tmp_path / "script.md"
    f.write_text("# Act One\n**Bold line**\nPlain line\n", encoding="utf-8")
    assert convert_text_file(str(f)) == ["Act One", "Bold line", "Plain line"]


def test_convert_text_file_horizontal_rule_skipped(tmp_path):
    f = tmp_path / "script.md"
    f.write_text("Before\n---\nAfter\n", encoding="utf-8")
    result = convert_text_file(str(f))
    assert "---" not in result
    assert "Before" in result
    assert "After" in result


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert _slugify("My Script") == "My_Script"


def test_slugify_special_chars():
    assert _slugify("Hello: World!") == "Hello_World"


def test_slugify_empty_fallback():
    assert _slugify("!!!") == "script"
