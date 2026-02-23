"""
formatter/markdown.py — Tạo metadata block YAML front-matter và Table of Contents
"""
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Page block builder
# ---------------------------------------------------------------------------

def build_page_block(
    title: str,
    url: str,
    content: str,
    collected_at: Optional[str] = None,
    summary: Optional[str] = None,
) -> str:
    """
    Tạo block Markdown chuẩn NotebookLM cho một trang.

    Format:
    ---
    source_url: https://...
    title: "Page Title"
    collected_at: 2026-02-23T16:03:00+07:00
    ---
    # Page Title

    [tóm tắt nếu có]

    {nội dung}

    ---
    """
    if collected_at is None:
        collected_at = datetime.now().astimezone().isoformat()

    # Escape nháy kép trong title để YAML không bị lỗi
    safe_title = title.replace('"', '\\"')

    lines = [
        "---",
        f'source_url: {url}',
        f'title: "{safe_title}"',
        f"collected_at: {collected_at}",
        "---",
        "",
        f"# {title}",
        "",
    ]

    if summary:
        lines += [f"> **Tóm tắt:** {summary}", ""]

    lines += [content.strip(), "", "---", ""]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Table of Contents
# ---------------------------------------------------------------------------

def build_toc(pages: list[dict]) -> str:
    """
    Tạo Table of Contents từ danh sách pages.
    
    Args:
        pages: List of dicts với keys 'title' và 'url'.
    
    Returns:
        Markdown string của ToC.
    """
    lines = [
        "# 📑 MỤC LỤC",
        "",
        f"Tổng số trang: **{len(pages)}**",
        "",
    ]

    for i, page in enumerate(pages, 1):
        title = page.get("title", "Untitled")
        url = page.get("url", "")
        lines.append(f"{i}. [{title}]({url})")

    lines += ["", "---", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSONL formatter
# ---------------------------------------------------------------------------

def build_jsonl_record(
    title: str,
    url: str,
    content: str,
    collected_at: Optional[str] = None,
) -> dict:
    """Tạo dict record cho một trang (xuất ra JSONL)."""
    if collected_at is None:
        collected_at = datetime.now().astimezone().isoformat()
    return {
        "url": url,
        "title": title,
        "content": content.strip(),
        "collected_at": collected_at,
    }


# ---------------------------------------------------------------------------
# Plain text formatter
# ---------------------------------------------------------------------------

def build_txt_block(title: str, url: str, content: str) -> str:
    """Tạo block plain text cho một trang (format txt)."""
    separator = "=" * 60
    return f"{separator}\nSOURCE: {title}\nURL: {url}\n{separator}\n\n{content.strip()}\n\n"
