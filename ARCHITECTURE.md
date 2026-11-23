# Architecture

This document describes how PrompterKit is structured for contributors. For
usage, see [README.md](README.md).

## Overview

PrompterKit is a management layer over the Elgato Camera Hub on-disk data
format. It reads and writes files directly to provide text conversion,
library management, and backups. Safeguards reduce some write risks; they
cannot guarantee recovery or compatibility with future Camera Hub versions.

The project is two modules over one core library:

```
prompter_kit.py       CLI entry point + core library (all operations)
prompter_kit_gui.py   Flask web GUI, a thin layer that calls the core library
```

The GUI calls core mutation functions and shares text-conversion and export
naming helpers with the CLI. It adds upload validation and HTTP responses.
Backup, restore, and explicit reorder are CLI workflows.

## Camera Hub data model

Camera Hub keeps Prompter data in one directory:

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Elgato/Camera Hub/` |
| Windows | `%APPDATA%\Elgato\Camera Hub\` |

A legacy `CameraHub` directory (no space) is used as a fallback when only that
older path exists.

Two kinds of file matter:

- `AppSettings.json` - the registry list of script GUIDs.
  Names and sort indexes live in the per-script JSON files.
- `Texts/<GUID>.json` — per-script content. Each chapter is one entry and one
  Camera Hub scroll/save point. On import, a blank line (hard return) starts a
  new chapter and a single newline (soft return) is kept as a line break inside
  the chapter, matching how Camera Hub itself stores embedded newlines.

A script exists only when both its registry entry and its `Texts/` file are
present and their GUIDs agree. Import and delete update both; rename, edit,
and reindex update script files. There is no library-wide transaction or lock.

## File format reference

This is the complete on-disk format PrompterKit understands, recorded so the
project can be forked or reimplemented. Automated compatibility evidence uses
sanitized fixtures. A macOS live eval passed in June 2026, but its Camera Hub
version was not recorded. No current-version or all-2.x compatibility claim
is made. The schema guard checks selected fields, with exceptions below.

`AppSettings.json` is a flat JSON object holding every Camera Hub setting.
Normal library operations modify one key and preserve the others.
Replace restore replaces the full settings file from the archive:

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
  when importing. The GUID validation applies to schema checks and restore;
  read helpers do not uniformly enforce it.

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
in two on export-then-reimport. Empty chapters also do not round-trip.
From 1.0.2, .txt imports preserve literal characters and nonblank-line spaces;
.md imports use the existing Markdown stripping rules. Both normalize line
endings and collapse blank-line separators.

Backup zips contain `AppSettings.json` at the root plus `Texts/<GUID>.json`
for registered scripts that can be read and parsed. Missing, corrupt, and
unregistered script files and other Camera Hub data are excluded. Replace
restore removes the entire live Texts directory, including unregistered files,
and replaces unrelated settings too. Keep an independent full directory copy.
Merge can overwrite unregistered files at incoming GUID paths. Archives contain
private script content and settings. `restore` rejects unexpected archive paths,
duplicate entries, or GUID mismatches; it does not fully validate script schema
or limit entry sizes. A restored script with an unrecognized shape makes the
schema guard refuse later writes until that file is removed or replaced.

PrompterKit also writes automatic pre-write snapshots (same zip format) to
`PrompterKitBackups/` inside the data directory. This is separate from GUI
Export all, whose ZIP contains only text and cannot be used with restore.

## Module map

### prompter_kit.py

Grouped by responsibility:

- Path resolution: `get_camerahub_path`, `_resolve_base_dir`,
  `_script_json_path`. CLI `--base-dir` and GUI `PROMPTERKIT_BASE_DIR` override the
  discovered path so operations can run against a disposable copy.
- Atomic I/O: `_atomic_write_json`, `_load_appsettings`, `save_json_to_texts`,
  `update_appsettings`.
- Verification: `verify_script_registered`, `verify_script_absent`. Called
  after writes to confirm the expected change is visible on disk.
- Write guard: `check_library_schema`, `auto_backup`, `_pre_write_guard`,
  `SchemaError`. Used by normal mutation operations; restore bypasses the live
  schema check and uses a best-effort snapshot.
- Conversion: `strip_markdown`, `group_into_chapters`, `chapters_to_text`,
  `convert_text_file`, `generate_json_data`. `group_into_chapters` and
  `chapters_to_text` share the blank-line convention, with the normalization
  and fidelity limits described above.
- Core operations: `import_script`, `list_scripts`, `export_script`,
  `export_all`, `delete_script`, `rename_script`, `reindex_scripts`,
  `edit_script`, `backup`, `restore`.
- Camera Hub lifecycle: `camerahub_is_running`, `camerahub_stop`,
  `camerahub_start` (macOS `osascript` / `open`, trying current
  `Elgato Camera Hub` and legacy `Camera Hub` app names; Windows
  `tasklist`, a forced `taskkill /F`, and `start`, each resolved by bare
  name through the normal Windows search path).
- Diagnostics: `diagnose_camerahub`, backing the `doctor` command.
- CLI layer: `_cmd_*` handlers and `main`, which builds the argparse
  subcommands.

### prompter_kit_gui.py

A Flask app that imports the core library. It adds only web concerns:

- A `PROMPTERKIT_BASE_DIR` environment override and index parsing.
- CSRF protection: `_csrf_token`, `_validate_csrf`, a `_protect_post_routes`
  before-request hook, and a `_inject_csrf_token` context processor.
- Upload validation: `_validate_import_filename` rejects unsupported
  extensions. Uploads use generated temporary filenames.
- Routes: `/`, `/import`, `/export/<guid>`, `/export-all`, `/delete/<guid>`,
  `/rename/<guid>`, `/reindex`. Every write route is POST and CSRF-checked.
  Single export serves registered scripts only.
- Host check: `_reject_untrusted_host` returns 400 unless the Host header names
  `127.0.0.1` or `localhost`, so a web page cannot reach the GUI under its own
  hostname.
- Response headers: `_set_security_headers` sends a Content-Security-Policy
  with a per-response script nonce, plus frame, content-type, and referrer
  headers. The template has no inline event handlers; script names reach the
  page script only through data attributes.
- `_open_browser` opens the local browser on launch. The server binds to
  `127.0.0.1` only.

## Write safety

Five layers protect the data directory:

1. Schema guard. Import, rename, delete, edit, and reindex check known fields
   before mutation. Missing and unparseable script files are tolerated; absent
   registry keys are accepted. Detected drift raises SchemaError, but unknown
   future formats are not guaranteed detectable. Read paths bypass this guard
   and can also fail on unknown data.
2. Automatic pre-write snapshot. `auto_backup` zips the current library to
   `PrompterKitBackups/` inside the data directory before the write, keeping
   the up to `AUTO_BACKUP_KEEP` (20) snapshots. Disable with
   `PROMPTERKIT_AUTO_BACKUP=0`. Snapshots have the backup exclusions above;
   they do not guarantee that every destructive operation is reversible.
3. Atomic writes. JSON is written to a temporary file and renamed into place,
   providing per-file atomic replacement, not a transaction across all files.
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
swap or verification fails. Merge mode rolls back any script JSON files it
writes if the final `AppSettings.json` update fails, preserving pre-existing
unregistered files at those paths. Merge verification after the settings commit
is outside that rollback block. Rollback can itself fail due to filesystem
errors. No operation guarantees recovery or prevents concurrent writers.

## CLI and aliases

`push` is an alias for `import` and `pull` is an alias for `export`, for
users who think of local scripts as device sync operations. Aliases share the
underlying command handlers; they are not separate implementations.

## Testing

Literal
```sh
python3 -m pytest tests/ -v
python3 scripts/check_agent_surfaces.py
```

- `tests/test_importer.py` — import, export, Markdown stripping, round trips.
- `tests/test_crud.py` — delete, rename, reindex, backup, restore.
- `tests/test_write_guard.py` — schema guard and automatic pre-write snapshots.
- `tests/test_diagnostics.py` — `doctor` checks and Camera Hub path discovery.
- `tests/test_gui.py` — GUI routes, CSRF protection, upload validation, host
  check, response headers, script-name handling.
- `tests/fixtures/` — sanitized Camera Hub data used by the suite.

Tests run against a temporary directory via `--base-dir`, never the live
Camera Hub data. `scripts/manual_live_eval.sh` is an opt-in smoke test that
does touch the real directory and is excluded from the default run.
