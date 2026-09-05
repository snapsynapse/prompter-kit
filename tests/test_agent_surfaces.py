import importlib.util
from pathlib import Path
import shutil
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
