# Architecture

This document describes how PrompterKit is structured for contributors. For
usage, see [README.md](README.md).

## Overview

PrompterKit is a management layer over the Elgato Camera Hub on-disk data
format. Camera Hub stores Prompter scripts but exposes no import, export,
rename, reorder, or backup path. PrompterKit reads and writes the same files
directly, with safeguards so a failed operation cannot leave the data
directory corrupt.

The project is two modules over one core library:

```
prompter_kit.py       CLI entry point + core library (all operations)
prompter_kit_gui.py   Flask web GUI, a thin layer that calls the core library
```

The GUI duplicates no logic. Every route resolves to the same functions the
CLI calls, so behavior and safety guarantees are identical across surfaces.

## Camera Hub data model

Camera Hub keeps Prompter data in one directory:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Elgato/Camera Hub/` |
| Windows | `%APPDATA%\Elgato\Camera Hub\` |

A legacy `CameraHub` directory (no space) is used as a fallback when only that
older path exists.

Two kinds of file matter:

- `AppSettings.json` — the registry. Each script has a GUID, an index that
  sets library order, and a friendly name.
- `Texts/<GUID>.json` — per-script content. Each chapter is one entry and one
  Camera Hub scroll/save point. On import, a blank line (hard return) starts a
  new chapter and a single newline (soft return) is kept as a line break inside
  the chapter, matching how Camera Hub itself stores embedded newlines.

A script exists only when both its registry entry and its `Texts/` file are
present and their GUIDs agree. Most write operations touch both files, which
is why write safety is the central design concern.

## File format reference

This is the complete on-disk format PrompterKit understands, recorded so the
project can be forked or reimplemented without reverse-engineering. Last
verified against Camera Hub 2.x. The schema guard (below) refuses to write
when live data no longer matches this shape.

`AppSettings.json` is a flat JSON object holding every Camera Hub setting.
PrompterKit reads and writes exactly one key and preserves all others:

```json
{
    "applogic.prompter.libraryList": [
        "6A3F0F0A-1111-2222-3333-444455556666",
        "0B1C2D3E-AAAA-BBBB-CCCC-DDDDEEEEFFFF"
    ]
}
```

- The value is a list of script GUIDs. List order is not display order;
  display order comes from each script's `index`.
- GUIDs are uppercase UUID4 strings. PrompterKit accepts any string matching
  `[A-Za-z0-9._-]+` when reading, and generates `str(uuid.uuid4()).upper()`
  when importing.

`Texts/<GUID>.json` is one JSON object per script:

```json
{
    "GUID": "6A3F0F0A-1111-2222-3333-444455556666",
    "chapters": [
        "First chapter line one\nline two after a soft return",
        "Second chapter"
    ],
    "friendlyName": "My Script",
    "index": 0
}
```

- `GUID` (string): matches the filename stem. Camera Hub sometimes writes an
  empty string here; PrompterKit accepts `""`, absent, or the matching GUID.
- `chapters` (list of strings): one entry per chapter. A chapter is one
  Camera Hub scroll/save point. Embedded `\n` is a soft return rendered as a
  line break without a new scroll point.
- `friendlyName` (string): display name. Not required to be unique; the
  `doctor` command warns on duplicates.
- `index` (integer): 0-based library sort position.

Text round-trip convention (`group_into_chapters` / `chapters_to_text`): in
flat text, a blank line is a hard return separating chapters and a single
newline is a soft return kept inside the chapter. A chapter that itself
contains a blank line (possible only from manual Camera Hub authoring) splits
in two on export-then-reimport.

Backup zips contain `AppSettings.json` at the root plus `Texts/<GUID>.json`
for every registered, non-missing script, and nothing else. `restore` rejects
archives with unexpected paths, duplicate entries, or GUID mismatches.

PrompterKit also writes automatic pre-write snapshots (same zip format) to
`PrompterKitBackups/` inside the data directory. Camera Hub ignores the extra
directory.

## Module map

### prompter_kit.py

Grouped by responsibility:

- Path resolution: `get_camerahub_path`, `_resolve_base_dir`,
  `_script_json_path`. `--base-dir` and `PROMPTERKIT_BASE_DIR` override the
  discovered path so operations can run against a disposable copy.
- Atomic I/O: `_atomic_write_json`, `_load_appsettings`, `save_json_to_texts`,
  `update_appsettings`.
- Verification: `verify_script_registered`, `verify_script_absent`. Called
  after writes to confirm the expected change is visible on disk.
- Write guard: `check_library_schema`, `auto_backup`, `_pre_write_guard`,
  `SchemaError`. Called at the top of every mutating operation.
- Conversion: `strip_markdown`, `group_into_chapters`, `chapters_to_text`,
  `convert_text_file`, `generate_json_data`. `group_into_chapters` and
  `chapters_to_text` are inverses over the blank-line chapter convention, so
  import, export, and `edit` all round-trip through one definition.
- Core operations: `import_script`, `list_scripts`, `export_script`,
  `export_all`, `delete_script`, `rename_script`, `reindex_scripts`,
  `edit_script`, `backup`, `restore`.
- Camera Hub lifecycle: `camerahub_is_running`, `camerahub_stop`,
  `camerahub_start` (macOS `osascript`, Windows `taskkill`).
- Diagnostics: `diagnose_camerahub`, backing the `doctor` command.
- CLI layer: `_cmd_*` handlers and `main`, which builds the argparse
  subcommands.

### prompter_kit_gui.py

A Flask app that imports the core library. It adds only web concerns:

- A shared `--base-dir` resolver and index parsing.
- CSRF protection: `_csrf_token`, `_validate_csrf`, a `_protect_post_routes`
  before-request hook, and a `_inject_csrf_token` context processor.
- Upload validation: `_validate_import_filename` rejects unsupported
  extensions and unsafe names.
- Routes: `/`, `/import`, `/export/<guid>`, `/export-all`, `/delete/<guid>`,
  `/rename/<guid>`, `/reindex`. Every write route is POST and CSRF-checked.
- `_open_browser` opens the local browser on launch. The server binds to
  `127.0.0.1` only.

## Write safety

Five layers protect the data directory:

1. Schema guard. Before any write, `check_library_schema` verifies the live
   data still matches the file format reference above. If Camera Hub has
   changed its format since this project was last maintained, every write is
   refused with a `SchemaError` rather than risking corruption. Read paths
   (list, export, backup) are never blocked.
2. Automatic pre-write snapshot. `auto_backup` zips the current library to
   `PrompterKitBackups/` inside the data directory before the write, keeping
   the newest `AUTO_BACKUP_KEEP` (20) snapshots. Disable with
   `PROMPTERKIT_AUTO_BACKUP=0`. Every destructive operation is therefore
   reversible with `restore`.
3. Atomic writes. JSON is written to a temporary file and renamed into place,
   so an interrupted write cannot leave a half-written `AppSettings.json`.
4. Post-write verification. After a write, the registry and script JSON are
   reloaded and the operation fails loudly if the expected change is absent.
5. Rollback. If updating `AppSettings.json` fails after a new script JSON has
   been written, the orphaned script JSON is removed.

`restore` is the recovery path, so it skips the schema guard and treats the
pre-write snapshot as best-effort: a corrupt live library must not block
restoring from a known-good backup.

`restore` adds a validation pass before writing anything: the backup zip must
contain a parseable `AppSettings.json`, every GUID must match
`[A-Za-z0-9._-]+`, no unexpected paths may be present, and each script's
embedded GUID must match its filename. Replace mode builds a staged `Texts/`
directory first, swaps it into place, and restores the prior live files if the
swap or verification fails.

## CLI and aliases

`push` is an alias for `import` and `pull` is an alias for `export`, for
users who think of local scripts as device sync operations. Aliases share the
underlying command handlers; they are not separate implementations.

## Testing

```
python3 -m pytest tests/ -v
```

- `tests/test_importer.py` — import, export, Markdown stripping, round trips.
- `tests/test_crud.py` — delete, rename, reindex, backup, restore.
- `tests/test_write_guard.py` — schema guard and automatic pre-write snapshots.
- `tests/test_diagnostics.py` — `doctor` checks and Camera Hub path discovery.
- `tests/test_gui.py` — GUI routes, CSRF protection, upload validation.
- `tests/fixtures/` — sanitized Camera Hub data used by the suite.

Tests run against a temporary directory via `--base-dir`, never the live
Camera Hub data. `scripts/manual_live_eval.sh` is an opt-in smoke test that
does touch the real directory and is excluded from the default run.
