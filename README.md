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

🛠 Local tools

The model can list, read, and search files inside a folder you select, plus use a safe
calculator. Tool calls use the model's native chat format and results are returned through
proper tool messages. Tools are read-only and cannot escape the selected workspace.

🧩 Skills

Add familiar `skills/<skill-name>/SKILL.md` instruction packages beside the EXE. Reload and
enable skills from the Skills menu; each chat remembers its own enabled skills. Two starter
skills are bundled.

📎 Attachments

Attach text files, screenshots, photos, or PDFs from the composer. Images and scanned PDF
pages are translated to text locally with the CPU-only PP-OCRv6 Small model through ONNX
Runtime. No CUDA, GPU, internet connection, or separate OCR installation is required.

⚙️ Settings

Choose the GGUF chat model, attachment OCR model folder, tools workspace, system prompt,
and local-tools toggle from one Settings window. Choices are remembered beside the EXE.

💾 Save/Load chats

Sessions are kept locally beside the app in `chat_sessions.json`, and individual conversations can be exported/imported as JSON. No cloud sync is used.

⚡ Llama.cpp inside

CPU‑only by default for max compatibility.

🎹 Hot‑keys

Enter sends, Shift + Enter adds a line, Ctrl + B toggles chat history, Ctrl + N starts a
new chat, Ctrl + O attaches files, Ctrl + Z stops, and Ctrl + P opens Settings.


# Quick Start

Build or copy `Notepad/dist/Local_LLM_Notepad-portable.exe`.

Copy the EXE and a compatible GGUF model (e.g. gemma-3-1b-it-Q4_K_M.gguf) onto your USB.

Double-click the EXE, then use File > Select Model to choose a compatible GGUF. The
runtime and its native libraries are embedded in the EXE; the model remains a separate file.

Need another model? Open Settings and choose a different GGUF. The bundled OCR model works
without configuration; an external PP-OCRv6 Small model folder can also be selected there.


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

$ pyinstaller --clean --noconfirm --onefile --noconsole --name Local_LLM_Notepad-portable --additional-hooks-dir=. --exclude-module torch --exclude-module torchvision --exclude-module triton --exclude-module transformers --exclude-module tensorflow --add-binary "..\.vendor\llama.cpp-k2\build\bin\Release\*;k2_runtime" --add-data "skills;skills" main.py

The `k2_runtime` folder must contain `llama-completion.exe`, `llama-server.exe`, and their
native DLLs compiled from the MBZUAI-IFM `model/K2Horizon` branch. The server provides native
streaming tool calls and keeps the selected model loaded between prompts. The K2-specific
tokenizer workaround is applied only when the selected filename contains `K2-Horizon`.
RapidOCR, ONNX Runtime, PyMuPDF, and the PP-OCRv6 Small detector/classifier/recognizer files
are embedded in the same EXE for CPU-only image and scanned-PDF attachment reading.

### 4. Grab `dist/Local_LLM_Notepad-portable.exe`


