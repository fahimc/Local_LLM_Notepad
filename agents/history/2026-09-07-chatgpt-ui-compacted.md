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

## Verification

- `python -m py_compile Notepad/chat_gui.py Notepad/main.py Notepad/llm_utils.py` passes.
- `git diff --check` passes.
- `python Notepad/main.py` launched without a traceback in the available environment.
- Commit `34665ac` pushed to `git@github.com:fahimc/Local_LLM_Notepad.git` on `main`.

## Known limitations / follow-ups

- Visual native-window automation was unavailable in the current desktop session, so verification was launch/smoke based rather than screenshot based.
- Attachments currently inject readable text files into the prompt; binary/image understanding is not implemented because the bundled default model is text-only.
- The legacy source-word highlighting, find, and zoom controls were removed from the redesigned primary UI and can be restored if needed.

## Resume point

Continue from commit `34665ac` in `Notepad/chat_gui.py`. Install/build the existing runtime dependencies and run the app with a GGUF model to validate streaming and attachment context end-to-end.
