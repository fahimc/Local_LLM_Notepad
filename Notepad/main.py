import json
import sys

from chat_gui import run_app


def run_self_test(model_path: str, output_path: str) -> None:
    from llm_utils import respond

    answer = ""
    try:
        for answer in respond(
            "Reply with exactly READY",
            [],
            model=model_path,
            max_tokens=128,
            temperature=0.0,
        ):
            pass
        result = {"ok": answer.strip() == "READY", "answer": answer.strip()}
    except Exception as exc:
        result = {"ok": False, "error": str(exc)}
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--self-test":
        run_self_test(sys.argv[2], sys.argv[3])
    else:
        run_app()
