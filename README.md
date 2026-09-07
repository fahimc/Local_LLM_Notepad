# Local LLM Notepad
Plug a USB drive and run a modern LLM on any PC **locally** with a double‑click. 

***No installation, no internet, no API, no Cloud computing, no GPU, no admin rights required.***

Local LLM Notepad is an open-source, offline plug-and-play app for running local large-language models. Drop the single bundled .exe onto a USB stick, walk up to any computer, and start chatting, brainstorming, or drafting documents. 


![Portable One‑File Build](Images/Screenshot1.png)

![combined_gif](Images/Combined_gif.gif)


# Why you’ll love it

🔌 Portable

Drop the one‑file EXE and your .gguf model onto a flash drive; run on any Windows PC without admin rights.

🪶 ChatGPT-style UI

Focused black chat workspace with a collapsible session sidebar, rounded user bubbles,
unboxed assistant answers, elapsed generation time, and a compact bottom composer.

💬 Live streaming and formatted code

Answers appear as they are generated. Markdown headings and bold text are rendered after
completion, while fenced code blocks get their own one-click Copy button.

📎 Attachments

Attach text-based files from the composer. Their contents are included with the prompt and the attached filenames remain visible as removable chips.

💾 Save/Load chats

Sessions are kept locally beside the app in `chat_sessions.json`, and individual conversations can be exported/imported as JSON. No cloud sync is used.

⚡ Llama.cpp inside

CPU‑only by default for max compatibility.

🎹 Hot‑keys

Enter sends, Shift + Enter adds a line, Ctrl + B toggles chat history, Ctrl + N starts a
new chat, Ctrl + O attaches files, Ctrl + Z stops, and Ctrl + P edits the system prompt.


# Quick Start

Build or copy `Notepad/dist/Local_LLM_Notepad-portable.exe`.

Copy the EXE and a compatible GGUF model (e.g. gemma-3-1b-it-Q4_K_M.gguf) onto your USB.

Double-click the EXE, then use File > Select Model to choose a compatible GGUF. The
runtime and its native libraries are embedded in the EXE; the model remains a separate file.

Need another model? Use File ▸ Select Model… and point to a different GGUF.


# Download links:


| File | Link | Notes |
|------|------|-------|
| **Local_LLM_Notepad-portable.exe** | Build output: `Notepad/dist/` | One-file app containing the UI and native inference runtime |
| **gemma-3-1b-it-Q4_K_M.gguf** | [Hugging Face](https://huggingface.co/ggml-org/gemma-3-1b-it-GGUF/tree/main) | Fast CPU model (~0.8 GB) we recommend for first-time users. Achieves ~20 tokens/second on an i7-10750H CPU  ![HF_screenshot](Images/HF_screenshot_2.png)|
| **Icon (optional)** | [Notepad icon PNG](https://upload.wikimedia.org/wikipedia/commons/c/c9/Windows_Notepad_icon.png) | Save as `Icon.png` next to the EXE and it will be used automatically |


# Feature Details

### Portable One‑File Build

![Portable One‑File Build](Images/Screenshot1.png)


### Streaming responses and copyable code

The bundled runtime streams final-answer text into the conversation and hides private K2
reasoning output. Fenced Markdown code is displayed in a dark code panel with a Copy button.

### Ctrl + Z to stop LLM generation

![CtrlZ](Images/CtrlZ.gif)

### Ctrl + F to find in chat history

![CtrlF](Images/CtrlF.gif)

### Ctrl + X to clear chat history

![CtrlX](Images/CtrlX.gif)

### Ctrl + P to edit system prompt anytime

![change_syst_prompt](Images/change_syst_prompt.gif)

### File ▸ Save/Load chat history

![Load_chat](Images/Load_chat.gif)


# (Optional) Building Your Own Portable EXE
### 1. Clone

$ git clone https://github.com/fahimc/Local_LLM_Notepad.git

$ cd Local_LLM_Notepad

### 2. Create a Python 3.12 environment and install the runtime

$ py -3.12 -m venv .venv && .\.venv\Scripts\activate

$ python -m pip install -r requirements.txt

The source build uses a current `llama-cpp-python` runtime so recent GGUF model architectures and chat templates are supported.

### 3. Bundle everything

$ pyinstaller --onefile --noconsole --additional-hooks-dir=. --add-binary "..\.vendor\llama.cpp-k2\build\bin\Release\*;k2_runtime" main.py

The `k2_runtime` folder must contain the compiled `model/K2Horizon` branch from the MBZUAI-IFM llama.cpp fork. This runtime also supports standard GGUF architectures; the K2-specific tokenizer workaround is applied only when the selected filename contains `K2-Horizon`.

### 4. Grab `dist/Local_LLM_Notepad-portable.exe`


