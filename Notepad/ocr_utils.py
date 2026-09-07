from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterable


IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
TEXT_EXTENSIONS = {
    ".bat", ".cfg", ".conf", ".cpp", ".css", ".csv", ".h", ".hpp", ".htm",
    ".html", ".ini", ".java", ".js", ".json", ".log", ".md", ".py", ".rst",
    ".sh", ".toml", ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
MODEL_FILES = (
    "PP-OCRv6_det_small.onnx",
    "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
    "PP-OCRv6_rec_small.onnx",
)

_engines: dict[str, object] = {}


def validate_model_dir(model_dir: str) -> tuple[bool, str]:
    if not model_dir:
        return True, "Built-in PP-OCRv6 Small"
    folder = Path(model_dir)
    missing = [name for name in MODEL_FILES if not (folder / name).is_file()]
    if missing:
        return False, "Missing: " + ", ".join(missing)
    return True, "PP-OCRv6 Small (CPU)"


def _engine(model_dir: str):
    key = os.path.abspath(model_dir) if model_dir else "__bundled__"
    if key in _engines:
        return _engines[key]

    from rapidocr import RapidOCR

    params = {"Global.log_level": "error"}
    if model_dir:
        folder = Path(model_dir)
        valid, detail = validate_model_dir(model_dir)
        if not valid:
            raise FileNotFoundError(f"Invalid OCR model folder. {detail}")
        params.update({
            "Det.model_path": str(folder / MODEL_FILES[0]),
            "Cls.model_path": str(folder / MODEL_FILES[1]),
            "Rec.model_path": str(folder / MODEL_FILES[2]),
        })
    engine = RapidOCR(params=params)
    _engines[key] = engine
    return engine


def _ocr_images(images: Iterable[object], model_dir: str,
                status: Callable[[str], None] | None = None) -> str:
    engine = _engine(model_dir)
    pages: list[str] = []
    for page_number, image in enumerate(images, start=1):
        if status:
            status(f"Reading page {page_number} with CPU OCR…")
        result = engine(image)
        text = "\n".join(result.txts or ())
        pages.append(f"[Page {page_number}]\n{text}" if page_number > 1 else text)
    return "\n\n".join(pages).strip()


def extract_file_text(path: str, model_dir: str = "",
                      status: Callable[[str], None] | None = None,
                      max_chars: int = 30000, max_pdf_pages: int = 25) -> str:
    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix in TEXT_EXTENSIONS:
        return source.read_text(encoding="utf-8", errors="ignore")[:max_chars]

    if suffix in IMAGE_EXTENSIONS:
        if status:
            status(f"Reading {source.name} with CPU OCR…")
        return _ocr_images([str(source)], model_dir, status)[:max_chars]

    if suffix == ".pdf":
        import fitz

        document = fitz.open(source)
        try:
            page_count = min(document.page_count, max_pdf_pages)
            images = []
            for index in range(page_count):
                page = document.load_page(index)
                images.append(page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False).pil_image())
            text = _ocr_images(images, model_dir, status)
            if document.page_count > page_count:
                text += f"\n\n[Only the first {page_count} pages were read.]"
            return text[:max_chars]
        finally:
            document.close()

    # Office and other unknown formats may still contain usable plain text.
    return source.read_text(encoding="utf-8", errors="ignore")[:max_chars]


def attachment_context(paths: list[str], model_dir: str = "",
                       status: Callable[[str], None] | None = None) -> str:
    chunks: list[str] = []
    for path in paths:
        name = os.path.basename(path)
        try:
            if status:
                status(f"Reading {name}…")
            content = extract_file_text(path, model_dir, status)
            if not content.strip():
                content = "[No readable text was found.]"
            chunks.append(f"\n\n--- Attached file: {name} ---\n{content}")
        except Exception as exc:
            chunks.append(f"\n\n[Attached file: {name}; could not be read: {exc}]")
    return "".join(chunks)
