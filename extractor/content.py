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
            include_links=False,    # Bỏ link để tránh rác token
            include_images=False,   # Không cần ảnh trong NotebookLM output
            no_fallback=False,
            favor_precision=True,   # Tránh lấy rác từ sidebar/footer/nav
            favor_recall=False,     # Không ráng lấy toàn bộ text mồ côi
        )
        if result and len(result.strip()) >= 100:
            return _clean_markdown(result)
    except Exception as e:
        logger.warning(f"trafilatura error cho {url}: {e}")

    # ----------------------------------------------------------------
    # Layer 2: markdownify — tốt hơn cho trang có nhiều code/tables
    # ----------------------------------------------------------------
    try:
        # Quan trọng: CHỈ dùng `html` (đã qua clean_html), KHÔNG DÙNG raw fallback_html vì
        # nó sẽ chứa hàng tá JS payload và UI noise chưa bị decompose.
        source_html = html
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
    # Xóa dư thừa markdown table artifacts (thường rớt lại khi include_links=False)
    # Xóa các dòng chỉ chứa ký tự `|` và khoảng trắng
    lines = [line.rstrip() for line in text.splitlines()]
    clean_lines = []
    for line in lines:
        # Bỏ qua dòng chỉ chứa pipe
        if re.match(r"^[\s\|]+$", line):
            continue
        clean_lines.append(line)
        
    text = "\n".join(clean_lines)

    # Giảm nhiều blank lines liên tiếp thành tối đa 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Đảm bảo blank line trước code block
    text = re.sub(r"([^\n])\n(```)", r"\1\n\n\2", text)
    # Đảm bảo blank line sau code block
    text = re.sub(r"(```)\n([^\n])", r"\1\n\n\2", text)

    return text.strip()
