# Portable tool calling and skills

## Purpose

Extend the standalone local chat app with native model tool calling and reusable Markdown skills
without adding external services or install-time dependencies.

## Decisions and security constraints

- Use the K2-capable `llama-server.exe` API for normal GUI inference so assistant tool calls and
  tool results retain native assistant/tool roles. The existing completion CLI remains available
  as a compatibility fallback and for the original inference self-test.
- Start the server only on `127.0.0.1` with a random free port and random per-process API key.
  Keep it alive for fast subsequent prompts, restart it when the selected model changes, and stop
  it at application exit.
- Built-in tools are deliberately read-only: `list_files`, `read_file`, `search_text`, and a safe
  AST-based `calculator`. All file paths are resolved and confined to the user-selected workspace;
  large files and result counts are capped.
- Skills use `skills/<name>/SKILL.md` with simple YAML-style `name` and `description` metadata.
  Sidecar skills beside the EXE override bundled skills with the same name. Enabled skills are
  stored per chat session.
- K2 can emit its native `<ifm|tool_calls>` representation; the completion fallback parses that
  format as well as JSON/XML wrappers.

## Completed

- Added `Notepad/agent_runtime.py` for skill discovery, safe tool execution, fallback tool-call
  orchestration, and K2/native call parsing.
- Added `Notepad/server_backend.py` for authenticated local server lifecycle, OpenAI-compatible
  streamed chat requests, structured multi-round tool calls, and proper tool result messages.
- Added Tools and Skills menus, workspace selection, tool/skill status in the header, transient
  tool activity in the answer area, and elapsed tool-call counts on completed answers.
- Added bundled `coding-assistant` and `document-analyst` starter skills.
- Added six unit tests under `Notepad/tests/test_agent_runtime.py` and headless `--agent-self-test`
  and `--tool-self-test` modes.
- Updated README feature and portable build documentation. The PyInstaller build now includes
  `--add-data "skills;skills"` and bundles the release runtime directory containing the server.

## Verification

- Six unit tests pass: skill discovery, safe calculation, path confinement, generic and K2 call
  parsing, and deterministic call/result/final-answer orchestration.
- Source native K2 integration selected `list_files` and `read_file`, then returned
  `# Local LLM Notepad` from the real workspace.
- Packaged `--agent-self-test` returned two embedded skills, calculator `42`, and successful call
  parsing.
- Packaged `--tool-self-test` against `I:/Model/K2-Horizon-1B-BF16.gguf` returned
  `{"ok": true, "answer": "# Local LLM Notepad", "tool_calls": 2}`.
- The original packaged streaming regression test still returns
  `{"ok": true, "answer": "READY", "stream_chunks": 6}`.
- Final `Notepad/dist/Local_LLM_Notepad-portable.exe` is 44,696,741 bytes with SHA-256
  `C094255507D38594C6C39F8BA4EFC6241934A8CDFB20CA6EDA6CFEE0EE65F9C0`.

## Resume point

Use the packaged EXE above. Tool access defaults on and is limited to the EXE folder until the
user chooses Tools > Select Workspace. Enable bundled or sidecar skills from the Skills menu.
When rebuilding the native runtime, configure `LLAMA_BUILD_SERVER=ON` and include the complete
release binary directory in the PyInstaller bundle.
