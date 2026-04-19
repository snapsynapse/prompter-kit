import argparse
import json
import os
import re
import sys
import tempfile
import uuid


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
    if base_dir is None:
        base_dir = get_camerahub_path()
    dest = os.path.join(base_dir, "Texts", f"{guid_str}.json")
    try:
        _atomic_write_json(dest, data)
    except OSError as e:
        raise OSError(f"Could not write script JSON to '{dest}': {e}") from e
    return dest


def update_appsettings(guid_str: str, base_dir: str | None = None) -> str:
    """Register guid_str in AppSettings.json libraryList. Returns the settings path."""
    if base_dir is None:
        base_dir = get_camerahub_path()
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

    chapters = convert_text_file(text_file)
    guid_str = str(uuid.uuid4()).upper()
    json_data = generate_json_data(chapters, guid_str, friendly_name, index)

    script_path = save_json_to_texts(json_data, guid_str, base_dir)

    try:
        settings_path = update_appsettings(guid_str, base_dir)
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
    if base_dir is None:
        base_dir = get_camerahub_path()

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
    if base_dir is None:
        base_dir = get_camerahub_path()
    path = os.path.join(base_dir, "Texts", f"{guid_str}.json")
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

    for script in scripts:
        if script["missing"]:
            print(f"Warning: skipping '{script['guid']}' (file missing or corrupt)", file=sys.stderr)
            continue

        slug = _slugify(script["friendlyName"]) or script["guid"]
        output_path = os.path.join(output_dir, f"{slug}.txt")

        # Avoid silently overwriting if two scripts share a friendly name
        if os.path.exists(output_path):
            output_path = os.path.join(output_dir, f"{slug}_{script['guid'][:8]}.txt")

        try:
            export_script(script["guid"], output_path, base_dir)
            exported.append((script["guid"], output_path))
        except Exception as e:
            print(f"Warning: could not export '{script['guid']}': {e}", file=sys.stderr)

    return exported


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
    try:
        script_path, settings_path = import_script(args.text_file, args.name.strip(), args.index)
        print(f"Script saved:  {script_path}")
        print(f"AppSettings:   {settings_path}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_export(args: argparse.Namespace) -> None:
    base_dir = None

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import/export scripts for Elgato Prompter (Camera Hub)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # import subcommand
    p_import = sub.add_parser("import", help="Import a .txt file as a Prompter script")
    p_import.add_argument("text_file", help="Path to the .txt script file")
    p_import.add_argument("--name", required=True, help="Friendly name for the script")
    p_import.add_argument("--index", type=int, default=0, help="Order index (default: 0)")

    # export subcommand
    p_export = sub.add_parser("export", help="Export Prompter script(s) to .txt files")
    p_export.add_argument("--guid", help="Export script by GUID")
    p_export.add_argument("--name", help="Export script by friendly name")
    p_export.add_argument("--output", help="Output file (single export) or directory (--all)")
    p_export.add_argument("--all", action="store_true", help="Export all registered scripts")
    p_export.add_argument("--list", action="store_true", help="List all registered scripts")

    args = parser.parse_args()

    if args.command == "import":
        _cmd_import(args)
    elif args.command == "export":
        _cmd_export(args)


if __name__ == "__main__":
    main()
