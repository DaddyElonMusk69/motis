from __future__ import annotations

import importlib
import sys
from pathlib import Path


UPSTREAM_ROOT = Path(__file__).resolve().parents[1]
if str(UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_ROOT))

import run_agent as run_agent_module
import motis_constants
from agent.prompt_builder import build_context_files_prompt
from agent import motis_prompt
from motis_state import SessionDB
from tools.memory_tool import MemoryStore
from tools.file_tools import SEARCH_FILES_SCHEMA
from tools.session_search_tool import SESSION_SEARCH_SCHEMA
from tools.terminal_tool import TERMINAL_SCHEMA


def test_system_prompt_keeps_memory_session_and_skill_guidance_together() -> None:
    agent = run_agent_module.AIAgent.__new__(run_agent_module.AIAgent)
    agent.skip_context_files = True
    agent.valid_tool_names = {"skill_manage", "memory", "session_search"}
    agent._tool_use_enforcement = False
    agent.model = "demo-model"
    agent.provider = "custom"
    agent._memory_store = None
    agent._memory_enabled = True
    agent._user_profile_enabled = True
    agent._memory_manager = None
    agent.pass_session_id = False
    agent.session_id = None
    agent.platform = ""

    prompt = agent._build_system_prompt()

    assert "You have persistent memory across sessions." in prompt
    assert "use session_search to recall it" in prompt
    assert "After completing a complex task" in prompt
    assert "Do NOT inspect MEMORY.md, USER.md, state.db, or other files under ~/.motis" in prompt


def test_runtime_skips_internal_source_tree_agents_md() -> None:
    package_root = Path(__file__).resolve().parents[1]
    assert (package_root / "AGENTS.md").exists()

    prompt = build_context_files_prompt(cwd=str(package_root), skip_soul=True)

    assert prompt == ""


def test_memory_store_rejects_session_meta_memory(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "motis-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    store = MemoryStore(db_path=tmp_path / "state.db")
    result = store.add(
        "user",
        'User asked "do you remember me?" - first interaction in this session.',
    )

    assert result["success"] is False
    assert "durable facts" in result["error"]


def test_memory_store_accepts_durable_user_fact(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "motis-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    store = MemoryStore(db_path=tmp_path / "state.db")
    result = store.add(
        "user",
        "User is a gold trader and mainly uses Chan theory analysis.",
    )

    assert result["success"] is True
    assert result["entries"] == ["User is a gold trader and mainly uses Chan theory analysis."]


def test_memory_store_load_filters_existing_session_meta(monkeypatch, tmp_path: Path) -> None:
    home = tmp_path / "motis-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))

    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    db.replace_memory_entries(
        "cli-default",
        "user",
        ['User asked "do you remember me?" - first interaction in this session.'],
        source="cli",
    )

    store = MemoryStore(db_path=db_path)
    store.load_from_disk()

    assert store.user_entries == []
    assert store.format_for_system_prompt("user") is None


def test_motis_memory_guidance_discourages_filesystem_recall() -> None:
    guidance = motis_prompt.MEMORY_AND_SESSION_GUIDANCE

    assert "do not inspect MEMORY.md, USER.md, state.db, or other files under ~/.motis" in guidance
    assert 'If the user asks "do you remember me?"' in guidance


def test_tool_schemas_discourage_filesystem_recall_for_memory_questions() -> None:
    assert "Do NOT inspect MEMORY.md, USER.md, state.db, or other files under ~/.motis" in SESSION_SEARCH_SCHEMA["description"]
    assert "Do NOT use this to inspect Motis memory storage" in SEARCH_FILES_SCHEMA["description"]
    assert "state.db, ~/.motis" in SEARCH_FILES_SCHEMA["description"]
    assert "Do NOT use terminal to inspect Motis memory storage" in TERMINAL_SCHEMA["description"]
    assert "state.db, ~/.motis" in TERMINAL_SCHEMA["description"]


def test_get_motis_home_defaults_to_motis(monkeypatch) -> None:
    monkeypatch.delenv("MOTIS_HOME", raising=False)
    monkeypatch.delenv("HERMES_HOME", raising=False)
    reloaded = importlib.reload(motis_constants)

    assert reloaded.get_motis_home() == Path.home() / ".motis"
    assert reloaded.get_hermes_home() == Path.home() / ".motis"


def test_get_motis_home_prefers_motis_env_over_compat_env(monkeypatch) -> None:
    monkeypatch.setenv("MOTIS_HOME", "/tmp/motis-home")
    monkeypatch.setenv("HERMES_HOME", "/tmp/hermes-home")
    reloaded = importlib.reload(motis_constants)

    assert reloaded.get_motis_home() == Path("/tmp/motis-home")
    assert reloaded.get_hermes_home() == Path("/tmp/motis-home")
