"""Check published copies and metadata; this is not a GuideCheck verifier."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess


FILES = ("assistant-guide.txt", "assistant-guide-manifest.txt", "assistant-guide-transparency-log.txt")
ROOT = Path(__file__).resolve().parents[1]


def fields(path):
    result = {}
    content = path.read_text(encoding="ascii")
    if path.name == "assistant-guide.txt":
        content = content.split("[assistant-guide-metadata]", 1)[1].split("[/assistant-guide-metadata]", 1)[0]
    for line in content.splitlines():
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in result:
            raise ValueError(f"{path.name}: duplicate field {key}")
        result[key] = value
    return result


def check(root=ROOT, *, sync=False, prepare_release=None):
    guide = (root / FILES[0]).read_bytes()
    metadata = fields(root / FILES[0])
    manifest = fields(root / FILES[1])
    log = fields(root / FILES[2])
    digest = hashlib.sha256(guide).hexdigest()
    for key, expected in (("guide-version", metadata["guide-version"]),
                          ("guide-sha256", digest)):
        if manifest.get(key) != expected or log.get(key) != expected:
            raise ValueError(f"Manifest/log {key} does not match guide")
    if manifest.get("guide-bytes") != str(len(guide)):
        raise ValueError("Manifest guide-bytes does not match guide")
    canonical = "https://prompterkit.app/.well-known/assistant-guide.txt"
    if metadata.get("canonical-url") != canonical or log.get("canonical-url") != canonical:
        raise ValueError("Incorrect canonical guide URL")
    if manifest.get("guide-path") != "/.well-known/assistant-guide.txt":
        raise ValueError("Incorrect guide-path")
    anchor = manifest.get("immutable-release-url", "")
    prefix = "https://github.com/snapsynapse/prompter-kit/releases/tag/"
    if not anchor.startswith(prefix) or not re.fullmatch(r"v\d+\.\d+\.\d+", anchor[len(prefix):]):
        raise ValueError("Expected a semver release anchor")
    if anchor not in log.get("log-note", ""):
        raise ValueError("Log release anchor differs from manifest")
    tag = anchor[len(prefix):]
    if prepare_release is not None and prepare_release != tag:
        raise ValueError("Preparation tag differs from manifest")
    # Preparation is explicitly incomplete evidence, never a deployment gate.
    try:
        tagged = subprocess.run(["git", "show", f"{tag}:assistant-guide.txt"],
                                cwd=root, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        if prepare_release is None:
            raise
        tagged = None
    if tagged is not None and tagged != guide:
        raise ValueError("Release tag guide differs from current source")
    published = root / "docs" / ".well-known"
    if sync:
        published.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            shutil.copyfile(root / name, published / name)
    for name in FILES:
        if (root / name).read_bytes() != (published / name).read_bytes():
            raise ValueError(f"Published {name} differs; run with --sync")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sync", action="store_true", help="Copy validated root files to docs/.well-known")
    parser.add_argument("--prepare-release", metavar="TAG",
                        help="Allow an unavailable tag during authoring; not release verification")
    args = parser.parse_args()
    try:
        check(sync=args.sync, prepare_release=args.prepare_release)
    except (OSError, ValueError, KeyError, IndexError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Agent surfaces check failed: {error}\n")
    if args.prepare_release:
        print("Preparation only: copies and metadata match. Run strict checks after tagging; publication is unverified.")
    else:
        print("Agent copies, metadata, and local release-tag guide bytes match. Not a conformance certification.")
