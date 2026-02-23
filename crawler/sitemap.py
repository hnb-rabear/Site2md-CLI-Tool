"""
crawler/sitemap.py — Sitemap discovery, parsing và recursive link crawling
"""
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
import typer
from bs4 import BeautifulSoup

from config import SKIP_EXTENSIONS, USER_AGENT
from utils.logger import setup_logger

logger = setup_logger()

# Headers dùng chung cho các request đồng bộ trong module này
_HEADERS = {"User-Agent": USER_AGENT}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_skippable(url: str) -> bool:
    """Trả True nếu URL trỏ tới file media/binary hoặc thuộc danh sách Regex bị chặn."""
    from config import IGNORE_URL_PATTERNS

    path = urlparse(url).path.lower()
    if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
        return True
        
    for pattern in IGNORE_URL_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return True
            
    return False


def _same_domain(url: str, base: str) -> bool:
    """Kiểm tra url có cùng domain với base không."""
    return urlparse(url).netloc == urlparse(base).netloc


# ---------------------------------------------------------------------------
# Sitemap Discovery
# ---------------------------------------------------------------------------

def discover_sitemap_url(base_url: str) -> Optional[str]:
    """
    Tìm URL của sitemap.xml theo thứ tự ưu tiên:
    1. robots.txt
    2. /sitemap.xml (mặc định)
    3. /sitemap_index.xml
    Trả None nếu không tìm thấy.
    """
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    # 1. Thử đọc robots.txt
    try:
        resp = httpx.get(f"{root}/robots.txt", headers=_HEADERS, timeout=10, follow_redirects=True)
        if resp.status_code == 200:
            for line in resp.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                    logger.info(f"  ✔ Sitemap từ robots.txt: {sitemap_url}")
                    return sitemap_url
    except Exception:
        pass

    # 2. Fallback /sitemap.xml
    for candidate in ["/sitemap.xml", "/sitemap_index.xml", "/sitemap/"]:
        url = root + candidate
        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
            if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                logger.info(f"  ✔ Sitemap tìm thấy tại: {url}")
                return url
        except Exception:
            pass

    logger.warning(f"  ✘ Không tìm thấy sitemap cho {base_url}")
    return None


# ---------------------------------------------------------------------------
# Sitemap Parsing (hỗ trợ Sitemap Index đệ quy)
# ---------------------------------------------------------------------------

def parse_sitemap(xml_content: str, fetched_urls: Optional[set] = None) -> list[str]:
    """
    Parse XML sitemap. Tự động xử lý cả <sitemapindex> (đệ quy) và <urlset> thông thường.
    Trả về danh sách URL content đã lọc và deduplicated.
    """
    if fetched_urls is None:
        fetched_urls = set()

    soup = BeautifulSoup(xml_content, "lxml-xml")
    urls = []

    # Trường hợp 1: Sitemap Index — chứa nhiều sitemap con
    sitemap_tags = soup.find_all("sitemap")
    if sitemap_tags:
        for tag in sitemap_tags:
            loc = tag.find("loc")
            if not loc:
                continue
            child_url = loc.get_text(strip=True)
            if child_url in fetched_urls:
                continue
            fetched_urls.add(child_url)
            try:
                resp = httpx.get(child_url, headers=_HEADERS, timeout=15, follow_redirects=True)
                if resp.status_code == 200:
                    urls.extend(parse_sitemap(resp.text, fetched_urls))
            except Exception as e:
                logger.warning(f"[SKIPPED] Sitemap con {child_url} — {e}")
        return urls

    # Trường hợp 2: Sitemap thông thường — chứa <url><loc>
    for loc_tag in soup.find_all("loc"):
        url = loc_tag.get_text(strip=True)
        if url and not _is_skippable(url):
            urls.append(url)

    return list(dict.fromkeys(urls))  # Deduplicate, giữ thứ tự


# ---------------------------------------------------------------------------
# Fallback: Đọc danh sách URL từ file urls.txt
# ---------------------------------------------------------------------------

def load_urls_from_file(filepath: str = "urls.txt") -> list[str]:
    """Đọc danh sách URL từ file text (mỗi dòng 1 URL)."""
    try:
        with open(filepath, encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        logger.info(f"  ✔ Đọc {len(urls)} URL từ {filepath}")
        return [u for u in urls if not _is_skippable(u)]
    except FileNotFoundError:
        logger.warning(f"  ✘ Không tìm thấy file {filepath}")
        return []


# ---------------------------------------------------------------------------
# Recursive Crawl (khi --depth > 0)
# ---------------------------------------------------------------------------

def crawl_recursive(
    base_url: str,
    max_depth: int,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None
) -> list[str]:
    """
    Crawl đệ quy từ base_url, theo tất cả internal links tới max_depth.
    Trả về danh sách URL đã deduplicated.
    """
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(base_url, 0)]
    found: list[str] = []

    while queue:
        url, depth = queue.pop(0)
        if url in visited or depth > max_depth:
            continue
        if _is_skippable(url):
            continue

        # Lọc sớm trong lúc duyệt cây để tránh crawl hàng ngàn link rác
        if exclude and any(ex in url for ex in exclude):
            continue
        if include and not any(inc in url for inc in include):
            # Lưu ý: Ở depth=0 (base_url), có thể ta vẫn phải process để lấy các link con
            # nhưng thông thường người dùng truyền URL gốc khớp với `include`.
            # Nếu base_url không khớp include, nhánh này bị dừng từ đầu.
            if depth > 0:
                continue

        visited.add(url)
        found.append(url)

        if depth >= max_depth:
            continue
            
        typer.echo(f"  > [Depth {depth}] Đang rà quét: {url} ...")

        try:
            resp = httpx.get(url, headers=_HEADERS, timeout=15, follow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                abs_url = urljoin(url, href)
                # Chỉ lấy internal links, bỏ fragment
                abs_url = abs_url.split("#")[0]
                if _same_domain(abs_url, base_url) and abs_url not in visited:
                    queue.append((abs_url, depth + 1))
        except Exception as e:
            logger.warning(f"[SKIPPED] {url} — {e}")

    logger.info(f"  ✔ Crawl đệ quy tìm thấy {len(found)} URLs (depth={max_depth})")
    return list(dict.fromkeys(found))
