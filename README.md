# PrompterKit

Elgato Camera Hub stores your teleprompter scripts in opaque JSON files with no
official import or export path. This tool gives you a command line for getting
scripts in and out -- including from Markdown files.

Based on [spieldbergo/elgato_prompter_text_importer](https://github.com/spieldbergo/elgato_prompter_text_importer) (MIT).
Rewritten with export support, Markdown stripping, atomic writes, and a full test suite.

## Requirements

- Python 3.10+
- Elgato Camera Hub installed

Close Camera Hub before running any command.

## Quick start

```
# Import a script (plain text or Markdown)
python3 elgato_prompter_tools.py import script.txt --name "My Script"

# List registered scripts
python3 elgato_prompter_tools.py export --list

# Export one script by name
python3 elgato_prompter_tools.py export --name "My Script" --output my_script.txt

# Export everything
python3 elgato_prompter_tools.py export --all --output ./exported/
```

## Features

| Feature | Detail |
|---|---|
| Import | Reads `.txt` or `.md` files; one line per Prompter chapter |
| Markdown stripping | `#`, `*`, `_` and other formatting removed on import |
| Export by name | Match on friendly name, write to `.txt` |
| Export by GUID | Direct lookup, no name collision risk |
| Export all | Dumps every registered script to a directory |
| List | Tabular view of all registered scripts with GUIDs |
| Atomic writes | Temp-file-then-rename prevents corruption on interrupted writes |
| Rollback | Script JSON is removed if AppSettings update fails |
| Cross-platform | macOS and Windows paths handled automatically |

## Script format

Plain `.txt` or `.md` file. Each non-empty line becomes one chapter in Prompter.

```
This is chapter one.
This is chapter two.
This is chapter three.
```

Markdown headings, bold, italic, links, and list bullets are stripped automatically:

```markdown
# Act One

- Welcome to the show.
- **Tonight** we cover three topics.
```

imports as three plain chapters.

## Usage reference

### Import

```
python3 elgato_prompter_tools.py import <file> --name "Script Name" [--index N]
```

`--index` controls sort order in Prompter (default: 0).

### Export

```
python3 elgato_prompter_tools.py export --list
python3 elgato_prompter_tools.py export --name "Script Name" --output out.txt
python3 elgato_prompter_tools.py export --guid <GUID> --output out.txt
python3 elgato_prompter_tools.py export --all --output ./exported/
```

## Data locations

| Platform | Path |
|---|---|
| macOS | `~/Library/Application Support/Elgato/CameraHub/` |
| Windows | `%APPDATA%\Elgato\CameraHub\` |

## Running tests

```
python3 -m pytest tests/ -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
