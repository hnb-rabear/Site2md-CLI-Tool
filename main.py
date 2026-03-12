"""
main.py — Site2MD CLI Entry Point
Usage: python main.py [URL] [OPTIONS]
"""
import asyncio
import hashlib
import os
import re
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Reconfigure stdout/stderr to UTF-8 on Windows to avoid UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import httpx
import typer
from tqdm import tqdm

from config import DEFAULT_SPLIT_LIMIT, VALID_FORMATS
from crawler.fetcher import AsyncFetcher
from crawler.sitemap import (
    crawl_recursive,
    discover_sitemap_urls,
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

# Flag for graceful shutdown
_interrupted = False


def _handle_interrupt(signum, frame):
    """Handle Ctrl+C gracefully — set flag instead of crashing."""
    global _interrupted
    if _interrupted:
        # Second Ctrl+C → force exit
        typer.echo("\n[!] Force exit.")
        sys.exit(1)
    _interrupted = True
    typer.echo(typer.style(
        "\n[!] Ctrl+C detected. Finishing current page and saving partial output...",
        fg=typer.colors.YELLOW, bold=True,
    ))


# Register signal handler
signal.signal(signal.SIGINT, _handle_interrupt)


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
    sitemap_urls = discover_sitemap_urls(url)

    if sitemap_urls:
        all_urls: list[str] = []
        for sitemap_url in sitemap_urls:
            try:
                resp = httpx.get(sitemap_url, timeout=15, follow_redirects=True)
                urls = parse_sitemap(resp.text)
                all_urls.extend(urls)
            except Exception as e:
                logger.warning(f"Sitemap read error ({sitemap_url}): {e}")
        if all_urls:
            # Deduplicate across sitemaps while preserving order
            all_urls = list(dict.fromkeys(all_urls))
            typer.echo(f"    OK  Sitemap: {len(all_urls)} URLs found (from {len(sitemap_urls)} sitemap(s))")
            return all_urls

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
    max_pages: int,
    verbose: bool,
):
    global _interrupted
    collected_at = datetime.now().astimezone().isoformat()

    # ── Phase 1: URL Discovery ──────────────────────────────────────────────
    urls = _discover_urls(url, depth, include, exclude)

    if not urls:
        typer.echo("    ERR  No URLs to crawl.")
        raise typer.Exit(1)

    # ── Filter Includes/Excludes ────────────────────────────────────────────
    # Include filtering: URL must contain at least one of the include patterns
    if include:
        filtered_urls_inc = [u for u in urls if any(inc in u for inc in include)]
        included_count = len(filtered_urls_inc)
        typer.echo(f"[*] Kept {included_count} URLs matching --include patterns")
        urls = filtered_urls_inc
        
        if not urls:
            typer.echo("    ERR  No URLs left to crawl after applying includes.")
            raise typer.Exit(1)

    # Exclude filtering: URL must NOT contain any of the exclude patterns
    if exclude:
        filtered_urls_exc = [u for u in urls if not any(ex in u for ex in exclude)]
        excluded_count = len(urls) - len(filtered_urls_exc)
        if excluded_count > 0:
            typer.echo(f"[*] Excluded {excluded_count} URLs matching --exclude patterns")
        urls = filtered_urls_exc

        if not urls:
            typer.echo("    ERR  No URLs left to crawl after applying excludes.")
            raise typer.Exit(1)

    # ── Apply --max-pages limit ──────────────────────────────────────────────
    if max_pages > 0 and len(urls) > max_pages:
        typer.echo(f"[*] Limiting to {max_pages} pages (from {len(urls)} total)")
        urls = urls[:max_pages]

    # ── Dry Run ─────────────────────────────────────────────────────────────
    if dry_run:
        avg_page_chars = 5_000  # Ước tính bình quân
        est_chars = len(urls) * avg_page_chars
        est_parts = max(1, (est_chars // split_limit) + 1)
        est_time = len(urls) / concurrency * 1.5  # seconds ước tính

        typer.echo("\n" + "-" * 50)
        typer.echo(typer.style("[DRY RUN] Preview (no actual crawl)", bold=True))
        typer.echo("-" * 50)
        typer.echo(f"  URL          : {url}")
        typer.echo(f"  Total URLs   : {len(urls)}")
        typer.echo(f"  Format       : {fmt}")
        typer.echo(f"  Split limit  : {split_limit:,} chars")
        base_name = os.path.basename(output)
        typer.echo(f"  Output       : {output}/{base_name}.{fmt}")
        typer.echo(f"  Est. size    : ~{est_chars:,} chars ({est_parts} part(s))")
        typer.echo(f"  Est. time    : ~{est_time:.0f}s")
        typer.echo("-" * 50)
        typer.echo("\n  URL list (first 20):")
        for u in urls[:20]:
            typer.echo(f"    - {u}")
        if len(urls) > 20:
            typer.echo(f"    ... and {len(urls) - 20} more URLs")
        typer.echo()
        return

    # -- Phase 2: Async Crawl ------------------------------------------------
    typer.echo(f"\n[*] Crawling {len(urls)} URLs (concurrency={concurrency})...")

    pages_data = []

    async with AsyncFetcher(concurrency=concurrency, use_cache=use_cache) as fetcher:
        with tqdm(total=len(urls), desc="Fetching", unit="page", ncols=80) as pbar:
            results = await fetcher.fetch_all(urls, progress_callback=pbar.update)

    if _interrupted:
        typer.echo(typer.style("\n[!] Interrupted during fetch. Processing downloaded pages...", fg=typer.colors.YELLOW))

    typer.echo("\n[*] Extracting and formatting content...")

    seen_hashes: set[str] = set()
    skipped_short = 0
    skipped_dup = 0
    skipped_err = 0

    for result in tqdm(results, desc="Processing", unit="page", ncols=80):
        if _interrupted:
            typer.echo(typer.style("[!] Saving partial output...", fg=typer.colors.YELLOW))
            break

        page = _process_page(result, selector, ai_clean, ai_summary, fmt, collected_at, min_length)
        if page:
            # MD5 Deduplication
            content_hash = hashlib.md5(page["content"].encode('utf-8')).hexdigest()
            if content_hash in seen_hashes:
                logger.warning(f"[SKIPPED] {page['url']} — Duplicate content")
                skipped_dup += 1
                continue
            
            seen_hashes.add(content_hash)
            pages_data.append(page)
        elif result.skipped:
            skipped_err += 1
        else:
            skipped_short += 1

    total_skipped = len(urls) - len(pages_data)
    typer.echo(f"\n  [OK] Extracted: {len(pages_data)}/{len(urls)} pages")
    if total_skipped > 0:
        parts = []
        if skipped_err > 0:
            parts.append(f"{skipped_err} errors")
        if skipped_short > 0:
            parts.append(f"{skipped_short} too short")
        if skipped_dup > 0:
            parts.append(f"{skipped_dup} duplicates")
        detail = ", ".join(parts) if parts else "see error.log"
        typer.echo(f"  [WARN] Skipped: {total_skipped} pages ({detail})")

    if not pages_data:
        typer.echo("    ERR  No content extracted.")
        raise typer.Exit(1)

    # ── Phase 3: Write Output ───────────────────────────────────────────────
    typer.echo(f"\n[*] Writing to directory {output}/ ...")

    with FileSplitter(output, fmt=fmt, split_limit=split_limit) as splitter:
        # Ghi ToC (chỉ cho md và txt)
        if fmt == "md":
            toc_pages = [{"title": p["title"], "url": p["url"]} for p in pages_data]
            splitter.write_header(build_toc(toc_pages))
        elif fmt == "txt":
            splitter.write_header(f"SITE2MD — {url}\nCollected: {collected_at}\n{'='*60}\n\n")

        # Ghi từng trang
        for page in pages_data:
            splitter.write_record(
                content=page["block"],
                record_dict=page["record"],
            )

    # ── Summary ─────────────────────────────────────────────────────────────
    typer.echo("\n" + "-" * 50)
    if _interrupted:
        typer.echo(typer.style("[PARTIAL] Saved partial output!", fg=typer.colors.YELLOW, bold=True))
    else:
        typer.echo(typer.style("[DONE] Complete!", fg=typer.colors.GREEN, bold=True))
    typer.echo(f"  Pages OK     : {len(pages_data)}")
    typer.echo(f"  Output files : {splitter.total_parts}")
    for f in splitter.output_files:
        size_kb = Path(f).stat().st_size / 1024
        typer.echo(f"    -> {f} ({size_kb:.1f} KB)")
    if total_skipped > 0:
        typer.echo(f"  Skipped      : {total_skipped} (see error.log)")
    typer.echo("-" * 50 + "\n")


# ---------------------------------------------------------------------------
# Typer CLI Definition
# ---------------------------------------------------------------------------

@app.command()
def main(
    url: str = typer.Argument(..., help="Base URL to crawl (e.g.: https://docs.example.com/)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output folder/file prefix (default: auto from URL)"),
    fmt: str = typer.Option("md", "--format", "-f", help=f"Output format: {', '.join(VALID_FORMATS)}"),
    concurrency: int = typer.Option(5, "--concurrency", "-c", help="Concurrent requests"),
    use_cache: bool = typer.Option(False, "--cache", help="Enable 24h HTTP cache"),
    split_limit: int = typer.Option(DEFAULT_SPLIT_LIMIT, "--split-limit", help="Character limit per file"),
    selector: Optional[str] = typer.Option(None, "--selector", help="CSS selector for content area"),
    depth: int = typer.Option(0, "--depth", help="Recursive crawl depth (0=sitemap, >0=depth crawl)"),
    ai_clean: bool = typer.Option(False, "--ai-clean", help="Use AI to format Markdown"),
    ai_summary: bool = typer.Option(False, "--ai-summary", help="Use AI to generate page summaries"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview URLs without crawling"),
    min_length: int = typer.Option(50, "--min-length", help="Skip pages shorter than this"),
    exclude: Optional[list[str]] = typer.Option(None, "--exclude", "-x", help="Exclude URLs containing this string"),
    include: Optional[list[str]] = typer.Option(None, "--include", "-i", help="Only keep URLs containing this string"),
    max_pages: int = typer.Option(0, "--max-pages", help="Max pages to crawl (0=unlimited)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed debug output"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output (errors only)"),
):
    """
    Site2MD -- Crawl website and output Markdown optimized for NotebookLM / RAG.

    \b
    Examples:
      python main.py https://docs.example.com
      python main.py https://docs.example.com --format jsonl -o my_docs
      python main.py https://docs.example.com --depth 2 --selector "article.content"
      python main.py https://docs.example.com --dry-run
      python main.py https://docs.example.com --max-pages 50
    """
    # Configure log level based on verbose/quiet
    if quiet:
        import logging
        logging.getLogger("site2md").setLevel(logging.ERROR)
    elif verbose:
        import logging
        logging.getLogger("site2md").setLevel(logging.DEBUG)

    # Generate default output name based on URL if not provided
    if not output:
        parsed = urlparse(url)
        # e.g., docs.python.org/3/ -> docs.python.org_3
        base = parsed.netloc + parsed.path.replace('/', '_')
        base = re.sub(r'[^a-zA-Z0-9_-]', '_', base).strip('_')
        base = re.sub(r'_+', '_', base)
        output = base if base else "default_scrape"

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

    if not quiet:
        typer.echo(typer.style("\n[*] Site2MD — Starting", bold=True))
        typer.echo(f"  Target : {url}")
        base_name = os.path.basename(output)
        typer.echo(f"  Format : {fmt}  |  Output: {output}/{base_name}.{fmt}")
        typer.echo(f"  Cache  : {'on' if use_cache else 'off'}  |  Concurrency: {concurrency}")
        if max_pages > 0:
            typer.echo(f"  Limit  : {max_pages} pages max")
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
        max_pages=max_pages,
        verbose=verbose,
    ))


if __name__ == "__main__":
    app()
