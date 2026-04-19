# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Renamed project to PrompterKit. CLI module is now `prompter_kit.py` and GUI
  module is `prompter_kit_gui.py`. Repository moved to
  `snapsynapse/prompter-kit`; canonical site is https://prompterkit.app/.
  Any scripts or imports referencing the old `elgato_prompter_tools` module
  names must be updated.

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
