from __future__ import annotations

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, List, Tuple

__all__ = ["ChatGUI", "run_app"]


class ChatGUI:
    """A portable, ChatGPT-inspired front end for the local model."""

    BG = "#212121"
    SIDEBAR = "#171717"
    PANEL = "#2f2f2f"
    USER = "#343541"
    TEXT = "#ececec"
    MUTED = "#a7a7a7"
    ACCENT = "#10a37f"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Local LLM Notepad")
        self.root.geometry("1180x760")
        self.root.minsize(850, 560)
        self.root.configure(bg=self.BG)
        self.system_prompt = "You are a helpful assistant."
        self.model_path = "gemma-3-1b-it-Q4_K_M.gguf"
        self.session_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "chat_sessions.json")
        self.sessions: list[dict[str, Any]] = []
        self.current_session: dict[str, Any] | None = None
        self.history_data: list[dict[str, str]] = []
        self.attachments: list[str] = []
        self.queue: queue.Queue[str | None] = queue.Queue()
        self.gen_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.assistant_label: tk.Label | None = None
        self.assistant_text = ""
        self._build_styles()
        self._build_menu()
        self._build_layout()
        self._load_sessions()
        if self.sessions:
            self.current_session = self.sessions[0]
            self.title_label.config(text=self.current_session["title"])
            self._refresh_sessions()
            self._render_chat()
        else:
            self.new_chat()

    def _build_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Dark.TScrollbar", troughcolor=self.BG, background="#555555", bordercolor=self.BG)

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root, tearoff=0, bg=self.PANEL, fg=self.TEXT,
                       activebackground="#555555", activeforeground="white")
        file_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        file_menu.add_command(label="Select Model...", command=self.select_model)
        file_menu.add_command(label="Save Current Chat...", command=self.save_chat)
        file_menu.add_command(label="Load Chat...", command=self.load_chat)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menu.add_cascade(label="File", menu=file_menu)
        edit = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        edit.add_command(label="Send", accelerator="Ctrl+Enter", command=self.on_send)
        edit.add_command(label="Attach Files...", accelerator="Ctrl+O", command=self.attach_files)
        edit.add_command(label="Edit System Prompt...", accelerator="Ctrl+P", command=self.edit_system_prompt)
        edit.add_separator()
        edit.add_command(label="Stop Generation", accelerator="Ctrl+Z", command=self.on_stop)
        menu.add_cascade(label="Edit", menu=edit)
        help_menu = tk.Menu(menu, tearoff=0, bg=self.PANEL, fg=self.TEXT)
        help_menu.add_command(label="About", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def _button(self, parent: tk.Widget, text: str, command, **kwargs) -> tk.Button:
        defaults = dict(bg=self.PANEL, fg=self.TEXT, activebackground="#454545",
                        activeforeground="white", relief="flat", bd=0, cursor="hand2",
                        padx=12, pady=7, font=("Segoe UI", 10))
        defaults.update(kwargs)
        return tk.Button(parent, text=text, command=command, **defaults)

    def _build_layout(self) -> None:
        shell = tk.Frame(self.root, bg=self.BG)
        shell.pack(fill="both", expand=True)
        sidebar = tk.Frame(shell, bg=self.SIDEBAR, width=270)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="Local LLM", bg=self.SIDEBAR, fg="white",
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(fill="x", padx=18, pady=(20, 14))
        self._button(sidebar, "+  New chat", self.new_chat, bg=self.SIDEBAR,
                     activebackground="#2a2a2a", anchor="w", font=("Segoe UI", 10, "bold")).pack(fill="x", padx=10)
        tk.Label(sidebar, text="YOUR CHATS", bg=self.SIDEBAR, fg="#777777",
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", padx=18, pady=(24, 8))
        list_frame = tk.Frame(sidebar, bg=self.SIDEBAR)
        list_frame.pack(fill="both", expand=True, padx=8)
        self.session_list = tk.Listbox(list_frame, bg=self.SIDEBAR, fg="#d1d1d1",
                                       selectbackground="#343541", selectforeground="white",
                                       relief="flat", bd=0, highlightthickness=0,
                                       activestyle="none", font=("Segoe UI", 10), exportselection=False)
        self.session_list.pack(fill="both", expand=True)
        self.session_list.bind("<<ListboxSelect>>", self._select_session)
        bottom = tk.Frame(sidebar, bg=self.SIDEBAR)
        bottom.pack(fill="x", padx=10, pady=14)
        self._button(bottom, "⚙  Settings", self.edit_system_prompt, bg=self.SIDEBAR,
                     activebackground="#2a2a2a", anchor="w").pack(fill="x")
        tk.Label(sidebar, text="Local and private", bg=self.SIDEBAR, fg="#777777",
                 font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=18, pady=(0, 14))

        main = tk.Frame(shell, bg=self.BG)
        main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(main, bg=self.BG, height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        self.title_label = tk.Label(header, text="New chat", bg=self.BG, fg="white",
                                    font=("Segoe UI", 12, "bold"), anchor="w")
        self.title_label.pack(side="left", padx=26)
        self.model_label = tk.Label(header, text="gemma-3-1b-it", bg=self.BG, fg=self.MUTED,
                                    font=("Segoe UI", 9), anchor="e")
        self.model_label.pack(side="right", padx=26)

        chat_outer = tk.Frame(main, bg=self.BG)
        chat_outer.pack(fill="both", expand=True, padx=12)
        self.chat_canvas = tk.Canvas(chat_outer, bg=self.BG, highlightthickness=0, bd=0)
        scroll = tk.Scrollbar(chat_outer, orient="vertical", command=self.chat_canvas.yview,
                              bg="#555555", troughcolor=self.BG, activebackground="#777777",
                              relief="flat", bd=0, highlightthickness=0)
        self.chat_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.chat_canvas.pack(side="left", fill="both", expand=True)
        self.chat_frame = tk.Frame(self.chat_canvas, bg=self.BG)
        self.chat_window = self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw")
        self.chat_frame.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.bind("<Configure>", lambda e: self.chat_canvas.itemconfigure(self.chat_window, width=e.width))

        composer = tk.Frame(main, bg=self.BG)
        composer.pack(fill="x", padx=80, pady=(8, 28))
        self.attachment_row = tk.Frame(composer, bg=self.BG)
        self.attachment_row.pack(fill="x")
        box = tk.Frame(composer, bg="#303030", highlightbackground="#555555", highlightthickness=1)
        box.pack(fill="x")
        self.input_text = tk.Text(box, height=3, wrap="word", bg="#303030", fg=self.TEXT,
                                  insertbackground="white", relief="flat", bd=0,
                                  highlightthickness=0, padx=14, pady=11, font=("Segoe UI", 11))
        tools = tk.Frame(box, bg="#303030")
        tools.pack(side="right", fill="y", padx=7, pady=7)
        self.attach_button = self._button(tools, "Attach", self.attach_files, bg="#303030",
                                          activebackground="#454545", width=7, height=1,
                                          font=("Segoe UI", 9), padx=8, pady=5)
        self.attach_button.pack(side="left")
        self.send_button = self._button(tools, "Send", self.on_send, bg=self.ACCENT,
                                        activebackground="#0d8c6d", width=7, height=1,
                                        font=("Segoe UI", 9, "bold"), padx=8, pady=5)
        self.send_button.pack(side="left", padx=(5, 0))
        # Pack fixed-width controls before the expanding editor so Tk always
        # reserves space for both buttons, even at the minimum window width.
        self.input_text.pack(side="left", fill="both", expand=True)
        tk.Label(composer, text="Local LLM Notepad can make mistakes. Check important information.",
                 bg=self.BG, fg="#777777", font=("Segoe UI", 8)).pack(pady=(8, 0))
        self.root.bind("<Control-Return>", lambda e: self.on_send())
        self.root.bind("<Control-o>", lambda e: self.attach_files())
        self.root.bind("<Control-p>", lambda e: self.edit_system_prompt())
        self.root.bind("<Control-z>", lambda e: self.on_stop())

    def new_chat(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            return
        session = {"title": "New chat", "messages": []}
        self.sessions.insert(0, session)
        self.current_session = session
        self.history_data = []
        self.attachments.clear()
        self._refresh_sessions()
        self._render_chat()
        self._persist_sessions()
        self.input_text.focus_set()

    def _load_sessions(self) -> None:
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.sessions = [s for s in data if isinstance(s, dict) and isinstance(s.get("messages"), list)]
        except (OSError, json.JSONDecodeError):
            self.sessions = []

    def _persist_sessions(self) -> None:
        try:
            temp_path = self.session_file + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.session_file)
        except OSError:
            # The app remains usable on read-only media such as protected USB drives.
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
        self.history_data = []
        messages = self.current_session["messages"]
        for i, message in enumerate(messages):
            if message["role"] == "user" and i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                self.history_data.append({"user": message["content"], "assistant": messages[i + 1]["content"]})
        self.title_label.config(text=self.current_session["title"])
        self._render_chat()

    def _render_chat(self) -> None:
        for child in self.chat_frame.winfo_children():
            child.destroy()
        if not self.current_session or not self.current_session["messages"]:
            welcome = tk.Frame(self.chat_frame, bg=self.BG)
            welcome.pack(fill="x", pady=(110, 30))
            tk.Label(welcome, text="How can I help you today?", bg=self.BG, fg="white",
                     font=("Segoe UI", 23, "bold")).pack()
            tk.Label(welcome, text="Ask a question or attach a document to get started.", bg=self.BG,
                     fg=self.MUTED, font=("Segoe UI", 11)).pack(pady=(9, 0))
        else:
            for message in self.current_session["messages"]:
                self._add_message(message["role"], message["content"])
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)
        self._refresh_attachment_row()

    def _add_message(self, role: str, content: str) -> tk.Label:
        row = tk.Frame(self.chat_frame, bg=self.BG)
        row.pack(fill="x", pady=7)
        if role == "user":
            card = tk.Frame(row, bg=self.USER)
            card.pack(anchor="e", padx=(90, 16))
            label = tk.Label(card, text=content, bg=self.USER, fg=self.TEXT, justify="left",
                             anchor="w", wraplength=650, padx=16, pady=12, font=("Segoe UI", 11))
        else:
            avatar = tk.Label(row, text="✦", bg=self.ACCENT, fg="white", width=2, height=1,
                              font=("Segoe UI", 11, "bold"))
            avatar.pack(side="left", anchor="n", padx=(20, 12))
            card = tk.Frame(row, bg=self.BG)
            card.pack(side="left", fill="x", expand=True, padx=(0, 40))
            label = tk.Label(card, text=content, bg=self.BG, fg=self.TEXT, justify="left",
                             anchor="w", wraplength=740, padx=0, pady=4, font=("Segoe UI", 11))
        label.pack()
        return label

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
            chip = tk.Frame(self.attachment_row, bg="#343541")
            chip.pack(side="left", padx=(0, 6), pady=(0, 5))
            tk.Label(chip, text="📎 " + os.path.basename(path), bg="#343541", fg=self.TEXT,
                     font=("Segoe UI", 9), padx=8, pady=4).pack(side="left")
            tk.Button(chip, text="×", command=lambda p=path: self._remove_attachment(p),
                      bg="#343541", fg=self.MUTED, activebackground="#343541", activeforeground="white",
                      relief="flat", bd=0, font=("Segoe UI", 11)).pack(side="left", padx=(0, 4))

    def _remove_attachment(self, path: str) -> None:
        self.attachments.remove(path)
        self._refresh_attachment_row()

    def _attachment_context(self) -> str:
        chunks = []
        for path in self.attachments:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read(12000)
                chunks.append(f"\n\n--- Attached file: {os.path.basename(path)} ---\n{text}")
            except Exception:
                chunks.append(f"\n\n[Attached file: {os.path.basename(path)}; contents could not be read as text]")
        return "".join(chunks)

    def on_send(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            return
        prompt = self.input_text.get("1.0", tk.END).strip()
        if not prompt or not self.current_session:
            return
        prompt_for_model = prompt + self._attachment_context()
        previous: list[Tuple[str, str]] = []
        messages = self.current_session["messages"]
        for i, message in enumerate(messages):
            if message["role"] == "user" and i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                previous.append((message["content"], messages[i + 1]["content"]))
        self.current_session["messages"].append({"role": "user", "content": prompt})
        if self.current_session["title"] == "New chat":
            self.current_session["title"] = prompt[:34] + ("…" if len(prompt) > 34 else "")
        self.history_data.append({"user": prompt_for_model, "assistant": ""})
        self.input_text.delete("1.0", tk.END)
        self.attachments.clear()
        self._refresh_sessions()
        self._render_chat()
        self._add_message("assistant", "")
        row = self.chat_frame.winfo_children()[-1]
        card = row.winfo_children()[-1]
        self.assistant_label = card.winfo_children()[-1]
        self.assistant_text = ""
        self.stop_event.clear()
        self.queue = queue.Queue()
        self.gen_thread = threading.Thread(target=self._worker_generate,
                                           args=(prompt_for_model, previous, self.current_session), daemon=True)
        self.gen_thread.start()
        self.chat_canvas.after(50, self._process_queue)

    def _worker_generate(self, prompt: str, history: List[Tuple[str, str]], session: dict[str, Any]) -> None:
        last = ""
        try:
            # Keep the UI launchable even when the optional local-model runtime
            # is not present yet; the portable build bundles it separately.
            from llm_utils import respond

            for full in respond(prompt, history, model=self.model_path, system_message=self.system_prompt):
                if self.stop_event.is_set():
                    break
                self.queue.put(full[len(last):])
                last = full
        except ModuleNotFoundError as exc:
            missing = exc.name or "a required package"
            last = (f"Model runtime is not installed ({missing}).\n\n"
                    "Open a terminal in the app folder and run:\n"
                    "python -m pip install -r requirements.txt")
            self.queue.put(last)
        except Exception as exc:
            last += f"\n\nError: {exc}"
            self.queue.put(last)
        finally:
            session["messages"].append({"role": "assistant", "content": last})
            self.history_data[-1]["assistant"] = last
            self.queue.put(None)

    def _process_queue(self) -> None:
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self.assistant_label = None
                self._refresh_sessions()
                self._persist_sessions()
                return
            self.assistant_text += item
            if self.assistant_label:
                self.assistant_label.config(text=self.assistant_text)
            self.chat_canvas.update_idletasks()
            self.chat_canvas.yview_moveto(1.0)
        if self.gen_thread and self.gen_thread.is_alive():
            self.chat_canvas.after(50, self._process_queue)

    def on_stop(self) -> None:
        if self.gen_thread and self.gen_thread.is_alive():
            self.stop_event.set()

    def select_model(self) -> None:
        path = filedialog.askopenfilename(title="Select GGUF model", filetypes=[("GGUF Model", "*.gguf"), ("All files", "*.*")])
        if path:
            self.model_path = path
            self.model_label.config(text=os.path.basename(path))

    def save_chat(self) -> None:
        if not self.current_session or not self.current_session["messages"]:
            messagebox.showinfo("Save Chat", "Nothing to save yet.")
            return
        path = filedialog.asksaveasfilename(title="Save Chat", defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.current_session["messages"], f, ensure_ascii=False, indent=2)

    def load_chat(self) -> None:
        path = filedialog.askopenfilename(title="Load Chat", filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            messages = data if isinstance(data, list) else data.get("messages", [])
            if not all(isinstance(m, dict) and m.get("role") in ("user", "assistant") for m in messages):
                raise ValueError("Invalid chat format")
            session = {"title": next((m["content"][:34] for m in messages if m["role"] == "user"), "Loaded chat"), "messages": messages}
            self.sessions.insert(0, session)
            self.current_session = session
            self._refresh_sessions()
            self._render_chat()
            self._persist_sessions()
        except Exception as exc:
            messagebox.showerror("Load Chat", f"Could not load chat:\n{exc}")

    def edit_system_prompt(self) -> None:
        prompt = simpledialog.askstring("System prompt", "Instructions for the assistant:", initialvalue=self.system_prompt, parent=self.root)
        if prompt is not None:
            self.system_prompt = prompt.strip() or "You are a helpful assistant."

    def show_about(self) -> None:
        messagebox.showinfo("About Local LLM Notepad", "Local LLM Notepad\nA portable, private ChatGPT-style interface for local GGUF models.")


def run_app() -> None:
    root = tk.Tk()
    ChatGUI(root)
    root.mainloop()
