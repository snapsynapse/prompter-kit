# PrompterKit

![PrompterKit -- Manage your Elgato Prompter scripts](/imgs/og.png)

Manage your Elgato Prompter scripts from the command line or a local web GUI.
Camera Hub stores scripts in opaque JSON with no import, export, rename,
reorder, or backup path. PrompterKit fills every gap.

Site: https://prompterkit.app/
Repo: https://github.com/snapsynapse/prompter-kit

Based on [spieldbergo/elgato_prompter_text_importer](https://github.com/spieldbergo/elgato_prompter_text_importer) (MIT).

## Requirements

- Python 3.10+
- Elgato Camera Hub installed
- Flask (GUI only): `pip install flask`

Close Camera Hub before any write operation, or use `--restart` / the
`camerahub` subcommand to have PrompterKit do it for you.

## Quick start

### CLI

```
# Import a .txt or .md file (one line per chapter)
python3 prompter_kit.py import script.md --name "My Script"

# Import and auto-restart Camera Hub around the write
python3 prompter_kit.py import script.txt --name "My Script" --restart

# Same operation using push/pull language
python3 prompter_kit.py push script.txt --name "My Script" --restart
python3 prompter_kit.py pull --name "My Script" --output my_script.txt

# List registered scripts
python3 prompter_kit.py export --list

# Export one script by name or GUID
python3 prompter_kit.py export --name "My Script" --output my_script.txt

# Export every script to a directory
python3 prompter_kit.py export --all --output ./exported/

# Rename, delete, reorder
python3 prompter_kit.py rename "Old Name" "New Name"
python3 prompter_kit.py delete "My Script"
python3 prompter_kit.py reindex "Intro" "Act One" "Outro"

# Edit chapters in $EDITOR
python3 prompter_kit.py edit "My Script"

# Back up and restore the whole library
python3 prompter_kit.py backup --output backup.zip
python3 prompter_kit.py restore backup.zip           # replaces library
python3 prompter_kit.py restore backup.zip --merge   # adds new only

# Quit or relaunch Camera Hub
python3 prompter_kit.py camerahub stop
python3 prompter_kit.py camerahub start

# Diagnose the Camera Hub data directory
python3 prompter_kit.py doctor

# Test against a copied Camera Hub folder instead of the live one
python3 prompter_kit.py doctor --base-dir /tmp/prompterkit-eval
python3 prompter_kit.py push script.txt --name "Eval Script" --base-dir /tmp/prompterkit-eval

# Opt-in live smoke test against the real Camera Hub directory
scripts/manual_live_eval.sh
```

### GUI

```
python3 prompter_kit_gui.py
```

Opens a local web app in your browser for import, export, rename, delete,
reorder, backup, and restore, with drag-and-drop file input.

## Commands

| Command | What it does |
|---|---|
| `import` | Register a `.txt` or `.md` file as a Prompter script. Markdown formatting is stripped. |
| `push` | Alias for `import`, for pushing a local script into Camera Hub. |
| `export` | Write a script, or all scripts, back to `.txt`. Supports `--list`, `--name`, `--guid`, `--all`. |
| `pull` | Alias for `export`, for pulling scripts out of Camera Hub. |
| `delete` | Remove a script from `Texts/` and `AppSettings.json`. |
| `rename` | Change a script's friendly name. |
| `reindex` | Reorder the library. Pass names/GUIDs in desired order, or no args to normalize. |
| `edit` | Open a script's chapters in `$EDITOR` and re-save on close. |
| `backup` | Zip all scripts plus `AppSettings.json` into a timestamped archive. |
| `restore` | Restore from a backup zip. `--merge` keeps existing scripts. |
| `doctor` | Report Camera Hub path, AppSettings/Text status, missing scripts, duplicate names, orphan files, and whether Camera Hub appears to be running. |
| `camerahub stop` / `start` | Quit or relaunch Camera Hub (macOS `osascript`, Windows `taskkill`). |

Most commands accept `--base-dir` after the command name. Use it to run against
a copied Camera Hub directory before touching the live device data.

## Script format

Plain `.txt` or `.md`. Each non-empty line becomes one chapter.

```markdown
# Act One

- Welcome to the show.
- **Tonight** we cover three topics.
```

imports as three plain chapters. Markdown headings, bold, italic, links,
images, inline code, blockquotes, list bullets, and strikethrough are stripped.

## Safety

- Atomic writes: JSON is written to a temp file then renamed, so an
  interrupted write cannot corrupt `AppSettings.json`.
- Post-write verification: write operations reload `AppSettings.json` and the
  script JSON immediately, then fail if the expected change is not visible.
- Rollback: if updating `AppSettings.json` fails after writing a new script
  JSON, the script JSON is removed.
- Restore validation: before writing anything, `restore` checks that the zip
  contains a valid `AppSettings.json`, that every GUID matches `[A-Za-z0-9._-]+`,
  that no unexpected paths are present, and that each script's embedded GUID
  matches the filename. Replace mode clears `Texts/` atomically before writing.

## Data locations

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Elgato/CameraHub/` |
| Windows | `%APPDATA%\Elgato\CameraHub\` |

## Running tests

```
python3 -m pytest tests/ -v
```

89 tests cover import, export, push/pull aliases, CRUD, backup/restore,
Markdown stripping, atomic-write rollback, post-write verification,
diagnostics, fixture compatibility, base-directory overrides, simulated
overwrite failures, and restore validation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
