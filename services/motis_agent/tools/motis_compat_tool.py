"""Compatibility aliases that preserve Motis-native tool naming."""

from __future__ import annotations

from tools.registry import registry
from tools.skills_tool import skill_view, skills_list
from tools.web_tools import WEB_EXTRACT_SCHEMA, _web_requires_env, check_web_api_key, web_extract_tool


LOAD_SKILL_SCHEMA = {
    "name": "load_skill",
    "description": "Compatibility alias for skill_view. Load a skill's SKILL.md or one supporting file within that skill.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Skill name such as macro-analysis, technical-basic, or operator-builder.",
            },
            "file_path": {
                "type": "string",
                "description": "Optional relative file path inside the skill directory.",
            },
        },
        "required": ["name"],
    },
}

LIST_SKILLS_SCHEMA = {
    "name": "list_skills",
    "description": "Compatibility alias for skills_list. Discover skills before loading one in full.",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Optional category filter such as finance or builtin.",
            },
        },
    },
}

READ_URL_SCHEMA = {
    "name": "read_url",
    "description": "Compatibility alias for web_extract. Read one public URL and return normalized page content.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Public URL to read.",
            },
        },
        "required": ["url"],
    },
}


registry.register(
    name="load_skill",
    toolset="skills",
    schema=LOAD_SKILL_SCHEMA,
    handler=lambda args, **kw: skill_view(
        args.get("name", ""),
        args.get("file_path"),
        task_id=kw.get("task_id"),
    ),
    emoji="📘",
)

registry.register(
    name="list_skills",
    toolset="skills",
    schema=LIST_SKILLS_SCHEMA,
    handler=lambda args, **kw: skills_list(
        category=args.get("category"),
        task_id=kw.get("task_id"),
    ),
    emoji="🧰",
)

registry.register(
    name="read_url",
    toolset="web",
    schema=READ_URL_SCHEMA,
    handler=lambda args, **kw: web_extract_tool(
        [args.get("url", "")] if args.get("url") else [],
        format="markdown",
        use_llm_processing=True,
        session_id=kw.get("session_id"),
    ),
    check_fn=check_web_api_key,
    requires_env=_web_requires_env(),
    is_async=True,
    emoji="📄",
    max_result_size_chars=100_000,
)

registry.register(
    name="web_fetch",
    toolset="web",
    schema={**READ_URL_SCHEMA, "name": "web_fetch", "description": "Compatibility alias for read_url."},
    handler=lambda args, **kw: web_extract_tool(
        [args.get("url", "")] if args.get("url") else [],
        format="markdown",
        use_llm_processing=True,
        session_id=kw.get("session_id"),
    ),
    check_fn=check_web_api_key,
    requires_env=_web_requires_env(),
    is_async=True,
    emoji="📄",
    max_result_size_chars=100_000,
)
