"""
main.py — Site2MD CLI Entry Point
Usage: python main.py [URL] [OPTIONS]
"""
import asyncio
import os
import sys

# Reconfigure stdout/stderr to UTF-8 on Windows to avoid UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from tqdm import tqdm

from config import DEFAULT_SPLIT_LIMIT, VALID_FORMATS
from crawler.fetcher import AsyncFetcher
from crawler.sitemap import (
    crawl_recursive,
    discover_sitemap_url,
    load_urls_from_file,
    parse_sitemap,
)
from extractor.cleaner import clean_html, extract_title
from extractor.content import extract_markdown
from formatter.markdown import build_jsonl_record, build_page_block, build_toc, build_txt_block
from formatter.splitter import FileSplitter
from utils.logger import setup_logger

app = typer.Typer(
    name="site2md",
    help="Site2MD: Crawl website -> Markdown optimized for NotebookLM / RAG",
    add_completion=False,
)

logger = setup_logger()


# ---------------------------------------------------------------------------
# Helper: Discover URLs
# ---------------------------------------------------------------------------

def _discover_urls(
    url: str,
    depth: int,
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None
) -> list[str]:
    """Find URLs via sitemap or recursive crawl."""
    if depth > 0:
        typer.echo(f"[*] Recursive crawl mode (depth={depth})...")
        return crawl_recursive(url, depth, include, exclude)

    typer.echo("[*] Searching sitemap...")
    sitemap_url = discover_sitemap_url(url)

    if sitemap_url:
        try:
            import httpx
            resp = httpx.get(sitemap_url, timeout=15, follow_redirects=True)
            urls = parse_sitemap(resp.text)
            typer.echo(f"    OK  Sitemap: {len(urls)} URLs found")
            return urls
        except Exception as e:
            logger.warning(f"Sitemap read error: {e}")

    # Fallback: urls.txt
    typer.echo("    WARN  Sitemap failed. Trying urls.txt...")
    urls = load_urls_from_file("urls.txt")
    if not urls:
        typer.echo(typer.style(
            "    ERR  No sitemap found and no urls.txt. Create a urls.txt file with one URL per line.",
            fg=typer.colors.RED,
        ))
        raise typer.Exit(1)
    return urls


# ---------------------------------------------------------------------------
# Helper: Process một trang
# ---------------------------------------------------------------------------

def _process_page(
    result,
    selector: Optional[str],
    ai_clean: bool,
    ai_summary: bool,
    fmt: str,
    collected_at: str,
    min_length: int,
) -> Optional[dict]:
    """
    Xử lý kết quả fetch của một trang.
    Trả về dict {"title", "url", "content", "block", "record"} hoặc None nếu thất bại.
    """
    if result.skipped or not result.html:
        return None

    raw_html = result.html
    url = result.url

    # Extract title từ raw HTML (trước khi clean để giữ <title> tag)
    title = extract_title(raw_html)

    # Clean HTML
    cleaned_html = clean_html(raw_html, selector=selector)

    # Extract markdown content
    content = extract_markdown(cleaned_html, url=url, fallback_html=raw_html)
    if not content or len(content.strip()) < min_length:
        logger.warning(f"[SKIPPED] {url} — Nội dung quá ngắn hoặc rỗng (< {min_length} chars)")
        return None

    # AI refinement
    if ai_clean or ai_summary:
        from formatter.ai_refiner import clean_markdown, summarize_page

        summary = None
        if ai_summary:
            summary = summarize_page(title, content, url=url)

        if ai_clean:
            content = clean_markdown(content, url=url)
    else:
        summary = None

    # Build output theo format
    block = ""
    record = None

    if fmt == "md":
        block = build_page_block(title, url, content, collected_at, summary)
    elif fmt == "txt":
        block = build_txt_block(title, url, content)
    elif fmt == "jsonl":
        record = build_jsonl_record(title, url, content, collected_at)

    return {
        "title": title,
        "url": url,
        "content": content,
        "block": block,
        "record": record,
    }


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

async def _run(
    url: str,
    output: str,
    fmt: str,
    concurrency: int,
    use_cache: bool,
    split_limit: int,
    selector: Optional[str],
    depth: int,
    ai_clean: bool,
    ai_summary: bool,
    dry_run: bool,
    min_length: int,
    exclude: Optional[list[str]],
    include: Optional[list[str]],
):
    collected_at = datetime.now().astimezone().isoformat()

    # ── Phase 1: URL Discovery ──────────────────────────────────────────────
    urls = _discover_urls(url, depth, include, exclude)

    if not urls:
        typer.echo("    ERR  No URLs to crawl.")
        raise typer.Exit(1)

    # ── Filter Includes/Excludes ────────────────────────────────────────────
    # Include filtering: URL must contain at least one of the include patterns
    if include:
        filtered_urls_inc = []
        for u in urls:
            if any(inc in u for inc in include):
                filtered_urls_inc.append(u)
                
        included_count = len(filtered_urls_inc)
        typer.echo(f"[*] Kept {included_count} URLs matching --include patterns")
        urls = filtered_urls_inc
        
        if not urls:
            typer.echo("    ERR  No URLs left to crawl after applying includes.")
            raise typer.Exit(1)

    # Exclude filtering: URL must NOT contain any of the exclude patterns
    if exclude:
        filtered_urls_exc = []
        for u in urls:
            if not any(ex in u for ex in exclude):
                filtered_urls_exc.append(u)
        
        excluded_count = len(urls) - len(filtered_urls_exc)
        if excluded_count > 0:
            typer.echo(f"[*] Excluded {excluded_count} URLs matching --exclude patterns")
        urls = filtered_urls_exc

        if not urls:
            typer.echo("    ERR  No URLs left to crawl after applying excludes.")
            raise typer.Exit(1)

    # ── Dry Run ─────────────────────────────────────────────────────────────
    if dry_run:
        avg_page_chars = 5_000  # Ước tính bình quân
        est_chars = len(urls) * avg_page_chars
        est_parts = max(1, (est_chars // split_limit) + 1)
        est_time = len(urls) / concurrency * 1.5  # seconds ước tính

        typer.echo("\n" + "-" * 50)
        typer.echo(typer.style("[DRY RUN] Preview (khong crawl thuc te)", bold=True))
        typer.echo("-" * 50)
        typer.echo(f"  URL          : {url}")
        typer.echo(f"  Tong URL     : {len(urls)}")
        typer.echo(f"  Format       : {fmt}")
        typer.echo(f"  Split limit  : {split_limit:,} chars")
        import os
        base_name = os.path.basename(output)
        typer.echo(f"  Output       : {output}/{base_name}.{fmt}")
        typer.echo(f"  Est. size    : ~{est_chars:,} chars ({est_parts} part(s))")
        typer.echo(f"  Est. time    : ~{est_time:.0f}s")
        typer.echo("-" * 50)
        typer.echo("\n  URL list (first 10):")
        for u in urls[:10]:
            typer.echo(f"    - {u}")
        if len(urls) > 10:
            typer.echo(f"    ... and {len(urls) - 10} more URLs")
        typer.echo()
        return

    # -- Phase 2: Async Crawl ------------------------------------------------
    typer.echo(f"\n[*] Crawling {len(urls)} URLs (concurrency={concurrency})...")

    pages_data = []

    async with AsyncFetcher(concurrency=concurrency, use_cache=use_cache) as fetcher:
        with tqdm(total=len(urls), desc="Fetching", unit="page", ncols=80) as pbar:
            results = await fetcher.fetch_all(urls, progress_callback=pbar.update)

    typer.echo("\n[*] Extracting and formatting content...")

    seen_hashes = set()
    import hashlib

    for result in tqdm(results, desc="Processing", unit="page", ncols=80):
        page = _process_page(result, selector, ai_clean, ai_summary, fmt, collected_at, min_length)
        if page:
            # MD5 Deduplication
            content_hash = hashlib.md5(page["content"].encode('utf-8')).hexdigest()
            if content_hash in seen_hashes:
                logger.warning(f"[SKIPPED] {page['url']} — Nội dung hoàn toàn trùng lặp (Duplicate)")
                continue
            
            seen_hashes.add(content_hash)
            pages_data.append(page)

    typer.echo(f"\n  [OK] Extracted: {len(pages_data)}/{len(urls)} pages")
    skipped = len(urls) - len(pages_data)
    if skipped > 0:
        typer.echo(f"  [WARN] Skipped: {skipped} pages (see error.log)")

    if not pages_data:
        typer.echo("    ERR  No content extracted.")
        raise typer.Exit(1)

    # ── Phase 4: Write Output ───────────────────────────────────────────────
    typer.echo(f"\n[*] Writing to directory {output}/ ...")

    with FileSplitter(output, fmt=fmt, split_limit=split_limit) as splitter:
        # Ghi ToC (chỉ cho md và txt)
        if fmt == "md":
            toc_pages = [{"title": p["title"], "url": p["url"]} for p in pages_data]
            splitter.write_header(build_toc(toc_pages))
        elif fmt == "txt":
            splitter.write_header(f"SITE2MD — {url}\nThu thập: {collected_at}\n{'='*60}\n\n")

        # Ghi từng trang
        for page in pages_data:
            splitter.write_record(
                content=page["block"],
                record_dict=page["record"],
            )

    # ── Summary ─────────────────────────────────────────────────────────────
    typer.echo("\n" + "-" * 50)
    typer.echo(typer.style("[DONE] Complete!", fg=typer.colors.GREEN, bold=True))
    typer.echo(f"  Pages OK     : {len(pages_data)}")
    typer.echo(f"  Output files : {splitter.total_parts}")
    for f in splitter.output_files:
        size_kb = Path(f).stat().st_size / 1024
        typer.echo(f"    -> {f} ({size_kb:.1f} KB)")
    if skipped > 0:
        typer.echo(f"  Skipped      : {skipped} (see error.log)")
    typer.echo("-" * 50 + "\n")


# ---------------------------------------------------------------------------
# Typer CLI Definition
# ---------------------------------------------------------------------------

@app.command()
def main(
    url: str = typer.Argument(..., help="URL gốc cần crawl (VD: https://docs.example.com/)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Tên thư mục và prefix file (mặc định dựa theo URL)"),
    fmt: str = typer.Option("md", "--format", "-f", help=f"Format output: {', '.join(VALID_FORMATS)}"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Số request song song"),
    use_cache: bool = typer.Option(False, "--cache", help="Bật HTTP cache cục bộ (24h)"),
    split_limit: int = typer.Option(DEFAULT_SPLIT_LIMIT, "--split-limit", help="Giới hạn ký tự mỗi file"),
    selector: Optional[str] = typer.Option(None, "--selector", help="CSS selector chỉ định vùng content"),
    depth: int = typer.Option(0, "--depth", help="Crawl đệ quy (0=dùng sitemap, >0=depth crawl)"),
    ai_clean: bool = typer.Option(False, "--ai-clean", help="Dùng Deepseek AI làm sạch Markdown"),
    ai_summary: bool = typer.Option(False, "--ai-summary", help="Dùng AI tạo tóm tắt đầu mỗi trang"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview: liệt kê URLs và ước tính, không crawl"),
    min_length: int = typer.Option(50, "--min-length", help="Bỏ qua các trang có độ dài nội dung ngắn hơn mức này"),
    exclude: Optional[list[str]] = typer.Option(None, "--exclude", "-x", help="Bỏ qua các URL chứa chuỗi này (VD: -x zh-CN -x /tag/)"),
    include: Optional[list[str]] = typer.Option(None, "--include", "-i", help="CHỈ giữ lại các URL chứa chuỗi này (VD: -i /docs/)"),
):
    """
    Site2MD -- Crawl website and output Markdown optimized for NotebookLM / RAG.

    \b
    Examples:
      python main.py https://docs.example.com
      python main.py https://docs.example.com --format jsonl -o my_docs
      python main.py https://docs.example.com --depth 2 --selector "article.content"
      python main.py https://docs.example.com --dry-run
    """
    # Generate default output name based on URL if not provided
    if not output:
        import re
        from urllib.parse import urlparse
        parsed = urlparse(url)
        # e.g., docs.python.org/3/ -> docs.python.org_3
        base = parsed.netloc + parsed.path.replace('/', '_')
        base = re.sub(r'[^a-zA-Z0-9_-]', '_', base).strip('_')
        base = re.sub(r'_+', '_', base)
        output = base if base else "default_scrape"

    import os
    # Move all scrape folders inside the global 'output' folder
    output = os.path.join("output", output)

    # Validate format
    if fmt not in VALID_FORMATS:
        typer.echo(typer.style(
            f"    ERR  Invalid format: '{fmt}'. Choose from: {', '.join(VALID_FORMATS)}",
            fg=typer.colors.RED,
        ))
        raise typer.Exit(1)

    if not url.startswith(("http://", "https://")):
        typer.echo(typer.style("    ERR  URL must start with http:// or https://", fg=typer.colors.RED))
        raise typer.Exit(1)

    # Cảnh báo split limit không hợp lý
    if split_limit > 500_000 and fmt == "md":
        typer.echo(typer.style(
            f"  [WARN] NotebookLM limit is 500,000 chars/file. "
            f"Current split-limit ({split_limit:,}) may cause upload errors.",
            fg=typer.colors.YELLOW,
        ))

    typer.echo(typer.style("\n[*] Site2MD — Starting", bold=True))
    typer.echo(f"  Target : {url}")
    # Replace the redundant {output}/{output} log because output already contains the parent folder
    import os
    base_name = os.path.basename(output)
    typer.echo(f"  Format : {fmt}  |  Output: {output}/{base_name}.{fmt}")
    typer.echo(f"  Cache  : {'on' if use_cache else 'off'}  |  Concurrency: {concurrency}")
    if selector:
        typer.echo(f"  Selector: {selector}")
    if ai_clean or ai_summary:
        typer.echo(f"  AI     : {'clean ' if ai_clean else ''}{'summary' if ai_summary else ''}")

    # Run async pipeline
    asyncio.run(_run(
        url=url,
        output=output,
        fmt=fmt,
        concurrency=concurrency,
        use_cache=use_cache,
        split_limit=split_limit,
        selector=selector,
        depth=depth,
        ai_clean=ai_clean,
        ai_summary=ai_summary,
        dry_run=dry_run,
        min_length=min_length,
        exclude=exclude,
        include=include,
    ))


if __name__ == "__main__":
    app()
