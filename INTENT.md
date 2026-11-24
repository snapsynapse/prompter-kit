# INTENT

Scope: this repo only (PrompterKit, Snap Synapse portfolio). Not in
portfolio.yaml (PAICE federation only by 2026-06-09 scope decision).

## Status: maintenance mode (decided 2026-06-09)

PrompterKit 1.0.0 is the final feature release. No feature development or
Camera Hub compatibility tracking is planned. Security review is best-effort,
with no guaranteed response or remediation timeline (see SECURITY.md).

## Why

Elgato Camera Hub absorbed much of the original need: script rename and
drag-to-reorder (Camera Hub 1.9), auto-save (2.0). PrompterKit's retained scope
is text / Markdown conversion, registered-library backups, and CLI automation.
This does not justify an ongoing feature or compatibility roadmap.

## Safeguards and limits

- Normal mutations check known schema fields. Restore bypasses the live guard.
  Unknown formats can also break read operations; future compatibility is not
  guaranteed.
- Automatic registered-library snapshots have a retention limit of 20 and
  exclude missing, corrupt, and unregistered files. Recovery is not guaranteed.
- Complete file format reference in ARCHITECTURE.md, so the project can be
  forked without reverse-engineering.
- Flask has an exact direct dependency pin. Transitive dependencies are not
  locked; this is not a reproducible environment or a security guarantee.

## Post-1.0 safety patch

1.0.1 is a maintenance hardening patch, not a feature release. It preserves
the 1.0.0 maintenance-mode decision while tightening the final-release safety
claims: mutating commands now run schema checks before resolving or sorting
scripts, and merge-mode restore rolls back script files if settings cannot be
updated.

## What was deliberately dropped

The standalone double-click app (PyInstaller bundle, code signing,
notarization, auto-update) from the old roadmap. Signed binaries rot without
maintenance; source plus the AI-assisted install path age better.

## What would reopen development

Security reports may justify a discretionary patch. They do not automatically
reopen development. No active monitoring of manufacturer releases is planned.
Archive the repo if its remaining use no longer warrants keeping it active.
Schema refusals are a reason to stop writing, preserve an independent data copy,
and use compatible read tools or a maintained fork.

## September 2026 cleanup

1.0.2 fixes export filename collisions and preserves literal .txt input,
while keeping the repo public in maintenance-only state. Documentation and
agent surfaces reflect actual limitations and best-effort support. This is a
bounded cleanup, not a new feature roadmap.

## Final security patch (November 2026)

1.0.4 ships the 2026-11-22 security audit fixes: local GUI browser-origin
hardening, restore input limits, Windows absolute-path process calls, linear
Markdown stripping, CI tests before Pages deploy, SHA-pinned actions and
Dependabot. It is a patch, not a reopen. Unless a new security report arrives,
1.0.4 is the last planned release and the repo can be archived after it ships.

## Repository standards declaration

[repo-standards.yaml](repo-standards.yaml) records optional applicability,
source and delivery maps, and existing verification expectations. This INTENT
remains authoritative for purpose, maintenance boundaries and exceptions.
The declaration does not certify conformance or reopen feature development.
Guide 1.5.0, GuideCheck profile 2.0.0 and app 1.0.4 remain separate identities;
[CONTRIBUTING.md](CONTRIBUTING.md#agent-guide-publishing) retains the existing
publishing gates and hosted Level 4 target. AI Posture applicability and
owner-assigned levels remain unresolved.

## Exceptions to Repo Standards

None recorded.

## Changelog

- 2026-11-23: Recorded 1.0.4 as the final security patch, with guide 1.5.0,
  and the intent to archive once it ships.

- 2026-09-08: Added an optional repository standards declaration without
  changing maintenance scope, version identities or publishing gates.

- 2026-09-05: Clarified best-effort maintenance with no response or fix SLA;
  scoped 1.0.2 to data-fidelity fixes and documentation/publishing consistency.

- 2026-06-09: File created at 1.0.0 release to record the maintenance-mode
  decision. Release: https://github.com/snapsynapse/prompter-kit/releases/tag/v1.0.0
- 2026-06-12: Recorded 1.0.1 as a maintenance hardening patch, not a reopen
  of feature development. Published release:
  https://github.com/snapsynapse/prompter-kit/releases/tag/v1.0.1
