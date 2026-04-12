"""Filesystem-backed operator registry for the Motis runtime."""

from __future__ import annotations

from contextlib import contextmanager
import importlib.util
import logging
from pathlib import Path
import sys
from types import ModuleType
from typing import Any

from motis_constants import get_hermes_home

logger = logging.getLogger(__name__)

_BUNDLED_OPERATORS_ROOT = Path(__file__).resolve().parents[1] / "operators"
_USER_OPERATORS_ROOT = get_hermes_home() / "operators"
_REQUIRED_EXPORTS = ("STATE", "MANIFEST", "build_graph")


class _UnavailableCompiledGraph:
    """Placeholder compiled graph when the operator runtime is not installed."""

    def __init__(self, dependency: str) -> None:
        self.dependency = dependency

    async def ainvoke(self, _state: dict[str, Any] | None = None) -> dict[str, Any]:
        raise RuntimeError(
            f"Operator runtime dependency '{self.dependency}' is not installed. "
            "Operator discovery works, but invocation needs the full runtime."
        )


class _ShimStateGraph:
    """Tiny shim so operator discovery still works without LangGraph."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def add_node(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def add_edge(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def add_conditional_edges(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set_entry_point(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def compile(self) -> _UnavailableCompiledGraph:
        return _UnavailableCompiledGraph("langgraph")


@contextmanager
def _temporary_operator_import_shims():
    """Install lightweight compatibility shims while importing operator modules."""
    installed_modules: list[str] = []

    def _register(name: str, module: ModuleType) -> None:
        if name in sys.modules:
            return
        sys.modules[name] = module
        installed_modules.append(name)

    def _spec_missing(module_name: str) -> bool:
        try:
            return importlib.util.find_spec(module_name) is None
        except ModuleNotFoundError:
            return True

    try:
        if _spec_missing("langgraph.graph"):
            langgraph_module = ModuleType("langgraph")
            langgraph_graph_module = ModuleType("langgraph.graph")
            langgraph_graph_module.StateGraph = _ShimStateGraph
            langgraph_graph_module.END = "__end__"
            langgraph_module.graph = langgraph_graph_module
            _register("langgraph", langgraph_module)
            _register("langgraph.graph", langgraph_graph_module)

        yield
    finally:
        for module_name in reversed(installed_modules):
            sys.modules.pop(module_name, None)


def _parse_operator_md(md_path: Path) -> dict[str, str]:
    """Extract operator discovery metadata from OPERATOR.md."""
    try:
        text = md_path.read_text(encoding="utf-8")
    except Exception:
        return {}

    result: dict[str, str] = {"description": text}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and "name" not in result:
            result["name"] = stripped[2:].strip()
        elif stripped.startswith("> ") and "summary" not in result:
            result["summary"] = stripped[2:].strip()
        if "name" in result and "summary" in result:
            break
    return result


def _load_module_from_path(filepath: Path) -> ModuleType | None:
    """Import an operator module from disk."""
    op_dir_name = filepath.parent.name
    category_name = filepath.parent.parent.name
    module_name = f"motis_runtime.operators.{category_name}.{op_dir_name}.operator"
    try:
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            logger.warning("Cannot build import spec for %s", filepath)
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        with _temporary_operator_import_shims():
            spec.loader.exec_module(module)
        return module
    except Exception as exc:
        sys.modules.pop(module_name, None)
        logger.error("Failed to load operator module %s: %s", filepath, exc, exc_info=True)
        return None


def _normalize_lookup(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _is_valid_operator_module(module: ModuleType) -> bool:
    return all(hasattr(module, attr) for attr in _REQUIRED_EXPORTS) and callable(
        getattr(module, "build_graph", None)
    )


class _LoadedOperator:
    """Thin wrapper around a loaded operator module."""

    __slots__ = ("module", "manifest", "operator_id", "source", "discovery", "path")

    def __init__(
        self,
        module: ModuleType,
        *,
        operator_id: str,
        source: str,
        discovery: dict[str, str] | None = None,
        path: str = "",
    ) -> None:
        self.module = module
        self.manifest = module.MANIFEST
        self.operator_id = operator_id
        self.source = source
        self.discovery = discovery or {}
        self.path = path

    def build_graph(self):
        return self.module.build_graph()

    @property
    def display_name(self) -> str:
        return self.discovery.get("name") or self.manifest.get("name", "unnamed")

    @property
    def summary(self) -> str:
        return self.discovery.get("summary", "")

    def to_summary_dict(self) -> dict[str, Any]:
        manifest = self.manifest
        return {
            "id": self.operator_id,
            "name": self.display_name,
            "summary": self.summary,
            "state": manifest.get("_runtime_state", "draft"),
            "operator_type": manifest.get("type", "unknown"),
            "asset_class": manifest.get("asset_class", ""),
            "exchange": manifest.get("exchange", ""),
            "asset_universe": manifest.get("asset_universe", []),
            "risk": manifest.get("risk", {}),
            "trigger": manifest.get("trigger", {}),
            "nodes": [node.get("name") for node in manifest.get("nodes", [])],
            "source": self.source,
        }

    def to_detail_dict(self) -> dict[str, Any]:
        detail = self.to_summary_dict()
        detail.update(
            {
                "success": True,
                "operator_id": self.operator_id,
                "path": self.path,
                "content": self.discovery.get("description") or self._fallback_content(),
            }
        )
        return detail

    def _fallback_content(self) -> str:
        manifest = self.manifest
        lines = [f"# {self.display_name}"]
        if self.summary:
            lines.extend(["", f"> {self.summary}"])
        lines.extend(
            [
                "",
                "## Metadata",
                f"- id: {self.operator_id}",
                f"- type: {manifest.get('type', 'unknown')}",
                f"- source: {self.source}",
            ]
        )
        return "\n".join(lines).strip()


class OperatorRegistry:
    """Single-user operator registry backed by bundled + user filesystem roots."""

    _CONTEXT_BLOCK_LIMIT = 10

    def __init__(self) -> None:
        self.user_root = _USER_OPERATORS_ROOT
        self.bundled_root = _BUNDLED_OPERATORS_ROOT
        self._operators: dict[str, _LoadedOperator] | None = None

    def _ensure_loaded(self) -> dict[str, _LoadedOperator]:
        if self._operators is not None:
            return self._operators

        self._operators = {}
        roots: list[tuple[Path, str]] = []
        try:
            self.user_root.mkdir(parents=True, exist_ok=True)
            roots.append((self.user_root, "user"))
        except OSError as exc:
            logger.warning("Operator registry could not initialize user operator root %s: %s", self.user_root, exc)

        roots.append((self.bundled_root, "bundled"))

        for root, source in roots:
            if root.is_dir():
                self._load_from_root(root, source=source)

        return self._operators

    def _load_from_root(self, operators_dir: Path, *, source: str) -> None:
        for category in ("examples", "builtin", "user"):
            category_dir = operators_dir / category
            if not category_dir.is_dir():
                continue

            for op_dir in sorted(category_dir.iterdir()):
                if not op_dir.is_dir() or op_dir.name.startswith(("_", ".")):
                    continue

                entry_point = op_dir / "operator.py"
                if not entry_point.exists():
                    continue

                op_id = f"{category}-{op_dir.name}"
                if op_id in self._operators:
                    continue

                md_path = op_dir / "OPERATOR.md"
                discovery = _parse_operator_md(md_path) if md_path.exists() else {}
                relative_path = (
                    str(md_path.relative_to(operators_dir))
                    if md_path.exists()
                    else str(entry_point.relative_to(operators_dir))
                )

                module = _load_module_from_path(entry_point)
                if module is None or not _is_valid_operator_module(module):
                    continue

                self._operators[op_id] = _LoadedOperator(
                    module=module,
                    operator_id=op_id,
                    source=source,
                    discovery=discovery,
                    path=relative_path,
                )

    def get(self, operator_id: str) -> dict[str, Any] | None:
        loaded = self._ensure_loaded().get(str(operator_id))
        return loaded.to_summary_dict() if loaded else None

    def list(
        self,
        *,
        state_filter: str | None = None,
        operator_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        results = [op.to_summary_dict() for op in self._ensure_loaded().values()]
        if state_filter and state_filter != "all":
            results = [item for item in results if item["state"] == state_filter]
        if operator_type:
            results = [item for item in results if item["operator_type"] == operator_type]
        return results[:limit]

    def get_loaded_operator(self, operator_id: str) -> _LoadedOperator | None:
        return self._ensure_loaded().get(operator_id)

    def load_operator(
        self,
        *,
        operator_id: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        requested_id = (operator_id or "").strip()
        requested_name = _normalize_lookup(name or "")

        if requested_id:
            loaded = self._ensure_loaded().get(requested_id)
            if loaded is not None:
                return loaded.to_detail_dict()

        if requested_name:
            for loaded in self._ensure_loaded().values():
                candidates = {
                    _normalize_lookup(loaded.operator_id),
                    _normalize_lookup(loaded.display_name),
                }
                if loaded.path:
                    parent = Path(loaded.path).parent
                    candidates.add(_normalize_lookup(parent.name))
                    candidates.add(_normalize_lookup(str(parent)))
                if requested_name in candidates:
                    return loaded.to_detail_dict()

        return {
            "success": False,
            "error": "Operator not found.",
            "available_operators": [item["id"] for item in self.list(limit=50)],
        }

    def update_state(self, operator_id: str, state: str) -> None:
        loaded = self._ensure_loaded().get(operator_id)
        if loaded:
            loaded.manifest["_runtime_state"] = state

    def create(self, spec: dict[str, Any]) -> str:
        graph_code = spec.get("graph_code", "").strip()
        if not graph_code:
            graph_code = self._stub_graph_code(spec)

        safe_name = _normalize_lookup(spec.get("name", "untitled"))
        op_dir = self.user_root / "user" / safe_name
        op_dir.mkdir(parents=True, exist_ok=True)

        operator_py = op_dir / "operator.py"
        operator_md = op_dir / "OPERATOR.md"
        operator_py.write_text(graph_code, encoding="utf-8")
        operator_md.write_text(
            spec.get("operator_markdown", "").strip() or self._stub_operator_markdown(spec, safe_name),
            encoding="utf-8",
        )

        self._operators = None
        self._ensure_loaded()
        return f"user-{safe_name}"

    def get_context_block(self) -> str:
        operators = self.list(limit=self._CONTEXT_BLOCK_LIMIT)
        if not operators:
            return ""

        lines = ["Available operators:"]
        for operator in operators:
            operator_id = operator.get("id", "")
            name = operator.get("name", "unnamed")
            summary = operator.get("summary", "")
            category = operator_id.split("-")[0] if "-" in operator_id else "operator"
            if summary:
                lines.append(f"  [{category}] {name} — {summary} (id: {operator_id})")
            else:
                lines.append(f"  [{category}] {name} (id: {operator_id})")
        return "\n".join(lines)

    def _stub_graph_code(self, spec: dict[str, Any]) -> str:
        name = spec.get("name", "Untitled Operator")
        operator_type = spec.get("type", "paper_trade")
        return (
            '"""\n'
            f"{name}\n"
            "Generated by the Motis operator tool. Replace the stubs with real logic.\n"
            '"""\n\n'
            "from __future__ import annotations\n\n"
            "from typing import TypedDict\n\n"
            "class State(TypedDict, total=False):\n"
            "    should_exit: bool\n"
            "    run_log: list[dict]\n\n"
            "STATE = State\n\n"
            "MANIFEST = {\n"
            f'    "name": {name!r},\n'
            f'    "type": {operator_type!r},\n'
            '    "nodes": [],\n'
            '    "reason_prompts": {},\n'
            '}\n\n'
            "async def _run(state: State) -> dict:\n"
            "    return {**state, 'should_exit': True, 'run_log': [{'level': 'info', 'message': 'stub operator'}]}\n\n"
            "def build_graph():\n"
            "    return _run\n"
        )

    def _stub_operator_markdown(self, spec: dict[str, Any], safe_name: str) -> str:
        name = spec.get("name", "Untitled Operator")
        operator_type = spec.get("type", "paper_trade")
        description = spec.get("description") or spec.get("summary") or (
            "Draft operator generated from a strategy specification."
        )
        return (
            f"# {name}\n\n"
            f"> {description}\n\n"
            "## Metadata\n"
            f"- id: user-{safe_name}\n"
            f"- type: {operator_type}\n"
            "- source: user\n"
        )


_OPERATOR_REGISTRY: OperatorRegistry | None = None


def get_operator_registry() -> OperatorRegistry:
    """Return the process-global operator registry singleton."""
    global _OPERATOR_REGISTRY
    if _OPERATOR_REGISTRY is None:
        _OPERATOR_REGISTRY = OperatorRegistry()
    return _OPERATOR_REGISTRY


def reset_operator_registry() -> None:
    """Clear the cached singleton (useful for tests or manual reloads)."""
    global _OPERATOR_REGISTRY
    _OPERATOR_REGISTRY = None
