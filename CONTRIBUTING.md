# Contributing

No new features or Camera Hub compatibility work is planned. Forks are welcome.
Bug reports, security reports, and contributions receive best-effort review;
there is no guaranteed response or merge timeline. See SECURITY.md for private
vulnerability reporting.

## Local setup

Python 3.10+ required. The CLI uses the standard library, but the full test
suite also imports Flask. On macOS or a POSIX shell:
Literal
```sh
git clone https://github.com/snapsynapse/prompter-kit.git
cd prompter-kit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-gui.txt pytest
python3 -m pytest tests/ -q
python3 scripts/check_agent_surfaces.py
```
On Windows, activate with `.venv\Scripts\activate` instead.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the codebase is organized.

## Making changes

- One logical change per PR.
- Add or update tests for any changed behavior.
- Update CHANGELOG.md under `[Unreleased]`.
- Run the test suite before submitting.

## Commit style

Short imperative subject line, e.g. `Add export-all collision fix`. No period.

## Agent-guide publishing

The root assistant-guide.txt, manifest, and transparency log are authoritative.
The matching docs/.well-known files are published copies. After a guide edit,
update the guide version, review date, hash, byte count, and log, then sync:
Literal
```sh
python3 scripts/check_agent_surfaces.py --sync
python3 scripts/check_agent_surfaces.py
```
The Pages job checks these before upload. This verifies local copy/metadata
consistency, not GuideCheck conformance or a remote release's availability.
Keep release anchors on an existing tag that contains the guide bytes; do not
point at a planned release. After publishing a new guide, coordinate the tag
and anchor update and verify the public URLs.

## Questions

Use issues or discussions with the same best-effort expectations. Include
versions and a minimal sanitized reproduction; never post private scripts,
settings files, or backup archives.
