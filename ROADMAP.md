# Roadmap

PrompterKit remains public and maintenance-only. No feature development or
Camera Hub compatibility tracking is planned. Security reports and contributions
receive best-effort review, without guaranteed response or fix timelines.
Forks are welcome. The retained scope is text conversion, library management,
registered-library backups, and CLI automation.

## Supported workflow and limits

- Normal mutations check known schema fields; restore bypasses the live guard.
  Future format changes can still break reads and writes.
- Automatic snapshots cover registered readable scripts and full settings,
  not the whole Camera Hub directory. Recovery is not guaranteed.
- The data shape and limits are documented in [ARCHITECTURE.md](ARCHITECTURE.md).
- The June 2026 macOS live eval passed without recording the Camera Hub version.
  Automated fixture tests do not establish compatibility with future releases.

## What 1.0.1 tightens

- Mutating commands run the schema guard before resolving, sorting, or editing
  scripts, so schema drift is reported as a clear refusal before command
  resolution touches drifted metadata.
- `restore --merge` rolls back script JSON files if the final
  `AppSettings.json` write fails.

## What 1.0.2 tightens

- Resolve export filename collisions and preserve literal .txt content.
- Align published agent-guide copies and check their hashes before deployment.
- Correct support, backup, conversion, and compatibility claims.

## Dropped plans

The earlier roadmap item for a standalone double-click app (PyInstaller
bundle, code signing, notarization, auto-update) is dropped. Signed binaries
rot without maintenance; the Python source plus the AI-assisted install path
age better.

## If you need more

Fork it. The format reference in ARCHITECTURE.md plus the test suite in
`tests/` is everything required to keep going. License is MIT.
