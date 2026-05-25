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
- `Texts/<GUID>.json` — per-script content. Each chapter is one entry; on
  import, each non-empty input line becomes one chapter.

A script exists only when both its registry entry and its `Texts/` file are
present and their GUIDs agree. Most write operations touch both files, which
is why write safety is the central design concern.

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
- Conversion: `strip_markdown`, `convert_text_file`, `generate_json_data`.
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

Three layers protect the data directory:

1. Atomic writes. JSON is written to a temporary file and renamed into place,
   so an interrupted write cannot leave a half-written `AppSettings.json`.
2. Post-write verification. After a write, the registry and script JSON are
   reloaded and the operation fails loudly if the expected change is absent.
3. Rollback. If updating `AppSettings.json` fails after a new script JSON has
   been written, the orphaned script JSON is removed.

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
- `tests/test_diagnostics.py` — `doctor` checks and Camera Hub path discovery.
- `tests/test_gui.py` — GUI routes, CSRF protection, upload validation.
- `tests/fixtures/` — sanitized Camera Hub data used by the suite.

Tests run against a temporary directory via `--base-dir`, never the live
Camera Hub data. `scripts/manual_live_eval.sh` is an opt-in smoke test that
does touch the real directory and is excluded from the default run.
