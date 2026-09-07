import json
import os
import sys

from chat_gui import run_app


def run_self_test(model_path: str, output_path: str) -> None:
    from llm_utils import respond

    answer = ""
    chunks = 0
    try:
        for answer in respond(
            "Reply with exactly READY",
            [],
            model=model_path,
            max_tokens=128,
            temperature=0.0,
        ):
            chunks += 1
        result = {
            "ok": answer.strip() == "READY" and chunks > 1,
            "answer": answer.strip(),
            "stream_chunks": chunks,
        }
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False)


def run_agent_self_test(output_path: str) -> None:
    from agent_runtime import discover_skills, execute_tool, parse_tool_call

    app_dir = os.path.dirname(os.path.abspath(__file__))
    skills = discover_skills(app_dir)
    calculation = execute_tool("calculator", {"expression": "6 * 7"}, app_dir)
    parsed = parse_tool_call(
        '<tool_call>{"name":"calculator","arguments":{"expression":"6*7"}}</tool_call>'
    )
    result = {
        "ok": calculation == "42" and parsed is not None and len(skills) >= 2,
        "calculator": calculation,
        "skills": [skill.name for skill in skills],
        "tool_call_parsed": parsed is not None,
    }
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False)


def run_tool_self_test(model_path: str, workspace: str, output_path: str) -> None:
    from server_backend import server_agent_respond, stop_server

    result = {"ok": False}
    try:
        final = {"text": "", "tool_calls": 0}
        for kind, payload in server_agent_respond(
            "Use the read_file tool to read only the first line of README.md, then tell me that line.",
            [],
            model=model_path,
            system_message="You are a helpful assistant.",
            workspace=workspace,
            skills=[],
            tools_enabled=True,
        ):
            if kind == "done":
                final = payload
        answer = str(final.get("text", "")).strip()
        calls = int(final.get("tool_calls", 0))
        result = {
            "ok": calls >= 1 and "Local LLM Notepad" in answer,
            "answer": answer,
            "tool_calls": calls,
        }
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    finally:
        stop_server()
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False)


def run_ocr_self_test(model_dir: str, image_path: str, output_path: str) -> None:
    from ocr_utils import extract_file_text

    result = {"ok": False}
    try:
        text = extract_file_text(image_path, model_dir)
        expected = ("Local_LLM_Notepad", "Icon.png", "gemma-3-1b")
        result = {"ok": all(value in text for value in expected), "text": text}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        run_self_test(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "--agent-self-test":
        run_agent_self_test(sys.argv[2])
    elif len(sys.argv) == 5 and sys.argv[1] == "--tool-self-test":
        run_tool_self_test(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 5 and sys.argv[1] == "--ocr-self-test":
        run_ocr_self_test(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        run_app()
