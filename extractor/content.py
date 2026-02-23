"""
extractor/content.py — Content extraction pipeline: trafilatura + markdownify fallback
"""
import re
from typing import Optional

import trafilatura
from markdownify import markdownify as md

from utils.logger import setup_logger

logger = setup_logger()


def extract_markdown(html: str, url: str = "", fallback_html: str = "") -> str:
    """
    Extract nội dung chính từ HTML và trả về Markdown string.

    Pipeline:
    1. Thử trafilatura với full options (include_formatting, tables, links)
    2. Nếu trafilatura trả về quá ít (< 100 chars), fallback sang markdownify
       trên cleaned HTML để đảm bảo code blocks và tables được giữ nguyên.

    Args:
        html: HTML đã được làm sạch bởi cleaner.py
        url: URL gốc (dùng cho trafilatura link resolution)
        fallback_html: HTML thô gốc (fallback nếu cần)

    Returns:
        Markdown string.
    """
    # ----------------------------------------------------------------
    # Layer 1: Trafilatura — tốt nhất cho body text, prose content
    # ----------------------------------------------------------------
    try:
        result = trafilatura.extract(
            html,
            url=url or None,
            output_format="markdown",
            include_formatting=True,
            include_tables=True,
            include_links=True,
            include_images=False,   # Không cần ảnh trong NotebookLM output
            no_fallback=False,
            favor_precision=False,
            favor_recall=True,      # Ưu tiên lấy nhiều hơn bỏ sót
        )
        if result and len(result.strip()) >= 100:
            return _clean_markdown(result)
    except Exception as e:
        logger.warning(f"trafilatura error cho {url}: {e}")

    # ----------------------------------------------------------------
    # Layer 2: markdownify — tốt hơn cho trang có nhiều code/tables
    # ----------------------------------------------------------------
    try:
        source_html = fallback_html if fallback_html else html
        result = md(
            source_html,
            heading_style="ATX",        # Dùng # ## ### thay vì underline
            bullets="-",
            code_language_callback=_detect_code_language,
            strip=["img", "script", "style"],
            convert_links=False,        # Bỏ markdown links trong output NotebookLM
        )
        if result and len(result.strip()) >= 50:
            return _clean_markdown(result)
    except Exception as e:
        logger.warning(f"markdownify error cho {url}: {e}")

    logger.warning(f"[WARN] Không extract được nội dung từ {url}")
    return ""


def _detect_code_language(el) -> str:
    """Detect ngôn ngữ code từ class attribute của <code> tag."""
    classes = el.get("class", [])
    for cls in classes:
        # Patterns: language-python, lang-js, highlight-ruby, etc.
        match = re.match(r"(?:language|lang|highlight)[_-](\w+)", cls)
        if match:
            return match.group(1)
    return ""


def _clean_markdown(text: str) -> str:
    """
    Post-process Markdown để chuẩn hóa output:
    - Xóa nhiều dòng trắng liên tiếp (> 2)
    - Xóa trailing whitespace
    - Đảm bảo code blocks có blank line trước/sau
    """
    # Xóa trailing whitespace mỗi dòng
    lines = [line.rstrip() for line in text.splitlines()]
    text = "\n".join(lines)

    # Giảm nhiều blank lines liên tiếp thành tối đa 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Đảm bảo blank line trước code block
    text = re.sub(r"([^\n])\n(```)", r"\1\n\n\2", text)
    # Đảm bảo blank line sau code block
    text = re.sub(r"(```)\n([^\n])", r"\1\n\n\2", text)

    return text.strip()
