from __future__ import annotations

import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

__all__ = [
    "Skill",
    "agent_respond",
    "build_agent_system_prompt",
    "discover_skills",
    "execute_tool",
    "parse_tool_call",
    "TOOL_DEFINITIONS",
]


MAX_TOOL_RESULT = 16000
MAX_SKILL_CHARS = 12000


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    instructions: str
    path: str


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and folders inside the selected workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative folder path"},
                    "recursive": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file inside the selected workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path"},
                    "start_line": {"type": "integer", "minimum": 1},
                    "max_lines": {"type": "integer", "minimum": 1, "maximum": 400},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search text files inside the selected workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text to find"},
                    "path": {"type": "string", "description": "Relative folder path"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression without running code.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
]


def _skill_roots(app_dir: str) -> list[Path]:
    roots = [Path(app_dir) / "skills"]
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        bundled = Path(bundle_root) / "skills"
        if bundled not in roots:
            roots.append(bundled)
    return roots


def discover_skills(app_dir: str) -> list[Skill]:
    """Load sidecar and bundled SKILL.md files, preferring sidecar overrides."""
    found: dict[str, Skill] = {}
    for root in reversed(_skill_roots(app_dir)):
        if not root.is_dir():
            continue
        for skill_path in sorted(root.glob("*/SKILL.md")):
            try:
                raw = skill_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            metadata: dict[str, str] = {}
            instructions = raw
            frontmatter = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
            if frontmatter:
                instructions = frontmatter.group(2)
                for line in frontmatter.group(1).splitlines():
                    key, separator, value = line.partition(":")
                    if separator:
                        metadata[key.strip().lower()] = value.strip().strip("\"'")
            name = metadata.get("name") or skill_path.parent.name
            description = metadata.get("description") or "Local assistant instructions"
            found[name.casefold()] = Skill(
                name=name,
                description=description,
                instructions=instructions[:MAX_SKILL_CHARS].strip(),
                path=str(skill_path),
            )
    return sorted(found.values(), key=lambda skill: skill.name.casefold())


def _resolve_workspace_path(workspace: str, requested: str, *, require_file: bool = False) -> Path:
    root = Path(workspace).resolve()
    candidate = (root / (requested or ".")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("The requested path is outside the selected workspace.") from exc
    if require_file and not candidate.is_file():
        raise FileNotFoundError(f"File not found: {requested}")
    return candidate


def _list_files(workspace: str, arguments: dict[str, Any]) -> str:
    requested = str(arguments.get("path", "."))
    folder = _resolve_workspace_path(workspace, requested)
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {requested}")
    recursive = bool(arguments.get("recursive", False))
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    root = Path(workspace).resolve()
    entries = []
    for path in iterator:
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        suffix = "/" if path.is_dir() else ""
        entries.append(path.relative_to(root).as_posix() + suffix)
        if len(entries) >= 200:
            entries.append("[results limited to 200 entries]")
            break
    return "\n".join(entries) if entries else "[folder is empty]"


def _read_file(workspace: str, arguments: dict[str, Any]) -> str:
    requested = str(arguments.get("path", ""))
    path = _resolve_workspace_path(workspace, requested, require_file=True)
    if path.stat().st_size > 2_000_000:
        raise ValueError("File is larger than the 2 MB text-reading limit.")
    start = max(1, int(arguments.get("start_line", 1)))
    count = max(1, min(400, int(arguments.get("max_lines", 200))))
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[start - 1:start - 1 + count]
    return "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start)) \
        or "[no lines in requested range]"


def _search_text(workspace: str, arguments: dict[str, Any]) -> str:
    query = str(arguments.get("query", ""))
    if not query:
        raise ValueError("search_text requires a non-empty query.")
    requested = str(arguments.get("path", "."))
    folder = _resolve_workspace_path(workspace, requested)
    if not folder.is_dir():
        raise NotADirectoryError(f"Folder not found: {requested}")
    root = Path(workspace).resolve()
    matches = []
    files_seen = 0
    for path in folder.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        files_seen += 1
        if files_seen > 1000:
            break
        try:
            if path.stat().st_size > 1_000_000:
                continue
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            if query.casefold() in line.casefold():
                matches.append(f"{path.relative_to(root).as_posix()}:{line_number}: {line.strip()}")
                if len(matches) >= 50:
                    matches.append("[results limited to 50 matches]")
                    return "\n".join(matches)
    return "\n".join(matches) if matches else "[no matches]"


def _calculate(expression: str) -> int | float:
    operators: dict[type[ast.AST], Callable[..., Any]] = {
        ast.Add: lambda a, b: a + b,
        ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b,
        ast.Div: lambda a, b: a / b,
        ast.FloorDiv: lambda a, b: a // b,
        ast.Mod: lambda a, b: a % b,
        ast.Pow: lambda a, b: a ** b,
        ast.UAdd: lambda a: +a,
        ast.USub: lambda a: -a,
    }

    def evaluate(node: ast.AST, depth: int = 0) -> int | float:
        if depth > 20:
            raise ValueError("Expression is too complex.")
        if isinstance(node, ast.Expression):
            return evaluate(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operators:
            left = evaluate(node.left, depth + 1)
            right = evaluate(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponent is too large.")
            return operators[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in operators:
            return operators[type(node.op)](evaluate(node.operand, depth + 1))
        raise ValueError("Only numeric arithmetic is supported.")

    return evaluate(ast.parse(expression, mode="eval"))


def execute_tool(name: str, arguments: dict[str, Any], workspace: str) -> str:
    """Execute one read-only built-in tool and return a model-safe result."""
    try:
        if name == "list_files":
            result = _list_files(workspace, arguments)
        elif name == "read_file":
            result = _read_file(workspace, arguments)
        elif name == "search_text":
            result = _search_text(workspace, arguments)
        elif name == "calculator":
            result = str(_calculate(str(arguments.get("expression", ""))))
        else:
            return f"Tool error: unknown tool {name!r}."
        return result[:MAX_TOOL_RESULT]
    except Exception as exc:
        return f"Tool error: {exc}"


def parse_tool_call(output: str) -> tuple[str, dict[str, Any]] | None:
    stripped = output.strip()
    native = re.search(
        r"<ifm\|tool_call>\s*([^\r\n<]+)\s*(.*?)</ifm\|tool_call>",
        stripped,
        re.DOTALL,
    )
    if native:
        arguments: dict[str, Any] = {}
        for key, value in re.findall(
            r"<ifm\|arg_key>(.*?)</ifm\|arg_key>\s*"
            r"<ifm\|arg_value>(.*?)</ifm\|arg_value>",
            native.group(2),
            re.DOTALL,
        ):
            cleaned = value.strip()
            try:
                arguments[key.strip()] = json.loads(cleaned)
            except json.JSONDecodeError:
                arguments[key.strip()] = cleaned
        return native.group(1).strip(), arguments
    match = re.search(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", stripped, re.DOTALL)
    if not match:
        match = re.search(r"```(?:tool_call|json)\s*(\{.*?\})\s*```", stripped,
                          re.DOTALL | re.IGNORECASE)
    candidate = match.group(1) if match else stripped
    if not candidate.startswith("{"):
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    name = payload.get("name") or payload.get("tool")
    arguments = payload.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return None
    return name, arguments


def build_agent_system_prompt(base_prompt: str, skills: Sequence[Skill],
                              tools_enabled: bool) -> str:
    sections = [base_prompt.strip()]
    if skills:
        skill_text = "\n\n".join(
            f"### Skill: {skill.name}\n{skill.instructions}" for skill in skills
        )
        sections.append("Follow these enabled local skills when relevant:\n\n" + skill_text)
    if tools_enabled:
        sections.append(
            "You can use local read-only tools. When a tool is needed, reply with ONLY "
            "<tool_call>{\"name\":\"tool_name\",\"arguments\":{...}}</tool_call>. "
            "Do not invent tool results. After receiving a <tool_result>, answer the user's "
            "request or make another tool call. Available tools:\n" +
            json.dumps(TOOL_DEFINITIONS, ensure_ascii=False)
        )
    return "\n\n".join(section for section in sections if section)


def _looks_like_tool_prefix(text: str) -> bool:
    stripped = text.lstrip()
    prefixes = ("<tool_call>", "<ifm|tool_calls>", "<ifm|tool_call>",
                "```tool_call", "```json", "{")
    return any(prefix.startswith(stripped) or stripped.startswith(prefix) for prefix in prefixes)


def agent_respond(
    message: str,
    history: list[tuple[str, str]],
    *,
    model: str,
    system_message: str,
    workspace: str,
    skills: Sequence[Skill],
    tools_enabled: bool,
    respond_fn: Callable[..., Iterator[str]],
    max_tool_rounds: int = 6,
) -> Iterator[tuple[str, Any]]:
    """Stream a final answer while privately executing model-requested tools."""
    agent_prompt = build_agent_system_prompt(system_message, skills, tools_enabled)
    working_history = list(history)
    original_message = message
    current_message = message
    tool_results: list[str] = []
    tool_calls = 0
    for round_number in range(max_tool_rounds + 1):
        output = ""
        published = ""
        withholding = True
        if round_number:
            yield "replace", ""
        for full in respond_fn(current_message, working_history, model=model,
                               system_message=agent_prompt):
            output = full
            if withholding and _looks_like_tool_prefix(full):
                continue
            withholding = False
            delta = full[len(published):] if full.startswith(published) else full
            published = full
            if delta:
                yield "text", delta
        tool_call = parse_tool_call(output) if tools_enabled else None
        if not tool_call:
            if withholding and output:
                yield "text", output
            yield "done", {"text": output, "tool_calls": tool_calls}
            return
        name, arguments = tool_call
        tool_calls += 1
        yield "status", f"Using {name}…"
        result = execute_tool(name, arguments, workspace)
        tool_results.append(f"Tool {name} returned:\n{result}")
        current_message = (
            f"Original request:\n{original_message}\n\n"
            + "\n\n".join(tool_results)
            + "\n\nAnswer the original request using these real tool results. "
              "Use another tool only if more information is required."
        )
    final = "I stopped after too many consecutive tool calls."
    yield "replace", ""
    yield "text", final
    yield "done", {"text": final, "tool_calls": tool_calls}
