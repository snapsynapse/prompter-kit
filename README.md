# elgato-prompter-tools

Command-line tool for importing and exporting scripts with [Elgato Prompter](https://www.elgato.com/uk/en/s/welcome-to-prompter) (Camera Hub).

Forked from [spieldbergo/elgato_prompter_text_importer](https://github.com/spieldbergo/elgato_prompter_text_importer) with a full rewrite and added export support.

## What it does

- **Import** a plain `.txt` file (one chapter per line) as a Prompter script
- **Export** any registered script back to `.txt`
- **List** all scripts registered in Camera Hub
- **Export all** scripts at once to a directory

Works on macOS and Windows.

## Requirements

- Python 3.10+
- Elgato Camera Hub installed (so the data directories exist)

## Usage

Close Camera Hub before running any command.

### Import

```
python3 elgato_prompter_tools.py import script.txt --name "My Script" --index 0
```

`--index` controls sort order in Prompter (default: 0).

### List registered scripts

```
python3 elgato_prompter_tools.py export --list
```

### Export a single script

By name:
```
python3 elgato_prompter_tools.py export --name "My Script" --output my_script.txt
```

By GUID:
```
python3 elgato_prompter_tools.py export --guid <GUID> --output my_script.txt
```

### Export all scripts

```
python3 elgato_prompter_tools.py export --all --output ./exported/
```

Filenames are derived from the friendly name. Collisions are resolved automatically.

## Script format

Plain `.txt` file. Each non-empty line becomes one chapter in Prompter.

```
This is chapter one.
This is chapter two.
This is chapter three.
```

## Running tests

```
python3 -m pytest tests/ -v
```

## Data locations

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Elgato/CameraHub/` |
| Windows | `%APPDATA%\Elgato\CameraHub\` |

## License

MIT
