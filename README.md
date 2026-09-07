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

Dark chat workspace with a session sidebar, user and assistant message cards, streaming answers, and a familiar bottom composer.

📎 Attachments

Attach text-based files from the composer. Their contents are included with the prompt and the attached filenames remain visible as removable chips.

🔍 Source‑word under‑lining

Every word or number you wrote in your prompt is automatically bold‑underlined in the model’s reply. Ctrl+left click on them to view them in a separate window. Handy for fact‑checking summaries, tables, or data extractions.

💾 Save/Load chats

Sessions are kept locally beside the app in `chat_sessions.json`, and individual conversations can be exported/imported as JSON. No cloud sync is used.

⚡ Llama.cpp inside

CPU‑only by default for max compatibility.

🎹 Hot‑keys

Ctrl + Enter to send, Ctrl + O to attach files, Ctrl + Z to stop, and Ctrl + P to edit the system prompt.


# Quick Start

Download Local_LLM_Notepad-portable.exe from the Releases page.

Copy the EXE and a compatible GGUF model (e.g. gemma-3-1b-it-Q4_K_M.gguf) onto your USB.

Double‑click the EXE on any Windows computer. First launch caches the model into RAM; subsequent prompts stream instantly.

Need another model? Use File ▸ Select Model… and point to a different GGUF.


# Download links:


| File | Link | Notes |
|------|------|-------|
| **Local_LLM_Notepad-portable.exe** | [Direct download (v1.0.1)](https://github.com/runzhouye/Local_LLM_Notepad/releases/tag/v1.0.1) | ~45 MB, contains everything needed to run LLM on Windows computer |
| **gemma-3-1b-it-Q4_K_M.gguf** | [Hugging Face](https://huggingface.co/ggml-org/gemma-3-1b-it-GGUF/tree/main) | Fast CPU model (~0.8 GB) we recommend for first-time users. Achieves ~20 tokens/second on an i7-10750H CPU  ![HF_screenshot](Images/HF_screenshot_2.png)|
| **Icon (optional)** | [Notepad icon PNG](https://upload.wikimedia.org/wikipedia/commons/c/c9/Windows_Notepad_icon.png) | Save as `Icon.png` next to the EXE and it will be used automatically |


# Feature Details

### Portable One‑File Build

![Portable One‑File Build](Images/Screenshot1.png)


### Automated Source Highlighting (Ctrl + click)

Every word, number you used in the prompt is bold‑underlined in the LLM answer.  

Ctrl + click any under‑lined word to open a side window with every single prompt that contained it—great for tracing sources.

![bold_text_demo](Images/bold_text_demo.gif)

### Ctrl + S to Send text to LLM

![CtrlS](Images/CtrlS.gif)

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

$ git clone https://github.com/runzhouye/Local_LLM_Notepad.git

$ cd Local_LLM_Notepad

### 2. Create an environment and install the runtime

$ python -m venv .venv && .\.venv\Scripts\activate

$ python -m pip install -r requirements.txt

The source build uses `llama-cpp-python` directly. The requirements file pins a version compatible with the older Python runtime used by the original portable build. If you use a newer Python version, you can remove the version pin and install the latest `llama-cpp-python` instead.

### 3. Bundle everything

$ pyinstaller --onefile --noconsole --additional-hooks-dir=. main.py

### 4. Grab dist/Local_LLM_Notepad.exe (≈45 MB)


