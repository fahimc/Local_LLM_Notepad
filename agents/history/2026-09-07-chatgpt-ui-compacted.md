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
- Migrated builds to Python 3.12 and `llama-cpp-python==0.3.35`; standard llama.cpp still cannot load the newly released K2-Horizon architecture.
- Built MBZUAI-IFM's `model/K2Horizon` llama.cpp branch at commit `35999d101` and embedded its CLI plus native DLLs in the one-file executable.
- Added a packaged CLI backend with chat-template handling, K2's Windows tokenizer workaround, reasoning-marker cleanup, conversation context, and a Python fallback for source environments.
- Added `--self-test MODEL OUTPUT_JSON` to the executable for deterministic packaged inference verification.
- Reworked the conversation surface to closely match the supplied ChatGPT reference: pure-black
  canvas, hidden-by-default chat-history drawer, rounded user bubbles, unboxed assistant text,
  elapsed-generation labels, compact `+` composer control, and a clear send arrow. Voice and
  Grammarly controls were intentionally omitted.
- Added final-answer streaming to the bundled K2 CLI backend while filtering K2 private-reasoning
  and end-of-generation markers. Unicode output is decoded incrementally.
- Added lightweight Markdown headings/bold rendering and fenced code panels with a working Copy
  button.

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
- Fixed composer clipping by packing the fixed-width controls before the expanding text editor; geometry verification at the 850x560 minimum window showed both `Attach` and `Send` mapped at 69x30 pixels.
- Rebuilt and launched the corrected executable; replacement SHA-256 is `18CCAC276E9D439C87F85B2F685E75DF714F6B47C183D4A2339510648C11804A`.
- Source-mode inference against `I:/Model/K2-Horizon-1B-BF16.gguf` returned exactly `READY`.
- Final one-file executable self-test against the same model returned `{"ok": true, "answer": "READY"}` with exit code 0.
- Final artifact is 35,320,718 bytes with SHA-256 `3C3E9A5C39C8B2B25CCDCF7E187115C3297C925E464E6703297EBD9A886EAC94`; the GUI process was relaunched successfully.
- Source inference against `I:/Model/K2-Horizon-1B-BF16.gguf` produced six accumulated stream
  updates and exactly `READY`, with no reasoning/end markers exposed.
- Minimum-window UI verification at 850x560 confirmed the attachment button, send button, and
  fenced-code Copy button are mapped while the history drawer starts hidden.
- Rebuilt `Notepad/dist/Local_LLM_Notepad-portable.exe`; its packaged self-test returned
  `{"ok": true, "answer": "READY", "stream_chunks": 6}`. The artifact is 35,300,461 bytes with
  SHA-256 `5211D83B288013F53823AB4670DF63E886F029C6C61BDEC3A8B9E7B43D1FEC1B`.

## Known limitations / follow-ups

- Programmatic UI geometry and widget tests are available; native screenshot focus was unreliable
  while another application was active, but backend verification includes real packaged inference.
- Attachments currently inject readable text files into the prompt; binary/image understanding is not implemented because the bundled default model is text-only.
- The legacy source-word highlighting, find, and zoom controls were removed from the redesigned primary UI and can be restored if needed.

## Resume point

Use `Notepad/dist/Local_LLM_Notepad-portable.exe`. For rebuilds, compile the MBZUAI-IFM `model/K2Horizon` branch into `.vendor/llama.cpp-k2/build/bin/Release`, then use the updated PyInstaller command in README. Re-run the packaged `--self-test` after every backend or build change.
