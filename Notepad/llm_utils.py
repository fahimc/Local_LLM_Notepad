from __future__ import annotations

import codecs
import os
import subprocess
import sys
import tempfile
from typing import Any, Iterator, List, Tuple

__all__ = ["respond"]


_llm: Any = None
_llm_model_path: str | None = None


def _bundled_cli_path() -> str | None:
    """Return the K2-capable llama.cpp CLI from a bundle or dev checkout."""
    candidates = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(os.path.join(bundle_root, "k2_runtime", "llama-completion.exe"))

    source_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates.append(
        os.path.join(
            source_root,
            ".vendor",
            "llama.cpp-k2",
            "build",
            "bin",
            "Release",
            "llama-completion.exe",
        )
    )
    return next((path for path in candidates if os.path.isfile(path)), None)


def _conversation_prompt(message: str, history: List[Tuple[str, str]]) -> str:
    if not history:
        return message
    turns = []
    for user_message, assistant_message in history:
        turns.append(f"User: {user_message}\nAssistant: {assistant_message}")
    turns.append(f"User: {message}")
    return "Continue the conversation below. Respond to the final user message.\n\n" + "\n\n".join(turns)


def _clean_cli_output(output: str) -> str:
    # K2-Horizon emits its private reasoning before this marker. Keep the UI
    # focused on the final assistant answer, matching ordinary chat clients.
    if "</ifm|think>" in output:
        output = output.split("</ifm|think>", 1)[1]
    for marker in (
        "[end of text]",
        "<|endoftext|>",
        "<|ifm|im_end|>",
        "<|eot_id|>",
    ):
        output = output.replace(marker, "")
    return output.strip()


def _respond_via_cli(
    cli_path: str,
    message: str,
    history: List[Tuple[str, str]],
    *,
    model_path: str,
    system_message: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int,
    repeat_penalty: float,
) -> Iterator[str]:
    prompt_path = ""
    process: subprocess.Popen | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", delete=False
        ) as prompt_file:
            prompt_file.write(_conversation_prompt(message, history))
            prompt_path = prompt_file.name

        args = [
            cli_path,
            "-m", model_path,
            "--jinja",
            "--conversation",
            "--single-turn",
            "--system-prompt", system_message,
            "--file", prompt_path,
            "--predict", str(max_tokens),
            "--ctx-size", "8192",
            "--threads", str(max(1, min(8, os.cpu_count() or 4))),
            "--simple-io",
            "--no-display-prompt",
            "--no-warmup",
            "--temperature", str(temperature),
            "--top-p", str(top_p),
            "--top-k", str(top_k),
            "--repeat-penalty", str(repeat_penalty),
        ]
        if "k2-horizon" in os.path.basename(model_path).lower():
            # The preview K2 GGUF tokenizer regex is not accepted by MSVC's
            # regex implementation. The model team's compatible workaround is
            # to use the equivalent Qwen2 pre-tokenizer.
            args[3:3] = ["--override-kv", "tokenizer.ggml.pre=str:qwen2"]
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with tempfile.TemporaryFile() as error_file:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=error_file,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            is_k2 = "k2-horizon" in os.path.basename(model_path).lower()
            think_marker = "</ifm|think>"
            end_markers = (
                "[end of text]",
                "<|endoftext|>",
                "<|ifm|im_end|>",
                "<|eot_id|>",
            )
            raw_text = ""
            pending = ""
            answer = ""
            answer_started = not is_k2
            stopped_at_marker = False
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            def flush_safe_text() -> Iterator[str]:
                nonlocal pending, answer, stopped_at_marker
                marker_positions = [
                    (pending.find(marker), marker)
                    for marker in end_markers
                    if marker in pending
                ]
                if marker_positions:
                    position, _marker = min(marker_positions, key=lambda item: item[0])
                    safe = pending[:position]
                    pending = ""
                    stopped_at_marker = True
                else:
                    held = 0
                    for marker in end_markers:
                        for size in range(1, min(len(marker), len(pending)) + 1):
                            if pending.endswith(marker[:size]):
                                held = max(held, size)
                    safe = pending[:-held] if held else pending
                    pending = pending[-held:] if held else ""
                if safe:
                    if not answer:
                        safe = safe.lstrip()
                    if safe:
                        answer += safe
                        yield answer

            if process.stdout:
                while not stopped_at_marker:
                    chunk = process.stdout.read(1)
                    if not chunk:
                        break
                    character = decoder.decode(chunk)
                    if not character:
                        continue
                    if not answer_started:
                        raw_text += character
                        if think_marker in raw_text:
                            answer_started = True
                            pending += raw_text.split(think_marker, 1)[1]
                            raw_text = ""
                        elif len(raw_text) > len(think_marker):
                            raw_text = raw_text[-len(think_marker):]
                        else:
                            continue
                    else:
                        pending += character
                    yield from flush_safe_text()

            if answer_started and pending and not stopped_at_marker:
                cleaned_tail = _clean_cli_output(pending)
                if cleaned_tail:
                    answer += cleaned_tail
                    yield answer
            return_code = process.wait()
            error_file.seek(0)
            diagnostics = error_file.read().decode("utf-8", errors="replace")

        if return_code != 0:
            useful_lines = [line.strip() for line in diagnostics.splitlines() if line.strip()]
            detail = useful_lines[-1] if useful_lines else f"runtime exited with code {return_code}"
            raise RuntimeError(detail)
        if not answer and raw_text:
            answer = _clean_cli_output(raw_text)
            if answer:
                yield answer
        if not answer:
            raise RuntimeError("The model completed without returning an answer.")
    finally:
        if process and process.poll() is None:
            process.terminate()
        if prompt_path:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass


def _lazy_load_python_model(model_path: str):
    global _llm, _llm_model_path
    from llama_cpp import Llama

    if _llm and _llm_model_path == model_path:
        return _llm
    _llm = Llama(
        model_path=model_path,
        flash_attn=False,
        n_gpu_layers=0,
        n_batch=128,
        n_ctx=8192,
        n_threads=max(1, min(8, os.cpu_count() or 4)),
        n_threads_batch=max(1, min(8, os.cpu_count() or 4)),
    )
    _llm_model_path = model_path
    return _llm


def _respond_via_python(
    message: str,
    history: List[Tuple[str, str]],
    *,
    model_path: str,
    system_message: str,
    max_tokens: int,
    temperature: float,
    top_p: float,
    top_k: int,
    repeat_penalty: float,
) -> Iterator[str]:
    llm = _lazy_load_python_model(model_path)
    messages = [{"role": "system", "content": system_message}]
    for user_message, assistant_message in history:
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": assistant_message})
    messages.append({"role": "user", "content": message})
    stream = llm.create_chat_completion(
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repeat_penalty=repeat_penalty,
        stream=True,
    )
    full = ""
    for chunk in stream:
        full += chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
        yield full


def respond(
    message: str,
    history: List[Tuple[str, str]],
    *,
    model: str | None = None,
    system_message: str = "You are a helpful assistant.",
    max_tokens: int = 2048,
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
):
    model_path = model or "gemma-3-1b-it-Q4_K_M.gguf"
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    options = dict(
        model_path=model_path,
        system_message=system_message,
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        repeat_penalty=repeat_penalty,
    )
    cli_path = _bundled_cli_path()
    if cli_path:
        yield from _respond_via_cli(cli_path, message, history, **options)
    else:
        yield from _respond_via_python(message, history, **options)
