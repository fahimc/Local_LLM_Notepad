from __future__ import annotations

import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from typing import Any, List, Tuple

from agent_runtime import Skill, agent_respond, discover_skills

__all__ = ["ChatGUI", "run_app"]


class ChatGUI:
    """A focused, portable ChatGPT-style front end for a local model."""

    BG = "#000000"
    SIDEBAR = "#171717"
    PANEL = "#2f2f2f"
    PANEL_HOVER = "#424242"
    TEXT = "#f2f2f2"
    MUTED = "#b4b4b4"
    DIM = "#7d7d7d"
    CODE = "#1f1f1f"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Local LLM Notepad")
        self.root.geometry("1180x790")
        self.root.minsize(850, 560)
        self.root.configure(bg=self.BG)
        self.app_dir = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                        else os.path.dirname(os.path.abspath(__file__)))
        self.session_file = os.path.join(self.app_dir, "chat_sessions.json")
        self.settings_file = os.path.join(self.app_dir, "app_settings.json")
        default_ocr = r"I:\models\PP-OCRv6-small"
        self.system_prompt = "You are a helpful assistant."
        self.model_path = "gemma-3-1b-it-Q4_K_M.gguf"
        self.ocr_model_dir = default_ocr if os.path.isdir(default_ocr) else ""
        self.workspace_dir = self.app_dir
        saved_settings = self._load_settings()
        self.system_prompt = str(saved_settings.get("system_prompt", self.system_prompt))
        self.model_path = str(saved_settings.get("model_path", self.model_path))
        self.ocr_model_dir = str(saved_settings.get("ocr_model_dir", self.ocr_model_dir))
        self.workspace_dir = str(saved_settings.get("workspace_dir", self.workspace_dir))
        self.skills: list[Skill] = discover_skills(self.app_dir)
        self.enabled_skill_names: set[str] = set()
        self.skill_vars: dict[str, tk.BooleanVar] = {}
        self.tools_enabled = tk.BooleanVar(value=bool(saved_settings.get("tools_enabled", True)))
        self.sessions: list[dict[str, Any]] = []
        self.current_session: dict[str, Any] | None = None
        self.history_data: list[dict[str, str]] = []
        self.attachments: list[str] = []
        self.queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.gen_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.assistant_label: tk.Label | None = None
        self.assistant_text = ""
        self.sidebar_visible = False
        self.placeholder_visible = False
        self._build_menu()
        self._build_layout()
        self._load_sessions()
        if self.sessions:
            self.current_session = self.sessions[0]
            self.enabled_skill_names = {
                str(name).casefold() for name in self.current_session.get("skills", [])
            }
            self._rebuild_skills_menu()
            self._update_agent_label()
            self.title_label.config(text=self.current_session["title"])
            self._refresh_sessions()
            self._render_chat()
        else:
            self.new_chat()

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg=self.PANEL, fg=self.TEXT,
                       activebackground=self.PANEL_HOVER, activeforeground="white")
        file_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        file_menu.add_command(label="New chat", accelerator="Ctrl+N", command=self.new_chat)
        file_menu.add_command(label="Select Model...", command=self.select_model)
        file_menu.add_command(label="Settings...", command=self.open_settings)
        file_menu.add_command(label="Save Current Chat...", command=self.save_chat)
        file_menu.add_command(label="Load Chat...", command=self.load_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu.add_cascade(label="File", menu=file_menu)
        edit = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        edit.add_command(label="Send", accelerator="Enter", command=self.on_send)
        edit.add_command(label="Attach Files...", accelerator="Ctrl+O", command=self.attach_files)
        edit.add_command(label="Edit System Prompt...", accelerator="Ctrl+P", command=self.edit_system_prompt)
        edit.add_separator()
        edit.add_command(label="Stop Generation", accelerator="Ctrl+Z", command=self.on_stop)
        menu.add_cascade(label="Edit", menu=edit)
        view = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        view.add_command(label="Toggle chat history", accelerator="Ctrl+B", command=self.toggle_sidebar)
        menu.add_cascade(label="View", menu=view)
        tools_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        tools_menu.add_checkbutton(label="Enable local tools", variable=self.tools_enabled,
                                   command=self._toggle_tools)
        tools_menu.add_command(label="Select Workspace...", command=self.select_workspace)
        menu.add_cascade(label="Tools", menu=tools_menu)
        self.skills_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        menu.add_cascade(label="Skills", menu=self.skills_menu)
        self._rebuild_skills_menu()
        help_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def _button(self, parent: tk.Widget, text: str, command, **kwargs) -> tk.Button:
        defaults = dict(bg=self.PANEL, fg=self.TEXT, activebackground=self.PANEL_HOVER,
                        activeforeground="white", relief="flat", bd=0, cursor="hand2",
                        padx=10, pady=7, font=("Segoe UI", 10))
        defaults.update(kwargs)
        return tk.Button(parent, text=text, command=command, **defaults)

    @staticmethod
    def _rounded_rectangle(canvas: tk.Canvas, x1: int, y1: int, x2: int, y2: int,
                           radius: int, **kwargs) -> int:
        points = [x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
                  x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
                  x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _build_layout(self) -> None:
        self.shell = tk.Frame(self.root, bg=self.BG)
        self.shell.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.shell, bg=self.SIDEBAR, width=270)
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="Local LLM", bg=self.SIDEBAR, fg="white",
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(
                     fill="x", padx=18, pady=(20, 14))
        self._button(self.sidebar, "+  New chat", self.new_chat, bg=self.SIDEBAR,
                     activebackground="#2a2a2a", anchor="w",
                     font=("Segoe UI", 10, "bold")).pack(fill="x", padx=10)
        tk.Label(self.sidebar, text="YOUR CHATS", bg=self.SIDEBAR, fg=self.DIM,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(
                     fill="x", padx=18, pady=(24, 8))
        self.session_list = tk.Listbox(
            self.sidebar, bg=self.SIDEBAR, fg="#d1d1d1", selectbackground="#343434",
            selectforeground="white", relief="flat", bd=0, highlightthickness=0,
            activestyle="none", font=("Segoe UI", 10), exportselection=False)
        self.session_list.pack(fill="both", expand=True, padx=8)
        self.session_list.bind("<<ListboxSelect>>", self._select_session)
        self._button(self.sidebar, "Settings", self.open_settings,
                     bg=self.SIDEBAR, activebackground="#2a2a2a", anchor="w").pack(
                         fill="x", padx=10, pady=(8, 16))

        self.main = tk.Frame(self.shell, bg=self.BG)
        self.main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(self.main, bg=self.BG, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        self._button(header, "☰", self.toggle_sidebar, bg=self.BG,
                     activebackground="#202020", font=("Segoe UI Symbol", 14),
                     padx=12, pady=4).pack(side="left", padx=(10, 4), pady=8)
        self.title_label = tk.Label(header, text="New chat", bg=self.BG, fg=self.TEXT,
                                    font=("Segoe UI", 11, "bold"), anchor="w")
        self.title_label.pack(side="left", padx=4)
        self.model_label = tk.Label(header, text=os.path.basename(self.model_path), bg=self.BG,
                                    fg=self.MUTED, font=("Segoe UI", 9), anchor="e")
        self.model_label.pack(side="right", padx=24)
        self.agent_label = tk.Label(header, text="Tools on · 0 skills", bg=self.BG,
                                    fg=self.DIM, font=("Segoe UI", 9), anchor="e")
        self.agent_label.pack(side="right", padx=(8, 0))

        chat_outer = tk.Frame(self.main, bg=self.BG)
        chat_outer.pack(fill="both", expand=True)
        self.chat_canvas = tk.Canvas(chat_outer, bg=self.BG, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(chat_outer, orient="vertical", command=self.chat_canvas.yview,
                              bg="#555555", troughcolor=self.BG,
                              activebackground="#777777", relief="flat", bd=0,
                              highlightthickness=0)
        self.chat_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_frame = tk.Frame(self.chat_canvas, bg=self.BG)
        self.chat_window = self.chat_canvas.create_window(
            (0, 0), window=self.chat_frame, anchor="nw")
        self.chat_frame.bind("<Configure>", lambda _e: self.chat_canvas.configure(
            scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.bind("<Configure>", lambda e: self.chat_canvas.itemconfigure(
            self.chat_window, width=e.width))

        composer = tk.Frame(self.main, bg=self.BG)
        composer.pack(fill="x", padx=80, pady=(8, 20))
        self.attachment_row = tk.Frame(composer, bg=self.BG)
        self.attachment_row.pack(fill="x")
        self.composer_box = tk.Frame(composer, bg=self.PANEL, highlightthickness=0)
        self.composer_box.pack(fill="x", ipady=5)
        self.attach_button = self._button(
            self.composer_box, "+", self.attach_files, bg=self.PANEL,
            activebackground=self.PANEL_HOVER, font=("Segoe UI", 16), width=3,
            padx=1, pady=0)
        self.attach_button.pack(side="left", padx=(8, 2), pady=6)
        self.send_button = self._button(
            self.composer_box, "↑", self.on_send, bg="#f4f4f4", fg="#111111",
            activebackground="#d8d8d8", activeforeground="#111111",
            font=("Segoe UI", 15, "bold"), width=3, padx=2, pady=1)
        self.send_button.pack(side="right", padx=(4, 10), pady=6)
        self.input_text = tk.Text(
            self.composer_box, height=2, wrap="word", bg=self.PANEL, fg=self.TEXT,
            insertbackground="white", selectbackground="#565656", relief="flat",
            bd=0, highlightthickness=0, padx=8, pady=12,
            font=("Segoe UI", 12))
        self.input_text.pack(side="left", fill="both", expand=True)
        self.input_text.bind("<Return>", self._on_input_return)
        self.input_text.bind("<FocusIn>", self._clear_placeholder)
        self.input_text.bind("<FocusOut>", self._restore_placeholder)
        self._restore_placeholder()
        tk.Label(composer,
                 text="Local LLM Notepad can make mistakes. Check important information.",
                 bg=self.BG, fg=self.DIM, font=("Segoe UI", 8)).pack(pady=(8, 0))
        self.root.bind("<Control-n>", lambda _e: self.new_chat())
        self.root.bind("<Control-b>", lambda _e: self.toggle_sidebar())
        self.root.bind("<Control-o>", lambda _e: self.attach_files())
        self.root.bind("<Control-p>", lambda _e: self.open_settings())
        self.root.bind("<Control-z>", lambda _e: self.on_stop())

    def toggle_sidebar(self) -> None:
        if self.sidebar_visible:
            self.sidebar.pack_forget()
        else:
            self.sidebar.pack(side="left", fill="y", before=self.main)
        self.sidebar_visible = not self.sidebar_visible

    def _rebuild_skills_menu(self) -> None:
        self.skills_menu.delete(0, tk.END)
        self.skill_vars = {}
        if not self.skills:
            self.skills_menu.add_command(label="No skills found", state="disabled")
        for skill in self.skills:
            enabled = skill.name.casefold() in self.enabled_skill_names
            variable = tk.BooleanVar(value=enabled)
            self.skill_vars[skill.name.casefold()] = variable
            self.skills_menu.add_checkbutton(
                label=skill.name,
                variable=variable,
                command=lambda selected=skill.name: self._toggle_skill(selected),
            )
        self.skills_menu.add_separator()
        self.skills_menu.add_command(label="Reload Skills", command=self.reload_skills)
        self.skills_menu.add_command(label="Open Skills Folder", command=self.open_skills_folder)

    def _toggle_skill(self, name: str) -> None:
        key = name.casefold()
        variable = self.skill_vars[key]
        if variable.get():
            self.enabled_skill_names.add(key)
        else:
            self.enabled_skill_names.discard(key)
        if self.current_session is not None:
            self.current_session["skills"] = sorted(self.enabled_skill_names)
            self._persist_sessions()
        self._update_agent_label()

    def _update_agent_label(self) -> None:
        if not hasattr(self, "agent_label"):
            return
        tools = "Tools on" if self.tools_enabled.get() else "Tools off"
        count = len(self.enabled_skill_names)
        self.agent_label.configure(text=f"{tools} · {count} skill{'s' if count != 1 else ''}")

    def _toggle_tools(self) -> None:
        self._update_agent_label()
        self._persist_settings()

    def reload_skills(self) -> None:
        self.skills = discover_skills(self.app_dir)
        available = {skill.name.casefold() for skill in self.skills}
        self.enabled_skill_names.intersection_update(available)
        self._rebuild_skills_menu()
        self._update_agent_label()

    def open_skills_folder(self) -> None:
        path = os.path.join(self.app_dir, "skills")
        os.makedirs(path, exist_ok=True)
        if os.name == "nt":
            os.startfile(path)

    def _load_settings(self) -> dict[str, Any]:
        try:
            with open(self.settings_file, "r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _persist_settings(self) -> None:
        settings = {
            "model_path": self.model_path,
            "ocr_model_dir": self.ocr_model_dir,
            "workspace_dir": self.workspace_dir,
            "system_prompt": self.system_prompt,
            "tools_enabled": self.tools_enabled.get(),
        }
        try:
            temp_path = self.settings_file + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as settings_file:
                json.dump(settings, settings_file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.settings_file)
        except OSError:
            pass

    def select_workspace(self) -> None:
        path = filedialog.askdirectory(title="Select workspace for local tools",
                                       initialdir=self.workspace_dir)
        if path:
            self.workspace_dir = os.path.abspath(path)
            self._update_agent_label()
            self._persist_settings()

    def _on_input_return(self, event: tk.Event) -> str | None:
        if event.state & 0x0001:
            return None
        self.on_send()
        return "break"

    def _clear_placeholder(self, _event=None) -> None:
        if self.placeholder_visible:
            self.input_text.delete("1.0", tk.END)
            self.input_text.configure(fg=self.TEXT)
            self.placeholder_visible = False

    def _restore_placeholder(self, _event=None) -> None:
        if not self.input_text.get("1.0", tk.END).strip():
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", "Message Local LLM")
            self.input_text.configure(fg=self.MUTED)
            self.placeholder_visible = True

    def new_chat(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            return
        session = {"title": "New chat", "messages": [], "skills": []}
        self.sessions.insert(0, session)
        self.current_session = session
        self.enabled_skill_names.clear()
        self._rebuild_skills_menu()
        self._update_agent_label()
        self.history_data = []
        self.attachments.clear()
        self.title_label.config(text="New chat")
        self._refresh_sessions()
        self._render_chat()
        self._persist_sessions()
        self.input_text.focus_set()

    def _load_sessions(self) -> None:
        try:
            with open(self.session_file, "r", encoding="utf-8") as session_file:
                data = json.load(session_file)
            if isinstance(data, list):
                self.sessions = [session for session in data if isinstance(session, dict)
                                 and isinstance(session.get("messages"), list)]
        except (OSError, json.JSONDecodeError):
            self.sessions = []

    def _persist_sessions(self) -> None:
        try:
            temp_path = self.session_file + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as session_file:
                json.dump(self.sessions, session_file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.session_file)
        except OSError:
            pass

    def _refresh_sessions(self) -> None:
        self.session_list.delete(0, tk.END)
        for session in self.sessions:
            self.session_list.insert(tk.END, "  " + session["title"])
        if self.current_session in self.sessions:
            index = self.sessions.index(self.current_session)
            self.session_list.selection_set(index)
            self.session_list.see(index)

    def _select_session(self, _event=None) -> None:
        selection = self.session_list.curselection()
        if not selection or (self.gen_thread and self.gen_thread.is_alive()):
            return
        self.current_session = self.sessions[selection[0]]
        self.enabled_skill_names = {
            str(name).casefold() for name in self.current_session.get("skills", [])
        }
        self._rebuild_skills_menu()
        self._update_agent_label()
        self.history_data = []
        messages = self.current_session["messages"]
        for index, message in enumerate(messages):
            if (message["role"] == "user" and index + 1 < len(messages)
                    and messages[index + 1]["role"] == "assistant"):
                self.history_data.append({"user": message["content"],
                                          "assistant": messages[index + 1]["content"]})
        self.title_label.config(text=self.current_session["title"])
        self._render_chat()

    def _render_chat(self) -> None:
        for child in self.chat_frame.winfo_children():
            child.destroy()
        if not self.current_session or not self.current_session["messages"]:
            welcome = tk.Frame(self.chat_frame, bg=self.BG)
            welcome.pack(fill="x", pady=(135, 30))
            tk.Label(welcome, text="How can I help you today?", bg=self.BG, fg="white",
                     font=("Segoe UI", 24, "bold")).pack()
            tk.Label(welcome, text="Ask a question or attach a document to get started.",
                     bg=self.BG, fg=self.MUTED, font=("Segoe UI", 11)).pack(pady=(9, 0))
        else:
            for message in self.current_session["messages"]:
                self._add_message(message["role"], message["content"],
                                  message.get("elapsed_seconds"), message.get("tool_calls", 0))
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)
        self._refresh_attachment_row()

    def _add_message(self, role: str, content: str,
                     elapsed_seconds: float | None = None,
                     tool_calls: int = 0) -> tk.Label | None:
        row = tk.Frame(self.chat_frame, bg=self.BG)
        row.pack(fill="x", padx=20, pady=(7, 18 if role == "assistant" else 7))
        body = tk.Frame(row, bg=self.BG)
        body.pack(fill="x")
        if role == "user":
            bubble = tk.Canvas(body, bg=self.BG, highlightthickness=0, bd=0)
            label = tk.Label(bubble, text=content, bg=self.PANEL, fg=self.TEXT,
                             justify="left", anchor="w", wraplength=610,
                             font=("Segoe UI", 11))
            label.update_idletasks()
            width = min(646, max(72, label.winfo_reqwidth() + 36))
            height = max(46, label.winfo_reqheight() + 26)
            bubble.configure(width=width, height=height)
            self._rounded_rectangle(bubble, 1, 1, width - 1, height - 1, 18,
                                    fill=self.PANEL, outline=self.PANEL)
            bubble.create_window(18, 13, window=label, anchor="nw",
                                 width=width - 36, height=height - 26)
            bubble.pack(anchor="e", padx=(150, 55))
            return label
        content_frame = tk.Frame(body, bg=self.BG)
        content_frame.pack(fill="x", padx=(55, 70))
        if elapsed_seconds is not None:
            tool_note = f" · {tool_calls} tool call{'s' if tool_calls != 1 else ''}" \
                if tool_calls else ""
            tk.Label(content_frame,
                     text=f"Worked for {self._format_duration(elapsed_seconds)}{tool_note}  ›",
                     bg=self.BG, fg=self.MUTED, anchor="w",
                     font=("Segoe UI", 10)).pack(fill="x", pady=(0, 16))
        if not content:
            label = tk.Label(content_frame, text="", bg=self.BG, fg=self.TEXT,
                             justify="left", anchor="w", wraplength=790,
                             font=("Segoe UI", 12))
            label.pack(fill="x")
            return label
        self._render_assistant_content(content_frame, content)
        return None

    @staticmethod
    def _format_duration(seconds: float) -> str:
        rounded = max(1, int(round(seconds)))
        minutes, seconds_left = divmod(rounded, 60)
        return f"{minutes}m {seconds_left}s" if minutes else f"{seconds_left}s"

    def _render_assistant_content(self, parent: tk.Widget, content: str) -> None:
        parts = re.split(r"```([^\n`]*)\n?(.*?)```", content, flags=re.DOTALL)
        if len(parts) == 1:
            self._render_markdown_text(parent, content)
            return
        for index in range(0, len(parts), 3):
            prose = parts[index]
            if prose.strip():
                self._render_markdown_text(parent, prose.strip("\n"))
            if index + 2 < len(parts):
                self._render_code_block(parent, parts[index + 1].strip(),
                                        parts[index + 2].rstrip())

    def _render_markdown_text(self, parent: tk.Widget, text: str) -> None:
        display_lines = sum(max(1, (len(line) // 70) + 1)
                            for line in (text.splitlines() or [""]))
        widget = tk.Text(parent, height=max(1, display_lines), wrap="word", bg=self.BG,
                         fg=self.TEXT, relief="flat", bd=0, highlightthickness=0,
                         cursor="arrow", padx=0, pady=0, font=("Segoe UI", 12),
                         spacing1=2, spacing3=5)
        widget.pack(fill="x", pady=(0, 8))
        widget.tag_configure("h1", font=("Segoe UI", 18, "bold"), spacing1=9, spacing3=5)
        widget.tag_configure("h2", font=("Segoe UI", 15, "bold"), spacing1=8, spacing3=4)
        widget.tag_configure("h3", font=("Segoe UI", 13, "bold"), spacing1=7, spacing3=3)
        widget.tag_configure("bold", font=("Segoe UI", 12, "bold"))
        lines = text.splitlines()
        for line_number, line in enumerate(lines):
            heading = re.match(r"^(#{1,3})\s+(.*)$", line)
            if heading:
                widget.insert(tk.END, heading.group(2), f"h{len(heading.group(1))}")
            else:
                cursor = 0
                for match in re.finditer(r"\*\*(.+?)\*\*", line):
                    widget.insert(tk.END, line[cursor:match.start()])
                    widget.insert(tk.END, match.group(1), "bold")
                    cursor = match.end()
                widget.insert(tk.END, line[cursor:])
            if line_number < len(lines) - 1:
                widget.insert(tk.END, "\n")
        widget.configure(state="disabled")

    def _render_code_block(self, parent: tk.Widget, language: str, code: str) -> None:
        block = tk.Frame(parent, bg=self.CODE)
        block.pack(fill="x", pady=(8, 14))
        header = tk.Frame(block, bg=self.CODE)
        header.pack(fill="x", padx=12, pady=(9, 0))
        tk.Label(header, text=language or "code", bg=self.CODE, fg=self.MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        copy_button = self._button(header, "▣  Copy", lambda: self._copy_code(code, copy_button),
                                   bg=self.CODE, activebackground="#343434",
                                   font=("Segoe UI", 9), padx=7, pady=3)
        copy_button.pack(side="right")
        code_widget = tk.Text(block, height=max(1, min(24, code.count("\n") + 1)),
                              wrap="none", bg=self.CODE, fg="#f5f5f5",
                              selectbackground="#555555", relief="flat", bd=0,
                              highlightthickness=0, padx=14, pady=12,
                              font=("Consolas", 10))
        code_widget.insert("1.0", code)
        code_widget.configure(state="disabled")
        code_widget.pack(fill="x")

    def _copy_code(self, code: str, button: tk.Button) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.root.update_idletasks()
        button.configure(text="✓  Copied")
        self.root.after(1400, lambda: button.winfo_exists()
                        and button.configure(text="▣  Copy"))

    def attach_files(self) -> None:
        paths = filedialog.askopenfilenames(title="Attach files")
        for path in paths:
            if path not in self.attachments:
                self.attachments.append(path)
        self._refresh_attachment_row()

    def _refresh_attachment_row(self) -> None:
        for child in self.attachment_row.winfo_children():
            child.destroy()
        for path in self.attachments:
            chip = tk.Frame(self.attachment_row, bg=self.PANEL)
            chip.pack(side="left", padx=(0, 6), pady=(0, 5))
            tk.Label(chip, text=os.path.basename(path), bg=self.PANEL, fg=self.TEXT,
                     font=("Segoe UI", 9), padx=8, pady=4).pack(side="left")
            tk.Button(chip, text="×", command=lambda selected=path:
                      self._remove_attachment(selected), bg=self.PANEL, fg=self.MUTED,
                      activebackground=self.PANEL, activeforeground="white", relief="flat",
                      bd=0, font=("Segoe UI", 11)).pack(side="left", padx=(0, 4))

    def _remove_attachment(self, path: str) -> None:
        self.attachments.remove(path)
        self._refresh_attachment_row()

    def on_send(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            return
        prompt = "" if self.placeholder_visible else self.input_text.get("1.0", tk.END).strip()
        if not prompt or not self.current_session:
            return
        attached_paths = list(self.attachments)
        previous: list[Tuple[str, str]] = []
        messages = self.current_session["messages"]
        for index, message in enumerate(messages):
            if (message["role"] == "user" and index + 1 < len(messages)
                    and messages[index + 1]["role"] == "assistant"):
                previous.append((message["content"], messages[index + 1]["content"]))
        self.current_session["messages"].append({"role": "user", "content": prompt})
        if self.current_session["title"] == "New chat":
            self.current_session["title"] = prompt[:34] + ("…" if len(prompt) > 34 else "")
            self.title_label.config(text=self.current_session["title"])
        self.history_data.append({"user": prompt, "assistant": ""})
        self.input_text.delete("1.0", tk.END)
        self.placeholder_visible = False
        self.attachments.clear()
        self._restore_placeholder()
        self._refresh_sessions()
        self._render_chat()
        self.assistant_label = self._add_message("assistant", "")
        self.assistant_text = ""
        self.stop_event.clear()
        self.queue = queue.Queue()
        session = self.current_session
        self.gen_thread = threading.Thread(target=self._worker_generate,
                                           args=(prompt, attached_paths, previous, session),
                                           daemon=True)
        self.gen_thread.start()
        self.chat_canvas.after(35, self._process_queue)

    def _worker_generate(self, prompt: str, attachments: list[str],
                         history: List[Tuple[str, str]],
                         session: dict[str, Any]) -> None:
        last = ""
        visible = ""
        tool_calls = 0
        started = time.perf_counter()
        try:
            if attachments:
                from ocr_utils import attachment_context

                context = attachment_context(
                    attachments,
                    self.ocr_model_dir,
                    lambda message: self.queue.put(("status", message)),
                )
                prompt += context
                self.history_data[-1]["user"] = prompt
            from llm_utils import respond
            from server_backend import server_agent_respond, server_available
            enabled_skills = [skill for skill in self.skills
                              if skill.name.casefold() in self.enabled_skill_names]
            self.queue.put(("status", "Loading local model…"))
            if server_available():
                events = server_agent_respond(
                    prompt, history, model=self.model_path,
                    system_message=self.system_prompt, workspace=self.workspace_dir,
                    skills=enabled_skills, tools_enabled=self.tools_enabled.get())
            else:
                events = agent_respond(
                    prompt, history, model=self.model_path,
                    system_message=self.system_prompt, workspace=self.workspace_dir,
                    skills=enabled_skills, tools_enabled=self.tools_enabled.get(),
                    respond_fn=respond)
            for kind, payload in events:
                if self.stop_event.is_set():
                    last = visible
                    break
                if kind == "done":
                    last = str(payload.get("text", ""))
                    tool_calls = int(payload.get("tool_calls", 0))
                else:
                    if kind == "replace":
                        visible = str(payload)
                    elif kind == "text":
                        visible += str(payload)
                    self.queue.put((kind, payload))
        except Exception as exc:
            if not last:
                last = visible
            error_text = f"\n\nError: {exc}" if last else f"Error: {exc}"
            last += error_text
            self.queue.put(("text", error_text))
        finally:
            elapsed = time.perf_counter() - started
            session["messages"].append({"role": "assistant", "content": last,
                                        "elapsed_seconds": elapsed,
                                        "tool_calls": tool_calls})
            self.history_data[-1]["assistant"] = last
            self.queue.put(("done", {"elapsed_seconds": elapsed,
                                     "tool_calls": tool_calls}))

    def _process_queue(self) -> None:
        finished = False
        while True:
            try:
                kind, payload = self.queue.get_nowait()
            except queue.Empty:
                break
            if kind == "done":
                finished = True
                continue
            if kind == "replace":
                self.assistant_text = str(payload)
            elif kind == "status":
                if self.assistant_label:
                    self.assistant_label.configure(text=str(payload), fg=self.MUTED)
                continue
            else:
                self.assistant_text += str(payload)
            if self.assistant_label:
                self.assistant_label.config(text=self.assistant_text, fg=self.TEXT)
            self.chat_canvas.update_idletasks()
            self.chat_canvas.yview_moveto(1.0)
        if finished:
            self.assistant_label = None
            self._refresh_sessions()
            self._persist_sessions()
            self._render_chat()
            return
        if self.gen_thread and self.gen_thread.is_alive():
            self.chat_canvas.after(35, self._process_queue)

    def on_stop(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            self.stop_event.set()

    def select_model(self) -> None:
        path = filedialog.askopenfilename(title="Select GGUF model",
                                          filetypes=[("GGUF Model", "*.gguf"),
                                                     ("All files", "*.*")])
        if path:
            self.model_path = path
            self.model_label.config(text=os.path.basename(path))
            self._persist_settings()

    def save_chat(self) -> None:
        if not self.current_session or not self.current_session["messages"]:
            messagebox.showinfo("Save Chat", "Nothing to save yet.")
            return
        path = filedialog.asksaveasfilename(title="Save Chat", defaultextension=".json",
                                            filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as output_file:
                json.dump(self.current_session["messages"], output_file,
                          ensure_ascii=False, indent=2)

    def load_chat(self) -> None:
        path = filedialog.askopenfilename(title="Load Chat",
                                          filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as input_file:
                data = json.load(input_file)
            messages = data if isinstance(data, list) else data.get("messages", [])
            if not all(isinstance(message, dict)
                       and message.get("role") in ("user", "assistant")
                       for message in messages):
                raise ValueError("Invalid chat format")
            session = {"title": next((message["content"][:34] for message in messages
                                      if message["role"] == "user"), "Loaded chat"),
                       "messages": messages, "skills": []}
            self.sessions.insert(0, session)
            self.current_session = session
            self.title_label.config(text=session["title"])
            self._refresh_sessions()
            self._render_chat()
            self._persist_sessions()
        except Exception as exc:
            messagebox.showerror("Load Chat", f"Could not load chat:\n{exc}")

    def edit_system_prompt(self) -> None:
        prompt = simpledialog.askstring("System prompt", "Instructions for the assistant:",
                                        initialvalue=self.system_prompt, parent=self.root)
        if prompt is not None:
            self.system_prompt = prompt.strip() or "You are a helpful assistant."
            self._persist_settings()

    def open_settings(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            messagebox.showinfo("Settings", "Wait for the current response to finish first.")
            return

        dialog = tk.Toplevel(self.root, bg=self.SIDEBAR)
        dialog.title("Settings")
        dialog.geometry("700x560")
        dialog.minsize(620, 500)
        dialog.transient(self.root)
        dialog.grab_set()

        content = tk.Frame(dialog, bg=self.SIDEBAR)
        content.pack(fill="both", expand=True, padx=24, pady=20)
        tk.Label(content, text="Settings", bg=self.SIDEBAR, fg=self.TEXT,
                 font=("Segoe UI", 18, "bold"), anchor="w").pack(fill="x", pady=(0, 18))

        chat_var = tk.StringVar(value=self.model_path)
        ocr_var = tk.StringVar(value=self.ocr_model_dir)
        workspace_var = tk.StringVar(value=self.workspace_dir)
        tools_var = tk.BooleanVar(value=self.tools_enabled.get())

        def path_row(label_text: str, variable: tk.StringVar, browse_command) -> None:
            tk.Label(content, text=label_text, bg=self.SIDEBAR, fg=self.MUTED,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(7, 4))
            row = tk.Frame(content, bg=self.SIDEBAR)
            row.pack(fill="x")
            tk.Entry(row, textvariable=variable, bg=self.PANEL, fg=self.TEXT,
                     insertbackground="white", relief="flat", bd=0,
                     font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True,
                                                  ipady=8, padx=(0, 8))
            self._button(row, "Browse", browse_command, padx=14, pady=8).pack(side="right")

        def browse_chat() -> None:
            selected = filedialog.askopenfilename(parent=dialog, title="Select GGUF chat model",
                                                  filetypes=[("GGUF Model", "*.gguf"),
                                                             ("All files", "*.*")])
            if selected:
                chat_var.set(selected)

        def browse_ocr() -> None:
            selected = filedialog.askdirectory(parent=dialog,
                                               title="Select PP-OCRv6 model folder",
                                               initialdir=ocr_var.get() or self.app_dir)
            if selected:
                ocr_var.set(selected)

        def browse_workspace() -> None:
            selected = filedialog.askdirectory(parent=dialog, title="Select tools workspace",
                                               initialdir=workspace_var.get() or self.app_dir)
            if selected:
                workspace_var.set(selected)

        path_row("Chat model (.gguf)", chat_var, browse_chat)
        path_row("Attachment OCR model folder (PP-OCRv6 Small)", ocr_var, browse_ocr)
        tk.Label(content, text="Leave blank to use the OCR model bundled in the EXE.",
                 bg=self.SIDEBAR, fg=self.DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x")
        path_row("Local tools workspace", workspace_var, browse_workspace)

        tk.Label(content, text="System prompt", bg=self.SIDEBAR, fg=self.MUTED,
                 font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=(12, 4))
        prompt_text = tk.Text(content, height=5, wrap="word", bg=self.PANEL, fg=self.TEXT,
                              insertbackground="white", relief="flat", bd=0,
                              padx=10, pady=8, font=("Segoe UI", 10))
        prompt_text.insert("1.0", self.system_prompt)
        prompt_text.pack(fill="both", expand=True)
        tk.Checkbutton(content, text="Enable local tools", variable=tools_var,
                       bg=self.SIDEBAR, fg=self.TEXT, selectcolor=self.PANEL,
                       activebackground=self.SIDEBAR, activeforeground=self.TEXT,
                       font=("Segoe UI", 10)).pack(anchor="w", pady=(12, 5))

        actions = tk.Frame(content, bg=self.SIDEBAR)
        actions.pack(fill="x", pady=(10, 0))

        def save() -> None:
            from ocr_utils import validate_model_dir

            ocr_path = ocr_var.get().strip()
            valid, detail = validate_model_dir(ocr_path)
            if not valid:
                messagebox.showerror("Invalid OCR model folder", detail, parent=dialog)
                return
            self.model_path = chat_var.get().strip() or self.model_path
            self.ocr_model_dir = ocr_path
            self.workspace_dir = workspace_var.get().strip() or self.app_dir
            self.system_prompt = (prompt_text.get("1.0", tk.END).strip()
                                  or "You are a helpful assistant.")
            self.tools_enabled.set(tools_var.get())
            self.model_label.configure(text=os.path.basename(self.model_path))
            self._update_agent_label()
            self._persist_settings()
            dialog.destroy()

        self._button(actions, "Save", save, bg="#f4f4f4", fg="#111111",
                     activebackground="#d8d8d8", activeforeground="#111111",
                     padx=22, pady=9).pack(side="right")
        self._button(actions, "Cancel", dialog.destroy, bg=self.SIDEBAR,
                     activebackground="#2a2a2a", padx=18, pady=9).pack(side="right", padx=8)

    def show_about(self) -> None:
        messagebox.showinfo("About Local LLM Notepad",
                            "Local LLM Notepad\nA portable, private ChatGPT-style "
                            "interface for local GGUF models.")


def run_app() -> None:
    root = tk.Tk()
    ChatGUI(root)
    root.mainloop()
