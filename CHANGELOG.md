# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-06-12

Maintenance hardening patch. PrompterKit remains feature-complete and in
maintenance mode.

### Fixed
- Mutating operations now run the schema guard before resolving, sorting, or
  editing scripts, so future Camera Hub format drift is reported as a
  `SchemaError` instead of an incidental Python sorting/type error.
- `restore --merge` now rolls back script JSON files if updating
  `AppSettings.json` fails after new files are written, including preserving
  any pre-existing unregistered JSON file at the same path.
- macOS Camera Hub lifecycle commands now try the current app name
  (`Elgato Camera Hub`) before the legacy `Camera Hub` name, so
  `--restart` can relaunch current installs.

## [1.0.0] - 2026-06-09

Final feature release. PrompterKit is feature-complete; no further
development is planned. See ROADMAP.md for what 1.0.0 guarantees and how to
fork.

### Added
- Schema guard: every write operation now verifies that AppSettings.json and
  all registered script JSON still match the documented Camera Hub format
  before touching anything, and refuses with a clear error if the format has
  drifted (for example after a future Camera Hub update). Read-only
  operations (list, export, backup) are never blocked.
- Automatic pre-write snapshots: every write operation first archives the
  current library to `PrompterKitBackups/` inside the Camera Hub data
  directory (newest 20 kept), so any change can be undone with `restore`.
  Disable with `PROMPTERKIT_AUTO_BACKUP=0`.
- Complete on-disk file format reference in ARCHITECTURE.md, sufficient to
  fork or reimplement the tool without reverse-engineering.
- `tests/test_write_guard.py` covering the schema guard, snapshot rotation,
  and restore-despite-corruption behavior.

### Changed
- `restore` skips the schema guard and treats the pre-write snapshot as
  best-effort, so a corrupt live library cannot block recovery from a
  known-good backup.
- Flask dependency pinned to an exact known-good version (3.1.3) so the GUI
  install stays reproducible without ongoing maintenance.
- ROADMAP.md rewritten as a maintenance-mode statement; the standalone
  double-click app plan is dropped.
- README and site now carry a maintenance-status notice describing what
  Camera Hub covers natively (rename, reorder, auto-save) and what
  PrompterKit still uniquely provides (txt/md import/export, backup/restore,
  CLI automation).

## [0.6.1] - 2026-05-29

### Fixed
- GUI single-script export and export-all now use the same `chapters_to_text`
  helper as the CLI, preserving blank-line chapter boundaries and soft returns
  in exported text.

### Changed
- Assistant guide metadata, security policy, and site modified dates now reflect
  the 0.6.1 release.

## [0.6.0] - 2026-05-28

### Changed
- Import now distinguishes soft returns from hard returns. A blank line is a
  hard return that starts a new chapter (a new Camera Hub scroll/save point); a
  single newline is a soft return kept as a line break inside the chapter. This
  matches how Camera Hub itself stores embedded newlines. Previously every line
  became its own chapter and blank lines were discarded.
- Export and `edit` use the same convention: chapters are separated by a blank
  line and soft breaks are preserved, so a script round-trips through export
  and re-import without losing structure.

### Added
- `group_into_chapters` and `chapters_to_text` helpers in `prompter_kit.py`,
  the single source of truth for the chapter/return convention shared by
  import, export, and `edit`.

### Note
- A chapter that itself contains a blank line (only possible from manual Camera
  Hub authoring) will split into two chapters if exported to text and
  re-imported, since flat text uses the blank line as the chapter boundary.

## [0.5.2] - 2026-05-28

### Added
- Site landing page now has an Instructions section above the optional CLI
  commands, walking through how to start and use PrompterKit after install,
  with a matching nav link.
- Site landing page now has a Troubleshooting section covering common launch
  failures (wrong directory, missing Flask, Python version, port in use, and
  Camera Hub not reflecting changes), with a matching nav link.

### Fixed
- Replace-mode `restore` now stages replacement files before touching the live
  library and rolls back the prior `Texts/` directory and `AppSettings.json` if
  the final swap or verification fails.
- `import --restart` and `push --restart` now attempt to restart Camera Hub
  after a successful stop even when the import fails.

### Changed
- Assistant guide updated to GuideCheck profile 0.3.0 at conformance Level 4,
  with sidecar manifest, public transparency-log anchor, repository hash
  anchor, and root discovery copies.
- README and site install copy now link directly to the GuideCheck Level 4
  evidence files.

## [0.5.1] - 2026-05-21

### Added
- Assistant guide at `/.well-known/assistant-guide.txt`, originally built to
  the [GuideCheck](https://guidecheck.org/) standard at conformance Level 3.
- `ARCHITECTURE.md` describing the Camera Hub data model, module layout, and
  write-safety design.

### Changed
- Documentation and `llms.txt` now point to the GuideCheck-conformant
  assistant guide.
- Quick setup on the site and in the README now splits into AI Assisted
  Install and Terminal Install tabs; the CLI command reference moved to its
  own optional section.

### Fixed
- README header image now uses a repo-relative path so it renders on GitHub.

## [0.5.0] - 2026-05-21

### Added
- Plain-text AI-assisted install guide with a copy-paste prompt, approval
  checklist, and prompt-injection mitigations for users installing through
  ChatGPT, Claude, Codex, or another local coding assistant.
- `requirements-gui.txt` for repeatable GUI dependency installation.
- `doctor` command for Camera Hub path, process, library, missing script,
  duplicate-name, and orphan JSON diagnostics.
- `push` and `pull` aliases for users who think of local scripts as device
  sync operations.
- `--base-dir` troubleshooting override for commands that read or write Camera
  Hub data.
- Post-write verification helpers and tests for push/pull round trips,
  diagnostics, and verification failures.
- Sanitized Camera Hub fixture data and an opt-in `scripts/manual_live_eval.sh`
  live smoke test.
- Regression coverage for current Camera Hub data directory discovery on macOS
  and Windows.

### Changed
- Camera Hub data directory discovery now prefers `Camera Hub` with a space,
  matching current Camera Hub builds, and falls back to legacy `CameraHub` when
  only that directory exists.
- Write operations now verify that expected changes are visible on disk before
  reporting success.
- GUI write routes now require CSRF tokens, and script imports reject unsupported
  file extensions and oversized uploads.
- Install documentation now recommends a local Python virtual environment
  instead of global Flask installation.
- `--restart` waits for Camera Hub to exit before writing.
- Test suite expanded to 105 tests.

## [0.4.0] - 2026-04-23

### Changed
- `restore` now validates backup zips before writing: checks for missing or
  malformed `AppSettings.json`, duplicate archive paths, GUID format (alphanumeric
  plus `.`, `_`, `-` only), unexpected files, and GUID cross-checks between
  metadata and script JSON.
- Export filename collision logic extracted into `_unique_text_filename` helper,
  shared between the CLI `export --all` path and the GUI zip-export path.
- 8 new tests (79 total).

## [0.3.0] - 2026-04-19

### Added
- `delete` command: remove a script by name or GUID
- `rename` command: change a script's friendly name
- `reindex` command: reorder the library, or normalize indices with no args
- `edit` command: open a script's chapters in `$EDITOR`
- `backup` command: zip all scripts plus `AppSettings.json` into a timestamped archive
- `restore` command: restore from a backup zip, with `--merge` to preserve existing scripts
- `camerahub stop` / `camerahub start`: quit or relaunch Camera Hub
  (macOS `osascript`, Windows `taskkill`)
- `--restart` flag on `import`: auto-stop Camera Hub before write, auto-start after
- Local web GUI (`prompter_kit_gui.py`) wrapping all CLI functions with
  drag-and-drop import, browser-based export, and auto-open on launch
- Landing page at https://prompterkit.app/ with OG image and `llms.txt`

### Changed
- Renamed project to PrompterKit. CLI module is now `prompter_kit.py` and GUI
  module is `prompter_kit_gui.py`. Repository moved to
  `snapsynapse/prompter-kit`; canonical site is https://prompterkit.app/.
  Any scripts or imports referencing the old `elgato_prompter_tools` module
  names must be updated.
- README rewritten against the current CLI surface.
- ROADMAP trimmed to remaining work (double-click app bundling).

## [0.2.0] - 2026-04-18

### Added
- Markdown stripping on import: `#`, `*`, `_` and other formatting are removed
  before chapters are stored, so `.md` files import cleanly as plain teleprompter text
- `strip_markdown` function exposed as a public API

## [0.1.0] - 2026-04-18

### Added
- `import` command: reads a plain `.txt` file (one line per chapter) and registers
  it as an Elgato Prompter script in Camera Hub
- `export` command: exports a registered script back to `.txt` by GUID or friendly name
- `export --list`: lists all scripts registered in Camera Hub
- `export --all`: exports every registered script to a directory
- Atomic JSON writes to prevent data corruption on interrupted writes
- Rollback of the script JSON file if the AppSettings update fails
- macOS and Windows platform path support
- Full test suite with pytest
