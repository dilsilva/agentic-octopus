from pathlib import Path

import pytest

from octo.registry import load_registry

REPO_AGENTS = Path(__file__).resolve().parents[2] / "agents"


def _write_agent(root: Path, name: str, manifest: str, prompt: str = "do things") -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "agent.yaml").write_text(manifest)
    (d / "prompt.md").write_text(prompt)
    return d


def test_loads_repo_exemplar():
    registry = load_registry(REPO_AGENTS)
    assert "research-brief" in registry
    a = registry["research-brief"]
    assert a.manifest.executor in {"claude-sdk", "openrouter"}
    assert a.manifest.requires_approval is False
    assert "WebSearch" in a.manifest.tools
    assert a.prompt.strip()


def test_name_must_match_directory(tmp_path):
    _write_agent(tmp_path, "dir-name", "name: other-name\n")
    with pytest.raises(ValueError, match="does not match directory"):
        load_registry(tmp_path)


def test_unknown_executor_rejected(tmp_path):
    _write_agent(tmp_path, "bad", "name: bad\nexecutor: gpt-magic\n")
    with pytest.raises(ValueError, match="unknown executor"):
        load_registry(tmp_path)


def test_invalid_cron_rejected(tmp_path):
    _write_agent(tmp_path, "bad", "name: bad\nschedule: 'not a cron'\n")
    with pytest.raises(ValueError, match="invalid cron"):
        load_registry(tmp_path)


def test_missing_prompt_rejected(tmp_path):
    d = tmp_path / "noprompt"
    d.mkdir()
    (d / "agent.yaml").write_text("name: noprompt\n")
    with pytest.raises(ValueError, match="missing prompt.md"):
        load_registry(tmp_path)


def test_empty_dir_is_empty_registry(tmp_path):
    assert load_registry(tmp_path / "nothing-here") == {}
