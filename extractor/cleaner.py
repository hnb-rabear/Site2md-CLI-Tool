"""
extractor/cleaner.py — BS4 DOM pre-processing trước khi extract content
"""
from typing import Optional

from bs4 import BeautifulSoup, Tag

from config import NOISE_CLASSES, NOISE_TAGS


def clean_html(html: str, selector: Optional[str] = None) -> str:
    """
    Làm sạch HTML trước khi đưa vào trafilatura/markdownify.
    
    Args:
        html: Raw HTML string.
        selector: CSS selector để chỉ lấy vùng content (VD: "article.main-content").
                  Nếu None, dùng heuristic tự động.
    
    Returns:
        HTML string đã làm sạch.
    """
    soup = BeautifulSoup(html, "lxml")

    # ----------------------------------------------------------------
    # Bước 1: Nếu có --selector, chỉ lấy vùng đó
    # ----------------------------------------------------------------
    if selector:
        target = soup.select_one(selector)
        if target:
            soup = BeautifulSoup(str(target), "lxml")
        # Nếu selector không match, giữ nguyên và xử lý tiếp

    # ----------------------------------------------------------------
    # Bước 2: Xóa các thẻ HTML là UI noise rõ ràng
    # ----------------------------------------------------------------
    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # ----------------------------------------------------------------
    # Bước 3: Xóa elements theo class/id chứa noise keywords
    # ----------------------------------------------------------------
    to_remove = []
    for element in soup.find_all(True):  # Tất cả elements
        if not isinstance(element, Tag):
            continue
        # BS4 4.14+: attrs có thể là None trên một số element đặc biệt
        if not hasattr(element, "attrs") or element.attrs is None:
            continue

        classes = element.get("class") or []
        element_id = element.get("id") or ""

        class_str = " ".join(classes).lower()

        should_remove = any(
            noise_kw in class_str or noise_kw in element_id.lower()
            for noise_kw in NOISE_CLASSES
        )

        if should_remove:
            to_remove.append(element)

    # Decompose sau khi duyệt xong để tránh modifying tree trong lúc iterate
    for element in to_remove:
        element.decompose()

    # ----------------------------------------------------------------
    # Bước 4: Chuẩn hóa links — chuyển relative thành absolute (nếu có thể)
    # ----------------------------------------------------------------
    # Trafilatura sẽ handle link resolution nếu truyền url vào

    return str(soup)


def extract_title(html: str) -> str:
    """Lấy title của trang từ <title> hoặc <h1>."""
    soup = BeautifulSoup(html, "lxml")
    
    # Ưu tiên <title>
    title_tag = soup.find("title")
    if title_tag and title_tag.get_text(strip=True):
        title = title_tag.get_text(strip=True)
        # Xóa suffix phổ biến như "| Docs", "- Site Name"
        for sep in [" | ", " - ", " — ", " :: "]:
            if sep in title:
                title = title.split(sep)[0].strip()
        return title
    
    # Fallback: <h1>
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    
    return "Untitled"
