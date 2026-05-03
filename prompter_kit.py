import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile


LIBRARY_KEY = "applogic.prompter.libraryList"


# ---------------------------------------------------------------------------
# Platform path
# ---------------------------------------------------------------------------

def get_camerahub_path() -> str:
    """Return the platform-appropriate CameraHub data directory."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            raise EnvironmentError("APPDATA environment variable is not set")
        return os.path.join(appdata, "Elgato", "CameraHub")
    elif sys.platform == "darwin":
        home = os.path.expanduser("~")
        return os.path.join(home, "Library", "Application Support", "Elgato", "CameraHub")
    else:
        raise EnvironmentError(f"Unsupported platform: {sys.platform}")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _atomic_write_json(path: str, data: dict) -> None:
    """Write JSON to a temp file then rename -- avoids corruption on interrupted write."""
    dir_ = os.path.dirname(path)
    os.makedirs(dir_, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _load_appsettings(base_dir: str) -> dict:
    settings_path = os.path.join(base_dir, "AppSettings.json")
    if not os.path.exists(settings_path):
        return {}
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"AppSettings.json is not valid JSON: {e}") from e
    except OSError as e:
        raise OSError(f"Could not read AppSettings.json: {e}") from e


def _slugify(name: str) -> str:
    """Convert a friendly name to a safe filename stem."""
    slug = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[\s]+", "_", slug) or "script"


_SAFE_GUID_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _validate_backup_guid(guid: str) -> str:
    """Validate a GUID read from backup metadata before using it as a filename."""
    if not isinstance(guid, str) or not guid or not _SAFE_GUID_RE.fullmatch(guid):
        raise ValueError(f"Backup contains invalid script GUID: {guid!r}")
    return guid


def _unique_text_filename(name: str, guid: str, used_names: set[str] | None = None) -> str:
    """Return a collision-safe export filename for a script."""
    slug = _slugify(name) or guid
    filename = f"{slug}.txt"
    if used_names is not None:
        if filename in used_names:
            filename = f"{slug}_{guid[:8]}.txt"
        used_names.add(filename)
    return filename


def _resolve_script(name_or_guid: str, base_dir: str | None = None) -> dict:
    """Find a registered script by exact GUID or case-insensitive friendly name."""
    scripts = list_scripts(base_dir)
    for s in scripts:
        if s["guid"] == name_or_guid:
            return s
    matches = [s for s in scripts if s["friendlyName"].lower() == name_or_guid.lower()]
    if not matches:
        raise KeyError(f"No script found matching '{name_or_guid}'")
    if len(matches) > 1:
        guids = ", ".join(s["guid"] for s in matches)
        raise KeyError(f"Multiple scripts named '{name_or_guid}': {guids}. Use GUID to disambiguate.")
    return matches[0]


def _resolve_base_dir(base_dir: str | None = None) -> str:
    return base_dir if base_dir is not None else get_camerahub_path()


def _script_json_path(guid_str: str, base_dir: str) -> str:
    return os.path.join(base_dir, "Texts", f"{guid_str}.json")


def verify_script_registered(
    guid_str: str,
    expected_name: str | None = None,
    expected_chapters: list[str] | None = None,
    expected_index: int | None = None,
    base_dir: str | None = None,
) -> None:
    """Raise if a script write is not visible in AppSettings.json and Texts."""
    base_dir = _resolve_base_dir(base_dir)
    settings = _load_appsettings(base_dir)
    guids = settings.get(LIBRARY_KEY, [])
    if not isinstance(guids, list):
        raise RuntimeError(f"AppSettings.json key '{LIBRARY_KEY}' is not a list")
    if guid_str not in guids:
        raise RuntimeError(f"Verification failed: '{guid_str}' is not registered in AppSettings.json")

    data = load_script_json(guid_str, base_dir)
    if data.get("GUID") not in ("", None, guid_str):
        raise RuntimeError(f"Verification failed: '{guid_str}' has mismatched GUID metadata")
    if expected_name is not None and data.get("friendlyName") != expected_name:
        raise RuntimeError(
            f"Verification failed: '{guid_str}' name is {data.get('friendlyName')!r}, expected {expected_name!r}"
        )
    if expected_chapters is not None and data.get("chapters") != expected_chapters:
        raise RuntimeError(f"Verification failed: '{guid_str}' chapters do not match the expected content")
    if expected_index is not None and data.get("index") != expected_index:
        raise RuntimeError(
            f"Verification failed: '{guid_str}' index is {data.get('index')!r}, expected {expected_index!r}"
        )


def verify_script_absent(guid_str: str, base_dir: str | None = None) -> None:
    """Raise if a script still appears registered or present on disk."""
    base_dir = _resolve_base_dir(base_dir)
    settings = _load_appsettings(base_dir)
    guids = settings.get(LIBRARY_KEY, [])
    if isinstance(guids, list) and guid_str in guids:
        raise RuntimeError(f"Verification failed: '{guid_str}' is still registered in AppSettings.json")
    path = _script_json_path(guid_str, base_dir)
    if os.path.exists(path):
        raise RuntimeError(f"Verification failed: '{guid_str}' still exists at '{path}'")


# ---------------------------------------------------------------------------
# Markdown stripping
# ---------------------------------------------------------------------------

_MD_STRIP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),   # images -> alt text
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),    # links -> label
    (re.compile(r"~~(.+?)~~"), r"\1"),                 # strikethrough
    (re.compile(r"\*{3}(.+?)\*{3}"), r"\1"),           # bold+italic ***
    (re.compile(r"\*{2}(.+?)\*{2}"), r"\1"),           # bold **
    (re.compile(r"_{3}(.+?)_{3}"), r"\1"),             # bold+italic ___
    (re.compile(r"_{2}(.+?)_{2}"), r"\1"),             # bold __
    (re.compile(r"`(.+?)`"), r"\1"),                   # inline code
    (re.compile(r"^#{1,6}\s+"), ""),                   # headings
    (re.compile(r"^[-*+]\s+"), ""),                    # unordered list bullets
    (re.compile(r"^\d+\.\s+"), ""),                    # ordered list items
    (re.compile(r"^>\s*"), ""),                        # blockquotes
    (re.compile(r"^[-*_]{3,}\s*$"), ""),               # horizontal rules
    (re.compile(r"[*_#]"), ""),                        # remaining markers
]


def strip_markdown(text: str) -> str:
    """Strip markdown formatting, preserving plain text content."""
    for pattern, repl in _MD_STRIP:
        text = pattern.sub(repl, text)
    return text.strip()


# ---------------------------------------------------------------------------
# Import pipeline
# ---------------------------------------------------------------------------

def convert_text_file(file_path: str) -> list[str]:
    """Read a plain text or Markdown file; return non-empty lines as chapters."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    except OSError as e:
        raise OSError(f"Could not read '{file_path}': {e}") from e

    chapters = [stripped for line in raw_lines if (stripped := strip_markdown(line))]

    if not chapters:
        raise ValueError(f"'{file_path}' contains no text after stripping whitespace")

    return chapters


def generate_json_data(chapters: list[str], guid_str: str, friendly_name: str, index: int) -> dict:
    return {
        "GUID": guid_str,
        "chapters": chapters,
        "friendlyName": friendly_name,
        "index": index,
    }


def save_json_to_texts(data: dict, guid_str: str, base_dir: str | None = None) -> str:
    """Write the script JSON to the Texts directory. Returns the saved path."""
    base_dir = _resolve_base_dir(base_dir)
    dest = os.path.join(base_dir, "Texts", f"{guid_str}.json")
    try:
        _atomic_write_json(dest, data)
    except OSError as e:
        raise OSError(f"Could not write script JSON to '{dest}': {e}") from e
    return dest


def update_appsettings(guid_str: str, base_dir: str | None = None) -> str:
    """Register guid_str in AppSettings.json libraryList. Returns the settings path."""
    base_dir = _resolve_base_dir(base_dir)
    settings_path = os.path.join(base_dir, "AppSettings.json")

    settings = _load_appsettings(base_dir)

    if not isinstance(settings.get(LIBRARY_KEY), list):
        settings[LIBRARY_KEY] = []

    if guid_str not in settings[LIBRARY_KEY]:
        settings[LIBRARY_KEY].append(guid_str)

    try:
        _atomic_write_json(settings_path, settings)
    except OSError as e:
        raise OSError(f"Could not write AppSettings.json: {e}") from e

    return settings_path


def import_script(text_file: str, friendly_name: str, index: int, base_dir: str | None = None) -> tuple[str, str]:
    """
    Full import pipeline. Returns (script_path, settings_path).
    Rolls back the Texts JSON if the AppSettings update fails.
    """
    if not friendly_name:
        raise ValueError("friendly_name must not be empty")

    base_dir = _resolve_base_dir(base_dir)
    chapters = convert_text_file(text_file)
    guid_str = str(uuid.uuid4()).upper()
    json_data = generate_json_data(chapters, guid_str, friendly_name, index)

    script_path = save_json_to_texts(json_data, guid_str, base_dir)

    try:
        settings_path = update_appsettings(guid_str, base_dir)
        verify_script_registered(
            guid_str,
            expected_name=friendly_name,
            expected_chapters=chapters,
            expected_index=index,
            base_dir=base_dir,
        )
    except Exception:
        try:
            os.unlink(script_path)
        except OSError:
            pass
        raise

    return script_path, settings_path


# ---------------------------------------------------------------------------
# Export pipeline
# ---------------------------------------------------------------------------

def list_scripts(base_dir: str | None = None) -> list[dict]:
    """
    Return metadata for every registered script.
    Each entry: {"guid": str, "friendlyName": str, "index": int, "path": str}
    Scripts missing their JSON file are included with a "missing": True flag.
    """
    base_dir = _resolve_base_dir(base_dir)

    settings = _load_appsettings(base_dir)
    guids = settings.get(LIBRARY_KEY, [])
    if not isinstance(guids, list):
        guids = []

    results = []
    for guid in guids:
        json_path = os.path.join(base_dir, "Texts", f"{guid}.json")
        if not os.path.exists(json_path):
            results.append({"guid": guid, "friendlyName": "", "index": -1, "path": json_path, "missing": True})
            continue
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            results.append({
                "guid": guid,
                "friendlyName": data.get("friendlyName", ""),
                "index": data.get("index", -1),
                "path": json_path,
                "missing": False,
            })
        except (json.JSONDecodeError, OSError):
            results.append({"guid": guid, "friendlyName": "", "index": -1, "path": json_path, "missing": True})

    results.sort(key=lambda r: (r["index"], r["friendlyName"]))
    return results


def load_script_json(guid_str: str, base_dir: str | None = None) -> dict:
    """Load and return the raw JSON dict for a script GUID."""
    base_dir = _resolve_base_dir(base_dir)
    path = _script_json_path(guid_str, base_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No script file found for GUID '{guid_str}' at '{path}'")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Script JSON for '{guid_str}' is corrupt: {e}") from e
    except OSError as e:
        raise OSError(f"Could not read '{path}': {e}") from e


def export_script(guid_str: str, output_path: str, base_dir: str | None = None) -> str:
    """
    Export a single script to a plain-text file (one chapter per line).
    Returns the output path written.
    """
    data = load_script_json(guid_str, base_dir)
    chapters = data.get("chapters", [])
    if not chapters:
        raise ValueError(f"Script '{guid_str}' has no chapters to export")

    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(chapters) + "\n")
    except OSError as e:
        raise OSError(f"Could not write to '{output_path}': {e}") from e

    return output_path


def export_all(output_dir: str, base_dir: str | None = None) -> list[tuple[str, str]]:
    """
    Export every registered script to output_dir as <slug>.txt files.
    Returns list of (guid, output_path) for each successfully exported script.
    Skips missing/corrupt scripts with a warning rather than aborting.
    """
    scripts = list_scripts(base_dir)
    if not scripts:
        return []

    os.makedirs(output_dir, exist_ok=True)
    exported = []
    used_names: set[str] = set()

    for script in scripts:
        if script["missing"]:
            print(f"Warning: skipping '{script['guid']}' (file missing or corrupt)", file=sys.stderr)
            continue

        output_name = _unique_text_filename(script["friendlyName"], script["guid"], used_names)
        output_path = os.path.join(output_dir, output_name)

        try:
            export_script(script["guid"], output_path, base_dir)
            exported.append((script["guid"], output_path))
        except Exception as e:
            print(f"Warning: could not export '{script['guid']}': {e}", file=sys.stderr)

    return exported


# ---------------------------------------------------------------------------
# Delete pipeline
# ---------------------------------------------------------------------------

def delete_script(name_or_guid: str, base_dir: str | None = None) -> str:
    """
    Remove a script by name or GUID. Deletes the Texts JSON and unregisters from
    AppSettings.json. Returns the GUID that was deleted.
    """
    base_dir = _resolve_base_dir(base_dir)

    script = _resolve_script(name_or_guid, base_dir)
    guid = script["guid"]

    settings_path = os.path.join(base_dir, "AppSettings.json")
    settings = _load_appsettings(base_dir)
    lib = settings.get(LIBRARY_KEY, [])
    if isinstance(lib, list) and guid in lib:
        lib.remove(guid)
        settings[LIBRARY_KEY] = lib
        _atomic_write_json(settings_path, settings)

    json_path = os.path.join(base_dir, "Texts", f"{guid}.json")
    if os.path.exists(json_path):
        try:
            os.unlink(json_path)
        except OSError as e:
            raise OSError(f"Could not delete '{json_path}': {e}") from e

    verify_script_absent(guid, base_dir)
    return guid


# ---------------------------------------------------------------------------
# Rename pipeline
# ---------------------------------------------------------------------------

def rename_script(name_or_guid: str, new_name: str, base_dir: str | None = None) -> str:
    """
    Update the friendlyName of an existing script. Returns the GUID.
    """
    if not new_name or not new_name.strip():
        raise ValueError("new_name must not be empty")
    base_dir = _resolve_base_dir(base_dir)

    script = _resolve_script(name_or_guid, base_dir)
    guid = script["guid"]

    data = load_script_json(guid, base_dir)
    data["friendlyName"] = new_name.strip()
    json_path = os.path.join(base_dir, "Texts", f"{guid}.json")
    _atomic_write_json(json_path, data)

    verify_script_registered(
        guid,
        expected_name=new_name.strip(),
        expected_chapters=data.get("chapters"),
        expected_index=data.get("index"),
        base_dir=base_dir,
    )
    return guid


# ---------------------------------------------------------------------------
# Reindex pipeline
# ---------------------------------------------------------------------------

def reindex_scripts(ordered_names_or_guids: list[str] | None = None, base_dir: str | None = None) -> list[dict]:
    """
    Assign new 0-based index values across the script library.

    If ordered_names_or_guids is provided, those scripts are placed first (in that order)
    with indices 0, 1, 2 ... Any scripts not listed retain their relative order and are
    appended after with the next available indices.

    If ordered_names_or_guids is None or empty, the current sort order (by index, then name)
    is normalized to 0, 1, 2 ...

    Returns the updated list of script metadata dicts (same shape as list_scripts).
    """
    base_dir = _resolve_base_dir(base_dir)

    scripts = list_scripts(base_dir)
    if not scripts:
        return []

    if ordered_names_or_guids:
        # Resolve the explicitly ordered scripts first
        resolved_guids: list[str] = []
        for spec in ordered_names_or_guids:
            s = _resolve_script(spec, base_dir)
            if s["guid"] not in resolved_guids:
                resolved_guids.append(s["guid"])

        ordered = [s for s in scripts if s["guid"] in resolved_guids]
        ordered.sort(key=lambda s: resolved_guids.index(s["guid"]))
        remainder = [s for s in scripts if s["guid"] not in resolved_guids]
        final_order = ordered + remainder
    else:
        final_order = scripts  # already sorted by (index, name)

    for new_index, script in enumerate(final_order):
        if script["missing"]:
            continue
        data = load_script_json(script["guid"], base_dir)
        if data.get("index") != new_index:
            data["index"] = new_index
            json_path = os.path.join(base_dir, "Texts", f"{script['guid']}.json")
            _atomic_write_json(json_path, data)
        verify_script_registered(
            script["guid"],
            expected_name=data.get("friendlyName"),
            expected_chapters=data.get("chapters"),
            expected_index=new_index,
            base_dir=base_dir,
        )

    return list_scripts(base_dir)


# ---------------------------------------------------------------------------
# Edit pipeline
# ---------------------------------------------------------------------------

def edit_script(name_or_guid: str, base_dir: str | None = None) -> str:
    """
    Open a script's chapters in $EDITOR (one chapter per line).
    Saves the updated chapters back to the script JSON on exit.
    Returns the GUID edited.
    """
    base_dir = _resolve_base_dir(base_dir)

    script = _resolve_script(name_or_guid, base_dir)
    guid = script["guid"]
    data = load_script_json(guid, base_dir)
    chapters = data.get("chapters", [])

    if sys.platform == "win32":
        default_editor = "notepad"
    else:
        default_editor = "vi"
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or default_editor

    fd, tmp_path = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join(chapters) + ("\n" if chapters else ""))

        result = subprocess.run([editor, tmp_path])
        if result.returncode != 0:
            raise RuntimeError(f"Editor exited with code {result.returncode}")

        with open(tmp_path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    new_chapters = [line.rstrip("\n\r") for line in raw_lines if line.strip()]
    if not new_chapters:
        raise ValueError("Editor produced no content; script not updated")

    data["chapters"] = new_chapters
    json_path = os.path.join(base_dir, "Texts", f"{guid}.json")
    _atomic_write_json(json_path, data)

    verify_script_registered(
        guid,
        expected_name=data.get("friendlyName"),
        expected_chapters=new_chapters,
        expected_index=data.get("index"),
        base_dir=base_dir,
    )
    return guid


# ---------------------------------------------------------------------------
# Backup / restore pipeline
# ---------------------------------------------------------------------------

def backup(output_path: str | None = None, base_dir: str | None = None) -> str:
    """
    Archive all registered scripts and AppSettings.json to a zip file.
    If output_path is None, writes to the current directory with a timestamped name.
    Returns the path of the created archive.
    """
    base_dir = _resolve_base_dir(base_dir)

    if output_path is None:
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"prompter_backup_{stamp}.zip"

    scripts = list_scripts(base_dir)
    settings_path = os.path.join(base_dir, "AppSettings.json")

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(settings_path):
            zf.write(settings_path, "AppSettings.json")

        for script in scripts:
            if script["missing"]:
                continue
            arc_name = os.path.join("Texts", f"{script['guid']}.json")
            zf.write(script["path"], arc_name)

    return output_path


def restore(backup_path: str, merge: bool = False, base_dir: str | None = None) -> int:
    """
    Restore scripts from a backup zip.

    merge=False (default): replace AppSettings.json and all Texts JSON files from the archive.
    merge=True: add scripts from the archive that are not already registered, leaving
                existing scripts untouched.

    Returns the count of scripts written.
    """
    base_dir = _resolve_base_dir(base_dir)

    if not os.path.isfile(backup_path):
        raise FileNotFoundError(f"Backup file not found: '{backup_path}'")

    texts_dir = os.path.join(base_dir, "Texts")
    os.makedirs(texts_dir, exist_ok=True)
    settings_path = os.path.join(base_dir, "AppSettings.json")

    with zipfile.ZipFile(backup_path, "r") as zf:
        names = zf.namelist()
        if "AppSettings.json" not in names:
            raise ValueError("Backup is missing AppSettings.json")
        if len(names) != len(set(names)):
            raise ValueError("Backup contains duplicate archive paths")

        try:
            backup_settings = json.loads(zf.read("AppSettings.json"))
        except json.JSONDecodeError as e:
            raise ValueError(f"Backup AppSettings.json is not valid JSON: {e}") from e

        backup_guids = backup_settings.get(LIBRARY_KEY, [])
        if not isinstance(backup_guids, list):
            raise ValueError(f"Backup AppSettings.json key '{LIBRARY_KEY}' must be a list")

        validated_guids: list[str] = []
        seen_guids: set[str] = set()
        for guid in backup_guids:
            safe_guid = _validate_backup_guid(guid)
            if safe_guid not in seen_guids:
                validated_guids.append(safe_guid)
                seen_guids.add(safe_guid)

        expected_entries = {"AppSettings.json"} | {f"Texts/{guid}.json" for guid in validated_guids}
        unexpected_entries = [name for name in names if name not in expected_entries]
        if unexpected_entries:
            raise ValueError(f"Backup contains unexpected paths: {', '.join(sorted(unexpected_entries))}")

        backup_scripts: dict[str, dict] = {}
        for guid in validated_guids:
            arc_name = f"Texts/{guid}.json"
            if arc_name not in names:
                continue
            try:
                script_data = json.loads(zf.read(arc_name))
            except json.JSONDecodeError as e:
                raise ValueError(f"Backup script '{guid}' is not valid JSON: {e}") from e
            if not isinstance(script_data, dict):
                raise ValueError(f"Backup script '{guid}' must be a JSON object")
            if script_data.get("GUID") not in ("", None, guid):
                raise ValueError(f"Backup script '{guid}' has mismatched GUID metadata")
            script_data["GUID"] = guid
            backup_scripts[guid] = script_data

    if merge:
        current_settings = _load_appsettings(base_dir)
        current_guids = current_settings.get(LIBRARY_KEY, [])
        if not isinstance(current_guids, list):
            current_guids = []

        written = 0
        written_guids: list[str] = []
        for guid in validated_guids:
            if guid in current_guids:
                continue
            if guid not in backup_scripts:
                continue
            dest = os.path.join(texts_dir, f"{guid}.json")
            _atomic_write_json(dest, backup_scripts[guid])
            current_guids.append(guid)
            written_guids.append(guid)
            written += 1

        current_settings[LIBRARY_KEY] = current_guids
        _atomic_write_json(settings_path, current_settings)
        for guid in written_guids:
            if guid in backup_scripts:
                verify_script_registered(
                    guid,
                    expected_name=backup_scripts[guid].get("friendlyName"),
                    expected_chapters=backup_scripts[guid].get("chapters"),
                    expected_index=backup_scripts[guid].get("index"),
                    base_dir=base_dir,
                )
        return written

    written = 0
    for name in os.listdir(texts_dir):
        if name.endswith(".json"):
            os.unlink(os.path.join(texts_dir, name))

    for guid in validated_guids:
        if guid not in backup_scripts:
            continue
        dest = os.path.join(texts_dir, f"{guid}.json")
        _atomic_write_json(dest, backup_scripts[guid])
        written += 1

    backup_settings[LIBRARY_KEY] = validated_guids
    _atomic_write_json(settings_path, backup_settings)
    for guid in validated_guids:
        if guid in backup_scripts:
            verify_script_registered(
                guid,
                expected_name=backup_scripts[guid].get("friendlyName"),
                expected_chapters=backup_scripts[guid].get("chapters"),
                expected_index=backup_scripts[guid].get("index"),
                base_dir=base_dir,
            )
    return written


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def _mtime(path: str) -> str:
    if not os.path.exists(path):
        return "missing"
    return datetime.datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds")


def camerahub_is_running() -> bool | None:
    """Return Camera Hub process status, or None when the platform cannot tell."""
    if sys.platform == "darwin":
        result = subprocess.run(
            ["osascript", "-e", f'application "{_CAMERAHUB_APP_NAME}" is running'],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip().lower() == "true"
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {_CAMERAHUB_WIN_EXE}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return _CAMERAHUB_WIN_EXE.lower() in result.stdout.lower()
    return None


def diagnose_camerahub(base_dir: str | None = None) -> list[dict]:
    """Return pass/warn/fail diagnostic rows for the Camera Hub data directory."""
    base_dir = _resolve_base_dir(base_dir)
    settings_path = os.path.join(base_dir, "AppSettings.json")
    texts_dir = os.path.join(base_dir, "Texts")
    rows: list[dict] = []

    def add(status: str, check: str, detail: str) -> None:
        rows.append({"status": status, "check": check, "detail": detail})

    add("OK" if os.path.isdir(base_dir) else "FAIL", "Data directory", base_dir)
    add("OK" if os.path.isfile(settings_path) else "WARN", "AppSettings.json", settings_path)
    add("OK" if os.path.isdir(texts_dir) else "WARN", "Texts directory", texts_dir)
    add("INFO", "AppSettings modified", _mtime(settings_path))

    running = camerahub_is_running()
    if running is True:
        add("WARN", "Camera Hub process", "running; direct writes may be ignored or overwritten")
    elif running is False:
        add("OK", "Camera Hub process", "not running")
    else:
        add("INFO", "Camera Hub process", "unknown on this platform")

    try:
        settings = _load_appsettings(base_dir)
    except Exception as e:
        add("FAIL", "AppSettings parse", str(e))
        return rows

    guids = settings.get(LIBRARY_KEY, [])
    if not isinstance(guids, list):
        add("FAIL", "Library list", f"'{LIBRARY_KEY}' is {type(guids).__name__}, expected list")
        guids = []
    else:
        add("OK", "Library list", f"{len(guids)} registered script(s)")

    scripts = list_scripts(base_dir)
    missing = [s for s in scripts if s["missing"]]
    add("OK" if not missing else "WARN", "Missing or corrupt scripts", f"{len(missing)} issue(s)")

    names: dict[str, int] = {}
    for script in scripts:
        name = script["friendlyName"].lower()
        if name:
            names[name] = names.get(name, 0) + 1
    duplicates = [name for name, count in names.items() if count > 1]
    add("OK" if not duplicates else "WARN", "Duplicate friendly names", ", ".join(duplicates) or "none")

    if os.path.isdir(texts_dir):
        json_files = [name for name in os.listdir(texts_dir) if name.endswith(".json")]
        orphaned = [
            name for name in json_files
            if os.path.splitext(name)[0] not in set(guids)
        ]
        add("INFO", "Texts JSON files", f"{len(json_files)} file(s)")
        add("OK" if not orphaned else "WARN", "Unregistered JSON files", f"{len(orphaned)} file(s)")
        latest = "none"
        if json_files:
            latest_path = max((os.path.join(texts_dir, name) for name in json_files), key=os.path.getmtime)
            latest = f"{os.path.basename(latest_path)} modified {_mtime(latest_path)}"
        add("INFO", "Latest script file", latest)

    return rows


# ---------------------------------------------------------------------------
# Camera Hub lifecycle
# ---------------------------------------------------------------------------

_CAMERAHUB_APP_NAME = "Camera Hub"
_CAMERAHUB_WIN_EXE = "CameraHub.exe"


def camerahub_stop(wait: bool = False, timeout: float = 10.0) -> None:
    """Quit Camera Hub gracefully."""
    if sys.platform == "darwin":
        subprocess.run(
            ["osascript", "-e", f'tell application "{_CAMERAHUB_APP_NAME}" to quit'],
            check=False,
        )
    elif sys.platform == "win32":
        subprocess.run(["taskkill", "/IM", _CAMERAHUB_WIN_EXE, "/F"], check=False)
    else:
        raise EnvironmentError(f"camerahub stop not supported on {sys.platform}")

    if wait:
        deadline = time.time() + timeout
        while time.time() < deadline:
            running = camerahub_is_running()
            if running is False:
                return
            if running is None:
                return
            time.sleep(0.2)
        raise TimeoutError(f"Camera Hub did not stop within {timeout:g} seconds")


def camerahub_start() -> None:
    """Launch Camera Hub."""
    if sys.platform == "darwin":
        subprocess.run(["open", "-a", _CAMERAHUB_APP_NAME], check=True)
    elif sys.platform == "win32":
        subprocess.run(["start", "", _CAMERAHUB_WIN_EXE], shell=True, check=True)
    else:
        raise EnvironmentError(f"camerahub start not supported on {sys.platform}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_import(args: argparse.Namespace) -> None:
    if not os.path.isfile(args.text_file):
        print(f"Error: '{args.text_file}' does not exist or is not a file.", file=sys.stderr)
        sys.exit(1)
    if not args.name.strip():
        print("Error: --name must not be empty.", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "restart", False):
        print("Stopping Camera Hub...")
        camerahub_stop(wait=True)

    try:
        script_path, settings_path = import_script(
            args.text_file,
            args.name.strip(),
            args.index,
            base_dir=args.base_dir,
        )
        print(f"Script saved:  {script_path}")
        print(f"AppSettings:   {settings_path}")
        print("Verification:  passed")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "restart", False):
        print("Starting Camera Hub...")
        camerahub_start()


def _cmd_export(args: argparse.Namespace) -> None:
    base_dir = args.base_dir

    if args.list:
        try:
            scripts = list_scripts(base_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        if not scripts:
            print("No scripts registered.")
            return
        print(f"{'#':<4} {'Name':<40} {'GUID':<38} {'File'}")
        print("-" * 110)
        for i, s in enumerate(scripts):
            flag = " [MISSING]" if s["missing"] else ""
            print(f"{i:<4} {s['friendlyName']:<40} {s['guid']:<38} {s['path']}{flag}")
        return

    if args.all:
        output_dir = args.output or "."
        try:
            exported = export_all(output_dir, base_dir)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        for guid, path in exported:
            print(f"Exported: {path}  ({guid})")
        print(f"{len(exported)} script(s) exported to '{output_dir}'")
        return

    # Single export: resolve GUID
    guid = args.guid
    if not guid:
        if args.name:
            try:
                scripts = list_scripts(base_dir)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)
            matches = [s for s in scripts if s["friendlyName"].lower() == args.name.lower()]
            if not matches:
                print(f"Error: no script named '{args.name}'.", file=sys.stderr)
                sys.exit(1)
            if len(matches) > 1:
                print(f"Error: multiple scripts named '{args.name}'. Use --guid to disambiguate.", file=sys.stderr)
                for m in matches:
                    print(f"  {m['guid']}", file=sys.stderr)
                sys.exit(1)
            guid = matches[0]["guid"]
        else:
            print("Error: provide --guid, --name, --list, or --all.", file=sys.stderr)
            sys.exit(1)

    if not args.output:
        print("Error: --output is required for single-script export.", file=sys.stderr)
        sys.exit(1)

    try:
        out = export_script(guid, args.output, base_dir)
        print(f"Exported: {out}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_delete(args: argparse.Namespace) -> None:
    try:
        guid = delete_script(args.name_or_guid, base_dir=args.base_dir)
        print(f"Deleted: {guid}")
        print("Verification: passed")
    except (KeyError, OSError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_rename(args: argparse.Namespace) -> None:
    try:
        guid = rename_script(args.name_or_guid, args.new_name, base_dir=args.base_dir)
        print(f"Renamed: {guid}  ->  {args.new_name}")
        print("Verification: passed")
    except (KeyError, ValueError, OSError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_reindex(args: argparse.Namespace) -> None:
    specs = args.name_or_guid or None
    try:
        updated = reindex_scripts(specs, base_dir=args.base_dir)
    except (KeyError, OSError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"{'Index':<6} {'Name':<40} {'GUID'}")
    print("-" * 90)
    for s in updated:
        print(f"{s['index']:<6} {s['friendlyName']:<40} {s['guid']}")


def _cmd_edit(args: argparse.Namespace) -> None:
    try:
        guid = edit_script(args.name_or_guid, base_dir=args.base_dir)
        print(f"Saved: {guid}")
        print("Verification: passed")
    except (KeyError, ValueError, RuntimeError, OSError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_backup(args: argparse.Namespace) -> None:
    try:
        path = backup(args.output, base_dir=args.base_dir)
        print(f"Backup written: {path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_restore(args: argparse.Namespace) -> None:
    try:
        count = restore(args.backup_file, merge=args.merge, base_dir=args.base_dir)
        mode = "merged" if args.merge else "restored"
        print(f"{count} script(s) {mode} from '{args.backup_file}'")
        print("Verification: passed")
    except (FileNotFoundError, OSError, ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_camerahub(args: argparse.Namespace) -> None:
    try:
        if args.action == "stop":
            camerahub_stop(wait=True)
            print("Camera Hub stopped.")
        elif args.action == "start":
            camerahub_start()
            print("Camera Hub started.")
    except EnvironmentError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_doctor(args: argparse.Namespace) -> None:
    try:
        rows = diagnose_camerahub(args.base_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    failed = False
    print("PrompterKit doctor")
    print("-" * 80)
    for row in rows:
        status = row["status"]
        if status == "FAIL":
            failed = True
        print(f"{status:<5} {row['check']:<28} {row['detail']}")
    if failed:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import/export scripts for Elgato Prompter (Camera Hub)."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    data_parent = argparse.ArgumentParser(add_help=False)
    data_parent.add_argument(
        "--base-dir",
        help="Camera Hub data directory override (useful for copied fixtures and troubleshooting)",
    )

    # import subcommand
    p_import = sub.add_parser("import", parents=[data_parent], help="Import a .txt file as a Prompter script")
    p_import.add_argument("text_file", help="Path to the .txt script file")
    p_import.add_argument("--name", required=True, help="Friendly name for the script")
    p_import.add_argument("--index", type=int, default=0, help="Order index (default: 0)")
    p_import.add_argument("--restart", action="store_true", help="Stop Camera Hub before import and restart after")

    # push alias
    p_push = sub.add_parser("push", parents=[data_parent], help="Alias for import: push a local script into Camera Hub")
    p_push.add_argument("text_file", help="Path to the .txt script file")
    p_push.add_argument("--name", required=True, help="Friendly name for the script")
    p_push.add_argument("--index", type=int, default=0, help="Order index (default: 0)")
    p_push.add_argument("--restart", action="store_true", help="Stop Camera Hub before push and restart after")

    # export subcommand
    p_export = sub.add_parser("export", parents=[data_parent], help="Export Prompter script(s) to .txt files")
    p_export.add_argument("--guid", help="Export script by GUID")
    p_export.add_argument("--name", help="Export script by friendly name")
    p_export.add_argument("--output", help="Output file (single export) or directory (--all)")
    p_export.add_argument("--all", action="store_true", help="Export all registered scripts")
    p_export.add_argument("--list", action="store_true", help="List all registered scripts")

    # pull alias
    p_pull = sub.add_parser("pull", parents=[data_parent], help="Alias for export: pull scripts out of Camera Hub")
    p_pull.add_argument("--guid", help="Export script by GUID")
    p_pull.add_argument("--name", help="Export script by friendly name")
    p_pull.add_argument("--output", help="Output file (single export) or directory (--all)")
    p_pull.add_argument("--all", action="store_true", help="Export all registered scripts")
    p_pull.add_argument("--list", action="store_true", help="List all registered scripts")

    # delete subcommand
    p_delete = sub.add_parser("delete", parents=[data_parent], help="Remove a script by name or GUID")
    p_delete.add_argument("name_or_guid", help="Script friendly name or GUID")

    # rename subcommand
    p_rename = sub.add_parser("rename", parents=[data_parent], help="Rename an existing script")
    p_rename.add_argument("name_or_guid", help="Current friendly name or GUID")
    p_rename.add_argument("new_name", help="New friendly name")

    # reindex subcommand
    p_reindex = sub.add_parser("reindex", parents=[data_parent], help="Reorder the script library by assigning new index values")
    p_reindex.add_argument(
        "name_or_guid",
        nargs="*",
        help="Scripts in desired order (by name or GUID). Omit to normalize existing order.",
    )

    # edit subcommand
    p_edit = sub.add_parser("edit", parents=[data_parent], help="Open a script's chapters in $EDITOR")
    p_edit.add_argument("name_or_guid", help="Script friendly name or GUID")

    # backup subcommand
    p_backup = sub.add_parser("backup", parents=[data_parent], help="Export all scripts to a timestamped zip archive")
    p_backup.add_argument("--output", help="Output zip path (default: prompter_backup_TIMESTAMP.zip)")

    # restore subcommand
    p_restore = sub.add_parser("restore", parents=[data_parent], help="Restore scripts from a backup zip")
    p_restore.add_argument("backup_file", help="Path to the backup zip")
    p_restore.add_argument("--merge", action="store_true", help="Add new scripts without replacing existing ones")

    # doctor subcommand
    sub.add_parser("doctor", parents=[data_parent], help="Inspect Camera Hub data path and common sync failure modes")

    # camerahub subcommand
    p_camerahub = sub.add_parser("camerahub", help="Control the Camera Hub application lifecycle")
    p_camerahub.add_argument("action", choices=["stop", "start"], help="stop or start Camera Hub")

    args = parser.parse_args()

    dispatch = {
        "import": _cmd_import,
        "push": _cmd_import,
        "export": _cmd_export,
        "pull": _cmd_export,
        "delete": _cmd_delete,
        "rename": _cmd_rename,
        "reindex": _cmd_reindex,
        "edit": _cmd_edit,
        "backup": _cmd_backup,
        "restore": _cmd_restore,
        "doctor": _cmd_doctor,
        "camerahub": _cmd_camerahub,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
