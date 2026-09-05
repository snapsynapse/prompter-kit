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
For a new guide, the manifest may name the next unpublished app release during
authoring. Prepare its copies explicitly (the current candidate is v1.0.3):
Literal
```sh
python3 scripts/check_agent_surfaces.py --prepare-release v1.0.3 --sync
```
This does not validate the release anchor. Commit the final guide and sidecars,
create the new tag on that commit, and run the strict check before pushing the
commit and tag for Pages deployment. Never move an existing tag. Publish the
release, then verify the live guide with the hosted GuideCheck verifier.
Level 4 is the guide-file target; Level 5 requires a separate enforcing runtime.

### DNS provenance
GuideCheck 0.7.1 accepts a DNS TXT hash anchor under an independent control
plane. Keep DNS credentials separate from website/repository credentials.
DNSSEC is recommended. A matching TXT record alone does not establish Level 4:
the served guide, manifest, release, and every discovered anchor must agree,
and the guide must pass the lower-level checks.

For guide 1.4.0 (8075 bytes), add one record in the prompterkit.app DNS zone:
- Type: TXT
- Host: `_assistant-guide` (full name: `_assistant-guide.prompterkit.app`)
- TTL: 300 seconds, or the provider's lowest supported value at most 3600
- Value: the single line below, without adding surrounding quotation marks
Literal
```text
v=1; sha256=1b73f93f9f466de6f7b5f69182535d10c65e37e1cdf4427efa15d8508dfe6558; url=https://prompterkit.app/.well-known/assistant-guide.txt
```
The 2026-09-05 lookup returned NXDOMAIN for this record. Recheck before editing;
replace an existing GuideCheck value rather than leaving conflicting hashes.
This hash covers assistant-guide.txt bytes, not the manifest or source archive.

Adding the new hash before deployment temporarily disagrees with the old live
guide. Do not claim Level 4 during that transition. Freeze the guide bytes after
DNS entry; further guide edits require recomputing the hash and updating DNS.
After the operator confirms DNS, complete the separately authorized v1.0.3
commit/tag/release sequence above. Then check DNS propagation and byte identity
of all live surfaces, and submit the canonical guide URL to the hosted verifier.
Record verifier version, timestamp, guide hash, achieved level, and findings.
Level 4 with zero blocking findings is the closeout gate. Disclose remaining
warnings and that the hosted verifier does not establish runtime Level 5 or safety.

## Questions

Use issues or discussions with the same best-effort expectations. Include
versions and a minimal sanitized reproduction; never post private scripts,
settings files, or backup archives.
