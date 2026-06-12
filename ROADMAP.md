# Roadmap

PrompterKit is feature-complete as of 1.0.0. No further feature development
is planned. The 1.0.1 line is limited to maintenance hardening of the
final-release safety claims.

Elgato Camera Hub has absorbed much of what this tool was built for: script
rename and drag-to-reorder arrived in Camera Hub 1.9, and auto-save in 2.0.
PrompterKit remains useful for what Camera Hub still does not offer: plain
text and Markdown import/export with round-trip fidelity, zip backup and
restore, and CLI automation.

## What 1.0.0 guarantees

- A schema guard refuses every write if a future Camera Hub update changes
  the on-disk format, so an unmaintained PrompterKit cannot corrupt a library
  it no longer understands. Read-only operations keep working.
- Every write is preceded by an automatic snapshot to `PrompterKitBackups/`
  inside the Camera Hub data directory, reversible with `restore`.
- The complete file format is documented in
  [ARCHITECTURE.md](ARCHITECTURE.md) so anyone can fork and continue.

## What 1.0.1 tightens

- Mutating commands run the schema guard before resolving, sorting, or editing
  scripts, so schema drift is reported as a clear refusal before command
  resolution touches drifted metadata.
- `restore --merge` rolls back script JSON files if the final
  `AppSettings.json` write fails.

## Dropped plans

The earlier roadmap item for a standalone double-click app (PyInstaller
bundle, code signing, notarization, auto-update) is dropped. Signed binaries
rot without maintenance; the Python source plus the AI-assisted install path
age better.

## If you need more

Fork it. The format reference in ARCHITECTURE.md plus the test suite in
`tests/` is everything required to keep going. License is MIT.
