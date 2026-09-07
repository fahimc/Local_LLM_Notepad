import os
import tempfile
import unittest

from agent_runtime import agent_respond, discover_skills, execute_tool, parse_tool_call


class AgentRuntimeTests(unittest.TestCase):
    def test_discovers_bundled_skills(self):
        skills = discover_skills(os.path.dirname(os.path.dirname(__file__)))
        self.assertIn("coding-assistant", {skill.name for skill in skills})

    def test_tools_are_confined_to_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            result = execute_tool("read_file", {"path": "../outside.txt"}, workspace)
        self.assertIn("outside the selected workspace", result)

    def test_calculator(self):
        self.assertEqual("42", execute_tool("calculator", {"expression": "6 * 7"}, "."))

    def test_parses_wrapped_tool_call(self):
        call = parse_tool_call(
            '<tool_call>{"name":"read_file","arguments":{"path":"README.md"}}</tool_call>'
        )
        self.assertEqual(("read_file", {"path": "README.md"}), call)

    def test_parses_k2_native_tool_call(self):
        call = parse_tool_call(
            "<ifm|tool_calls>\n<ifm|tool_call>read_file\n"
            "<ifm|arg_key>path</ifm|arg_key>\n"
            "<ifm|arg_value>README.md</ifm|arg_value>\n"
            "</ifm|tool_call>\n</ifm|tool_calls>"
        )
        self.assertEqual(("read_file", {"path": "README.md"}), call)

    def test_agent_executes_tool_then_streams_final_answer(self):
        with tempfile.TemporaryDirectory() as workspace:
            path = os.path.join(workspace, "note.txt")
            with open(path, "w", encoding="utf-8") as note:
                note.write("portable agent")

            def fake_respond(message, history, **_kwargs):
                if not message.startswith("Original request:"):
                    yield '<tool_call>{"name":"read_file","arguments":{"path":"note.txt"}}</tool_call>'
                else:
                    yield "The"
                    yield "The note says portable agent."

            events = list(agent_respond(
                "What does note.txt say?", [], model="unused", system_message="help",
                workspace=workspace, skills=[], tools_enabled=True, respond_fn=fake_respond))

        self.assertIn(("status", "Using read_file…"), events)
        self.assertEqual("The note says portable agent.", events[-1][1]["text"])
        self.assertEqual(1, events[-1][1]["tool_calls"])


if __name__ == "__main__":
    unittest.main()
