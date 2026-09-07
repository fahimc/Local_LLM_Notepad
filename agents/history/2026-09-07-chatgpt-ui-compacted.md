# ChatGPT-style local chat UI

## Purpose

Rework the portable Tkinter interface in `Notepad/chat_gui.py` into a ChatGPT-inspired local chat workspace.

## Completed

- Created and pushed fork `fahimc/Local_LLM_Notepad`.
- Added dark sidebar with New chat and selectable chat sessions.
- Added user message cards, assistant response cards, streaming updates, bottom composer, attachment chips, and local text-file attachment context.
- Added local session persistence beside the executable in `chat_sessions.json`; excluded it and Python caches from Git.
- Preserved model selection, system prompt editing, stop generation, JSON chat import/export, and portable local-runtime behavior.
- Made the model import lazy so the UI can launch when optional runtime dependencies are absent; generation reports the runtime error instead.
- Updated README feature documentation and shortcuts.
- Replaced the broken `llama_cpp_agent` dependency path with direct `llama-cpp-python` chat completion streaming.
- Pinned `llama-cpp-python==0.1.85` for compatibility with the original Python 3.7 portable-build environment and improved the missing-runtime message.
- Resized composer controls into consistent `Attach` and `Send` buttons.
- Installed `llama-cpp-python==0.1.85` in the active Python 3.7 environment and added a `typing.OrderedDict` compatibility shim required by that runtime on this Windows Python distribution.

## Verification

- `python -m py_compile Notepad/chat_gui.py Notepad/main.py Notepad/llm_utils.py` passes.
- `git diff --check` passes.
- `python Notepad/main.py` launched without a traceback in the available environment.
- Commit `34665ac` pushed to `git@github.com:fahimc/Local_LLM_Notepad.git` on `main`.
- Simulated `respond()` streaming test passes through the direct llama-cpp adapter.
- Latest fix commit `a135c88` pushed to `main`.
- Verified the real `llm_utils` import prints `llama runtime ready`, then relaunched the desktop app successfully.
- Built `Notepad/dist/Local_LLM_Notepad-portable.exe` with PyInstaller 5.13.2 as a one-file, no-console Windows executable (22,353,455 bytes; SHA-256 `CA718EC6C37FAC4A3D2F0D47652FFDE1196DB259F6B628F8A98F79EB80B13C7A`).
- Launched the compiled executable and verified a running `Local LLM Notepad` window/process.

## Known limitations / follow-ups

- Visual native-window automation was unavailable in the current desktop session, so verification was launch/smoke based rather than screenshot based.
- Attachments currently inject readable text files into the prompt; binary/image understanding is not implemented because the bundled default model is text-only.
- The legacy source-word highlighting, find, and zoom controls were removed from the redesigned primary UI and can be restored if needed.

## Resume point

Continue from commit `a135c88` in `Notepad/chat_gui.py`. Install `requirements.txt` and run the app with a GGUF model to validate streaming and attachment context end-to-end.
