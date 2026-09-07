from __future__ import annotations

import os
import typing
from typing import List, Tuple
from typing_extensions import OrderedDict

# llama-cpp-python 0.1.85 imports OrderedDict from typing. Some Python 3.7
# distributions do not expose that alias even though the package supports 3.7.
if not hasattr(typing, "OrderedDict"):
    typing.OrderedDict = OrderedDict

from llama_cpp import Llama

__all__ = [
    "respond",
]

_llm: Llama | None = None
_llm_model_path: str | None = None


def _lazy_load_model(model_path: str) -> Llama:
    """Load (or return cached) GGUF model from *model_path*."""
    global _llm, _llm_model_path

    if _llm and _llm_model_path == model_path:
        return _llm

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}")

    _llm = Llama(
        model_path=model_path,
        flash_attn=False,
        n_gpu_layers=0,
        n_batch=8,
        n_ctx=102_400,
        n_threads=8,
        n_threads_batch=8,
    )
    _llm_model_path = model_path
    return _llm


# ───────────────────────────────── respond() ────────────────────────────────

def respond(
    message: str,
    history: List[Tuple[str, str]],
    *,
    model: str | None = None,
    system_message: str = "You are a helpful assistant.",
    max_tokens: int = 102_400,
    temperature: float = 0.7,
    top_p: float = 0.95,
    top_k: int = 40,
    repeat_penalty: float = 1.1,
):

    model_path = (
        model
        or "gemma-3-1b-it-Q4_K_M.gguf"  # default
    )

    llm = _lazy_load_model(model_path)
    messages = [{"role": "system", "content": system_message}]
    for user_msg, assistant_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
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
    try:
        for chunk in stream:
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            full += delta
            yield full
    except Exception as exc:
        yield f"[Error] {exc}\n"
