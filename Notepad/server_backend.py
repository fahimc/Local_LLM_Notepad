from __future__ import annotations

import atexit
import json
import os
import secrets
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Iterator, Sequence

from agent_runtime import (Skill, TOOL_DEFINITIONS, build_agent_system_prompt,
                           execute_tool)

__all__ = ["server_agent_respond", "server_available", "stop_server"]


_lock = threading.Lock()
_process: subprocess.Popen | None = None
_diagnostics: Any = None
_model_path: str | None = None
_base_url: str | None = None
_api_key: str | None = None


def _server_path() -> str | None:
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(os.path.join(bundle_root, "k2_runtime", "llama-server.exe"))
    source_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates.append(os.path.join(source_root, ".vendor", "llama.cpp-k2", "build",
                                   "bin", "Release", "llama-server.exe"))
    return next((path for path in candidates if os.path.isfile(path)), None)


def server_available() -> bool:
    return _server_path() is not None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(url: str, *, payload: dict[str, Any] | None = None,
             timeout: float = 600) -> Any:
    headers = {"Authorization": f"Bearer {_api_key}"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers),
                                  timeout=timeout)


def stop_server() -> None:
    global _process, _diagnostics, _model_path, _base_url, _api_key
    with _lock:
        if _process and _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
        if _diagnostics:
            _diagnostics.close()
        _process = None
        _diagnostics = None
        _model_path = None
        _base_url = None
        _api_key = None


atexit.register(stop_server)


def _ensure_server(model_path: str) -> str:
    global _process, _diagnostics, _model_path, _base_url, _api_key
    with _lock:
        if (_process and _process.poll() is None and _model_path == model_path
                and _base_url):
            return _base_url
        if _process and _process.poll() is None:
            _process.terminate()
            try:
                _process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _process.kill()
                _process.wait(timeout=5)
        if _diagnostics:
            _diagnostics.close()
        executable = _server_path()
        if not executable:
            raise RuntimeError("The bundled tool-calling server is not available.")
        port = _free_port()
        _base_url = f"http://127.0.0.1:{port}"
        _api_key = secrets.token_urlsafe(24)
        _diagnostics = tempfile.TemporaryFile()
        args = [
            executable, "-m", model_path, "--host", "127.0.0.1", "--port", str(port),
            "--ctx-size", "8192", "--threads", str(max(1, min(8, os.cpu_count() or 4))),
            "--parallel", "1", "--no-warmup", "--jinja", "--api-key", _api_key,
        ]
        if "k2-horizon" in os.path.basename(model_path).lower():
            args.extend(["--override-kv", "tokenizer.ggml.pre=str:qwen2"])
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        _process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=_diagnostics,
                                    stderr=_diagnostics, creationflags=creation_flags)
        _model_path = model_path
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if _process.poll() is not None:
                break
            try:
                with _request(_base_url + "/health", timeout=1):
                    return _base_url
            except (OSError, urllib.error.URLError):
                time.sleep(0.2)
        _diagnostics.seek(0)
        lines = _diagnostics.read().decode("utf-8", errors="replace").splitlines()
        detail = lines[-1] if lines else "server did not become ready"
        raise RuntimeError(f"Could not start local tool runtime: {detail}")


def _chat_stream(base_url: str, payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    with _request(base_url + "/v1/chat/completions", payload=payload) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            yield json.loads(data)


def server_agent_respond(
    message: str,
    history: list[tuple[str, str]],
    *,
    model: str,
    system_message: str,
    workspace: str,
    skills: Sequence[Skill],
    tools_enabled: bool,
    max_tool_rounds: int = 6,
) -> Iterator[tuple[str, Any]]:
    """Use llama-server's native roles, tool schemas, and streaming API."""
    base_url = _ensure_server(model)
    messages: list[dict[str, Any]] = [
        {"role": "system",
         "content": build_agent_system_prompt(system_message, skills, False)}
    ]
    for user_message, assistant_message in history:
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": assistant_message})
    messages.append({"role": "user", "content": message})
    tool_count = 0
    for round_number in range(max_tool_rounds + 1):
        payload: dict[str, Any] = {
            "model": "local",
            "messages": messages,
            "stream": True,
            "max_tokens": 2048,
            "temperature": 0.7,
        }
        if tools_enabled:
            payload["tools"] = TOOL_DEFINITIONS
            payload["tool_choice"] = "auto"
        content = ""
        calls: dict[int, dict[str, str]] = {}
        emitted = False
        for event in _chat_stream(base_url, payload):
            choice = (event.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            text = delta.get("content") or ""
            if text:
                content += text
                emitted = True
                yield "text", text
            for call_delta in delta.get("tool_calls") or []:
                index = int(call_delta.get("index", 0))
                call = calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                call["id"] += call_delta.get("id") or ""
                function = call_delta.get("function") or {}
                call["name"] += function.get("name") or ""
                call["arguments"] += function.get("arguments") or ""
        if not calls:
            yield "done", {"text": content, "tool_calls": tool_count}
            return
        if emitted:
            yield "replace", ""
        assistant_calls = []
        for index in sorted(calls):
            call = calls[index]
            call_id = call["id"] or f"local_call_{tool_count + 1}"
            try:
                arguments = json.loads(call["arguments"] or "{}")
            except json.JSONDecodeError:
                arguments = {}
            assistant_calls.append({
                "id": call_id,
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"]},
            })
            tool_count += 1
            yield "status", f"Using {call['name']}…"
            result = execute_tool(call["name"], arguments, workspace)
            messages.append({"role": "tool", "tool_call_id": call_id, "content": result})
        messages.insert(len(messages) - len(assistant_calls), {
            "role": "assistant", "content": content, "tool_calls": assistant_calls,
        })
        if round_number == max_tool_rounds:
            break
        yield "replace", ""
    final = "I stopped after too many consecutive tool calls."
    yield "text", final
    yield "done", {"text": final, "tool_calls": tool_count}
