# CPU attachment OCR and unified settings

## User outcome

- Replaced Falcon-OCR as the app attachment engine because Falcon's FlexAttention/Triton
  runtime is CUDA-only and conflicts with the CPU-only portable requirement.
- Added CPU-only PP-OCRv6 Small through RapidOCR and ONNX Runtime for images and scanned PDFs.
- Added a full Settings window for changing the GGUF chat model, OCR model folder, tools
  workspace, system prompt, and tools toggle.

## Implementation

- `Notepad/ocr_utils.py` lazily loads RapidOCR, directly reads text/code files, OCRs common
  image formats, and renders up to 25 PDF pages with PyMuPDF before OCR. Attachment work runs
  on the existing generation worker so the UI does not freeze.
- Three ONNX files can be supplied from a selected folder or loaded from the EXE's bundled
  RapidOCR data. The validated external copy is at `I:\models\PP-OCRv6-small`.
- Settings persist locally in ignored `app_settings.json`. On this machine the external OCR
  folder is selected by default when present; other machines automatically use the bundled
  model.
- `Notepad/main.py` now supports `--ocr-self-test MODEL_DIR IMAGE OUTPUT_JSON`.
- `Notepad/hook-rapidocr.py` packages RapidOCR data and the ONNX backend. Build arguments
  exclude optional torch, torchvision, triton, transformers, and tensorflow modules to keep
  the portable build CPU-only.

## Validation

- Source OCR on `Images/Screenshot1.png`: passed and recovered all expected filenames.
- Compiled OCR with `I:\models\PP-OCRv6-small`: passed.
- Compiled OCR with the model embedded in the EXE: passed.
- Six `unittest` agent/tool/skill tests: passed.
- Compiled agent self-test: passed (`calculator=42`, two bundled skills discovered).
- Compiled chat self-test with `I:\Model\K2-Horizon-1B-BF16.gguf`: passed (`READY`, 6 chunks).
- Compiled native tool self-test: passed (2 tool calls and README title returned).
- Settings-window Tk construction test: passed with chat-model, OCR-model, and workspace
  selectors present.
- Completion-race regression: passed; a queued completion event now waits for the worker
  thread to exit before the next send is allowed.
- Rebuilt EXE chat self-test: passed (`READY`, 6 chunks).
- Rebuilt EXE OCR self-test with external PP-OCRv6 folder: passed.

## Artifact

- `Notepad/dist/Local_LLM_Notepad-portable.exe`
- Size: 160,997,947 bytes
- SHA-256: `C964F74604EA4DF37A8B6D0FA9225F18FD941C9136BA214281419D5A78454BC2`

## Follow-up bug fix

- Fixed the second-send race in `Notepad/chat_gui.py`: the GUI no longer renders the response
  as complete while the generation worker is still technically alive.

## Falcon note

- The previously requested Falcon-OCR repository remains at `I:\models\Falcon-OCR` with its
  official weight checksum verified, but it is not used or bundled. Its current custom model
  code requires CUDA FlexAttention/Triton, so it is unsuitable as the CPU-only default.
