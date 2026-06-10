# INTENT

Scope: this repo only (PrompterKit, Snap Synapse portfolio). Not in
portfolio.yaml (PAICE federation only by 2026-06-09 scope decision).

## Status: maintenance mode (decided 2026-06-09)

PrompterKit 1.0.0 is the final feature release. No further development is
planned. Security reports against 1.0.x are still reviewed and fixed (see
SECURITY.md).

## Why

Elgato Camera Hub absorbed much of the original need: script rename and
drag-to-reorder (Camera Hub 1.9), auto-save (2.0). What PrompterKit still
uniquely provides is narrow and stable: plain text / Markdown import-export
with round-trip fidelity, zip backup/restore, and CLI automation. That
remaining surface does not justify ongoing maintenance.

## How 1.0.0 makes unmaintained operation safe

- Schema guard: every write validates the on-disk Camera Hub format against
  the documented shape and refuses on drift. A future Camera Hub format
  change degrades PrompterKit to read-only instead of corrupting libraries.
- Automatic pre-write snapshots to `PrompterKitBackups/` (newest 20 kept),
  so every write is reversible with `restore`.
- Complete file format reference in ARCHITECTURE.md, so the project can be
  forked without reverse-engineering.
- Flask pinned exactly (3.1.3) for reproducible installs.

## What was deliberately dropped

The standalone double-click app (PyInstaller bundle, code signing,
notarization, auto-update) from the old roadmap. Signed binaries rot without
maintenance; source plus the AI-assisted install path age better.

## What would reopen development

Only a security report against 1.0.x, or Camera Hub shipping native txt/md
import-export AND backup (at which point archive the repo rather than
extend it). Schema-guard refusals reported by users are working as designed,
not bugs to fix: the documented response is "use export/backup, or fork".

## Exceptions to Repo Standards

None recorded.

## Changelog

- 2026-06-09: File created at 1.0.0 release to record the maintenance-mode
  decision. Release: https://github.com/snapsynapse/prompter-kit/releases/tag/v1.0.0
