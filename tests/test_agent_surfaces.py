import importlib.util
import ast
import hashlib
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("agent_surfaces", ROOT / "scripts/check_agent_surfaces.py")
surfaces = importlib.util.module_from_spec(spec)
spec.loader.exec_module(surfaces)


@pytest.fixture()
def guide_tree(tmp_path, monkeypatch):
    published = tmp_path / "docs" / ".well-known"
    published.mkdir(parents=True)
    for name in surfaces.FILES:
        shutil.copyfile(ROOT / name, tmp_path / name)
        shutil.copyfile(ROOT / name, published / name)
    original_guide = (tmp_path / surfaces.FILES[0]).read_bytes()
    monkeypatch.setattr(surfaces.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=original_guide))
    return tmp_path


@pytest.mark.parametrize("filename", surfaces.FILES)
def test_agent_check_detects_and_syncs_published_drift(guide_tree, filename):
    published = guide_tree / "docs" / ".well-known" / filename
    published.write_text("stale", encoding="ascii")
    with pytest.raises(ValueError, match="differs"):
        surfaces.check(guide_tree)
    surfaces.check(guide_tree, sync=True)
    assert published.read_bytes() == (guide_tree / filename).read_bytes()


@pytest.mark.parametrize("field", ["guide-sha256", "guide-bytes", "guide-version"])
def test_agent_sync_refuses_invalid_metadata(guide_tree, field):
    manifest = guide_tree / surfaces.FILES[1]
    lines = manifest.read_text().splitlines()
    manifest.write_text("\n".join(f"{field}: wrong" if l.startswith(field + ":") else l for l in lines) + "\n")
    published = guide_tree / "docs" / ".well-known" / manifest.name
    original = published.read_bytes()
    with pytest.raises(ValueError, match=field):
        surfaces.check(guide_tree, sync=True)
    assert published.read_bytes() == original


def test_agent_check_refuses_guide_not_in_release_tag(guide_tree, monkeypatch):
    monkeypatch.setattr(surfaces.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"older guide"))
    with pytest.raises(ValueError, match="Release tag"):
        surfaces.check(guide_tree)


def test_preparation_allows_only_explicit_missing_release(guide_tree, monkeypatch):
    def missing(*args, **kwargs):
        raise subprocess.CalledProcessError(128, args[0])
    monkeypatch.setattr(surfaces.subprocess, "run", missing)
    tag = surfaces.fields(guide_tree / surfaces.FILES[1])["immutable-release-url"].rsplit("/", 1)[1]
    with pytest.raises(subprocess.CalledProcessError):
        surfaces.check(guide_tree)
    surfaces.check(guide_tree, prepare_release=tag)
    with pytest.raises(ValueError, match="Preparation tag"):
        surfaces.check(guide_tree, prepare_release="v99.0.0")


def test_preparation_cannot_override_existing_different_guide(guide_tree, monkeypatch):
    monkeypatch.setattr(surfaces.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=b"older guide"))
    tag = surfaces.fields(guide_tree / surfaces.FILES[1])["immutable-release-url"].rsplit("/", 1)[1]
    with pytest.raises(ValueError, match="Release tag"):
        surfaces.check(guide_tree, prepare_release=tag)


def test_guide_binds_executed_scripts_and_local_imports():
    guide = (ROOT / "assistant-guide.txt").read_text(encoding="ascii")
    assert len(guide.encode("ascii")) <= 8192
    assert max(map(len, guide.splitlines())) <= 120
    actions = [dict(line.split(": ", 1) for line in block.strip().splitlines())
               for block in re.findall(r"\[action\]\n(.*?)\n\[/action\]", guide, re.S)]
    pinned = set()
    for action in actions:
        argv = shlex.split(action["command"])
        if argv[0] == ".venv/bin/python" and argv[1].endswith(".py"):
            path = ROOT / argv[1]
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert action["exec-sha256"] == digest
            assert f"{path.name}: {digest}" in guide
            pinned.add(path.name)
    assert pinned == {"prompter_kit.py", "prompter_kit_gui.py"}
    for name in pinned:
        for node in ast.walk(ast.parse((ROOT / name).read_text())):
            modules = ([node.module] if isinstance(node, ast.ImportFrom)
                       else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                if module and (ROOT / (module.split(".")[0] + ".py")).is_file():
                    assert module.split(".")[0] + ".py" in pinned
    clone = next(a for a in actions if a["id"] == "clone-repo")
    assert "--branch v1.0.2 --depth 1" in clone["command"]
    verify = next(a for a in actions if a["id"] == "verify-source")
    assert set(shlex.split(verify["command"])[3:]) == pinned
