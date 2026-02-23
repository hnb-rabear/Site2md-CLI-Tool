# Site2MD — Website to Markdown CLI

[🇻🇳 Đọc bằng Tiếng Việt (Read in Vietnamese)](README_VI.md)

> Crawl any website → Optimized Markdown/JSONL/TXT for **NotebookLM**, **RAG**, and other AI systems.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [All Options](#all-options)
- [Output formats](#output-formats)
- [Advanced Features](#advanced-features)
  - [Sitemap Crawl](#sitemap-crawl)
  - [Recursive Crawl](#recursive-crawl)
  - [Fallback urls.txt](#fallback-urlstxt)
  - [CSS Selector](#css-selector)
  - [Content and URL Filtering](#content-and-url-filtering)
  - [File Splitting](#file-splitting)
  - [HTTP Caching](#http-caching)
  - [AI Refinement](#ai-refinement)
- [Real-world Examples](#real-world-examples)
- [Project Structure](#project-structure)
- [Error Handling](#error-handling)
- [NotebookLM Tips](#notebooklm-tips)

---

## Features

| Feature | Description |
|---|---|
| **Sitemap Crawler** | Automatically finds `sitemap.xml` via `robots.txt` or default paths |
| **Recursive Crawl** | Recursive breadth-first crawl with `--depth` when sitemap is missing |
| **Multi-format** | Output to Markdown (`.md`), plain text (`.txt`), JSON Lines (`.jsonl`) |
| **File Splitting** | Auto-splits files when exceeding character limits (optimized for NotebookLM's 500k limit) |
| **YAML Front-matter** | Injects `source_url`, `title`, `collected_at` metadata into each page |
| **Table of Contents** | Auto-generates a hyperlinked table of contents for the entire document |
| **HTTP Caching** | 24h HTTP caching to prevent re-crawling (`--cache`) |
| **Concurrency** | Concurrent crawling for multiple pages (`--concurrency`) |
| **CSS Selector** | Target specific content areas using CSS selectors (`--selector`) |
| **AI Cleaning** | Uses Deepseek AI to format and clean Markdown (`--ai-clean`) |
| **AI Summary** | Auto-generates a Vietnamese summary for each page (`--ai-summary`) |
| **URL Filtering** | Filter URLs by substrings like language or tags (`--include` / `--exclude`) |
| **Short Filter** | Skips empty pages or content that is too short (`--min-length`) |
| **Deduplication** | MD5 hashing algorithm prevents duplicate content output |
| **Global Output Dir**| All results are cleanly packed into an `output/` directory (git ignored) |
| **Dry Run** | Previews URLs and estimates results without crawling (`--dry-run`) |
| **Error Handling** | Auto-retries (3 times, exponential backoff) and logs to `error.log` |

---

## Requirements

- **Python 3.10+**
- Internet connection

---

## Installation

### 1. Clone or download the project

```bash
git clone https://github.com/yourname/site2md.git
cd site2md
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

Or if pip is not recognized:

```bash
python -m pip install -r requirements.txt
```

### 3. API Configuration (Optional — only for AI features)

```bash
cp .env.example .env
# Edit .env and fill in DEEPSEEK_API_KEY if you want to use --ai-clean / --ai-summary
```

---

## Configuration

### `.env`

```env
# Only needed for --ai-clean and --ai-summary
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com  # Default, can be omitted
```

### `config.py`

Adjustable global constants:

| Constant | Default | Description |
|---|---|---|
| `DEFAULT_SPLIT_LIMIT` | `450_000` | Character limit per file |
| `MIN_CONTENT_LENGTH` | `50` chars | Minimum text length (can be overridden) |
| `REQUEST_TIMEOUT` | `30` seconds | HTTP request timeout |
| `MAX_RETRIES` | `3` | Number of retries on network error |
| `CACHE_TTL` | `86400` seconds | Cache time-to-live (24h) |
| `AI_MAX_CHUNK` | `12_000` | Max tokens per AI call |

---

## Basic Usage

```bash
# Crawl entire site via sitemap, output to output/default_scrape/default_scrape.md
python main.py https://docs.example.com

# Recursive crawl depth=2, output named "laravel_docs"
python main.py https://laravel.com/docs -o laravel_docs --depth 2

# Export JSONL (for RAG vector store)
python main.py https://docs.example.com --format jsonl

# Preview URLs before crawling
python main.py https://docs.example.com --dry-run
```

---

## All Options

```
Usage: python main.py [URL] [OPTIONS]

Arguments:
  URL  [required]  Base URL to crawl (e.g.: https://docs.example.com/)

Options:
  -o, --output    TEXT     Output filename/folder (no extension) [default: auto]
  -f, --format    TEXT     Format: md | txt | jsonl          [default: md]
  -c, --concurrency INT   Concurrent requests                  [default: 5]
      --cache              Enable 24h HTTP cache
      --split-limit INT    Character limit per file          [default: 450000]
      --selector  TEXT     CSS selector for content area
      --depth     INT      Recursive crawl depth (0 = use sitemap)
      --ai-clean           Use AI to format Markdown
      --ai-summary         Use AI to generate page summaries
      --dry-run            Preview URLs without crawling
      --min-length INT     Skip pages shorter than this      [default: 50]
  -i, --include   TEXT     ONLY keep URLs containing this string (e.g. -i /docs/)
  -x, --exclude   TEXT     Ignore URLs containing this string (e.g. -x zh-CN)
      --help               Show help message
```

---

## Output formats

### `--format md` (default)

Best suited for **NotebookLM** and human reading.

```markdown
# 📑 MỤC LỤC (Table of Contents)

Total pages: **42**

1. [Getting Started](https://docs.example.com/getting-started)
2. [Installation](https://docs.example.com/installation)
...

---
---
source_url: https://docs.example.com/getting-started
title: "Getting Started"
collected_at: 2026-02-23T17:00:00+07:00
---

# Getting Started

Page content...
```

### `--format jsonl`

Suitable for **RAG vector stores**, **LangChain**, **LlamaIndex**.

Each line is a JSON object:

```json
{"url": "https://docs.example.com/page", "title": "Page Title", "content": "# Heading\n\nContent...", "collected_at": "2026-02-23T17:00:00+07:00"}
```

### `--format txt`

Exports simple plain text, without Markdown formatting.

```
SITE2MD — https://docs.example.com
Collected: 2026-02-23T17:00:00+07:00
============================================================

[Getting Started] https://docs.example.com/getting-started
Page content...
```

---

## Advanced Features

### Sitemap Crawl

By default, Site2MD finds the sitemap in this order:

1. Reads `robots.txt` for `Sitemap:` directives
2. Tries `/sitemap.xml`
3. Tries `/sitemap_index.xml`
4. Fallbacks to `urls.txt` if not found

```bash
python main.py https://docs.example.com
```

### Recursive Crawl

Used when a site lacks a sitemap, or to limit the number of pages:

```bash
# Crawl max depth=1 (only direct links from the base page)
python main.py https://docs.example.com --depth 1

# Crawl deeper
python main.py https://docs.example.com --depth 3
```

> **Note:** `--depth` only follows internal links (same domain).  
> **[⚡ Optimization Feature]:** When combining `--depth` with `--include` or `--exclude` filters, the tool intelligently scans and drops invalid branches *during the recursion process*. This speeds up crawling hundreds of times since the tool doesn't waste time going down dead ends.

### Fallback `urls.txt`

If no sitemap is found, create a `urls.txt` file in the working directory:

```
https://docs.example.com/page1
https://docs.example.com/page2
https://docs.example.com/page3
```

```bash
python main.py https://docs.example.com
# Automatically reads urls.txt when sitemap is missing
```

### CSS Selector

When a page has heavily noisy UI (nav, footer, sidebar), use `--selector` to target the main content:

```bash
# Only extract content inside <article class="content">
python main.py https://docs.example.com --selector "article.content"

# Extract main content
python main.py https://docs.example.com --selector "main"

# Extract specific div by id
python main.py https://docs.example.com --selector "#page-content"
```

**How to find a selector:**
1. Open DevTools in browser (F12)
2. Click on the main content area
3. Inspect element → copy selector

> **Auto-Heuristic Note:** If you don't provide a `--selector`, the tool will automatically search for common content tags like `<article>`, `<main>`, or `[role="main"]` to isolate content and systematically reduce Menu/Sidebar noise.

### Content and URL Filtering

1. **URL Inclusion/Exclusion (`--include` / `--exclude`)**:
   You can choose to exclusively keep URLs containing a string (`-i`) or exclude URLs containing unwanted strings (`-x`). The tool blocks/filters URLs during "URL Discovery" to avoid loading fake pages.
   ```bash
   # Remove Chinese pages and user Tag pages
   python main.py https://docs.example.com -x zh-CN -x /tag/

   # ONLY LOAD pages inside the /docs/ folder
   python main.py https://docs.example.com -i /docs/
   ```

2. **Short Content Filter (`--min-length`)**:
   Many URLs like `/search`, Tags... generate layouts without text content. If the extracted result is smaller than this limit (Default: 50 characters), the content is discarded.
   ```bash
   python main.py https://docs.example.com --min-length 300
   ```

3. **Content Deduplication**:
   Web frameworks sometimes serve the exact same text (like License, Error 404 pages) on multiple URLs. The tool uses **MD5** hashing to keep a fingerprint of each article. It ensures identical text is not overwritten to the Output even if found on dozens of URLs.

### File Splitting

NotebookLM limits files to **500,000 characters**. Site2MD auto-splits files when exceeding the threshold:

```
output.md        (450,000 chars)
output_part2.md  (continued...)
output_part3.md  (if needed...)
```

Customize the split limit:

```bash
# Split smaller (200k chars/file)
python main.py https://docs.example.com --split-limit 200000

# Do not split (for Google Drive, etc.)
python main.py https://docs.example.com --split-limit 999999999
```

### HTTP Caching

Enable cache to avoid re-fetching pages, saving time on subsequent runs:

```bash
python main.py https://docs.example.com --cache
```

Cache is saved in `.site2md_cache/` in the current directory, TTL = 24h.

### AI Refinement

Requires `DEEPSEEK_API_KEY` in `.env`.

#### `--ai-clean` — Standardize Markdown

Uses AI to:
- Fix code block indentation
- Standardize Markdown tables
- Remove garbage characters
- Unify heading levels

```bash
python main.py https://docs.example.com --ai-clean
```

> Adds ~1-2 secs/page. Includes automatic chunking for long pages.

#### `--ai-summary` — Page Summary

Adds a ~50-word summary at the top of each page:

```bash
python main.py https://docs.example.com --ai-summary
```

#### Combine Both

```bash
python main.py https://docs.example.com --ai-clean --ai-summary
```

---

## Real-world Examples

### Scrape Python docs for NotebookLM

```bash
python main.py https://docs.python.org/3/ --depth 1 -o python_docs --concurrency 10
```

→ Generates `python_docs.md` + `python_docs_part2.md`, upload both to NotebookLM.

### Scrape framework docs for RAG

```bash
python main.py https://fastapi.tiangolo.com --format jsonl -o fastapi_docs
```

→ Generates `fastapi_docs.jsonl`, import into LangChain/LlamaIndex.

### Site with complex sidebars

```bash
python main.py https://docs.rust-lang.org/book/ \
  --selector "div#content main" \
  --depth 2 \
  -o rust_book
```

### Handling Massive Sitemaps/Websites (Avoid Timeout)

Some very large websites (like `ubuntu.com`) have sitemaps containing hundreds of thousands of URLs, which can cause the tool to **Timeout** while loading the sitemap. Instead of downloading the company's entire sitemap, you can combine `--depth` and `--include` to restrict the tool to crawl exactly the folder you need:

```bash
# Only get docs in the /server/docs/ branch by following internal links up to 2 layers deep,
# while blocking URLs that wander outside this branch.
python main.py https://ubuntu.com/server/docs/ \
  --depth 2 \
  --include /server/docs/
```

### Fast crawl with cache (2nd run onwards)

```bash
# First time: actual crawl
python main.py https://docs.example.com --cache -o docs

# Next time: read from cache (<1 sec)
python main.py https://docs.example.com --cache -o docs_v2
```

### Preview before crawling large sites

```bash
python main.py https://docs.example.com --dry-run
```

Output:

```
--------------------------------------------------
[DRY RUN] Preview (khong crawl thuc te)
--------------------------------------------------
  URL          : https://docs.example.com
  Tong URL     : 523
  Format       : md
  Split limit  : 450,000 chars
  Output       : output/docs_example_com/docs_example_com.md
  Est. size    : ~2,615,000 chars (6 part(s))
  Est. time    : ~157s
--------------------------------------------------

  URL list (first 10):
    - https://docs.example.com/
    - https://docs.example.com/guide/
    ...
```

---

## Project Structure

```
Site2md CLI Tool/
├── main.py              # CLI entry point (Typer)
├── config.py            # Constants and settings
├── requirements.txt     # Dependencies
├── .env.example         # Environment template
├── .env                 # API keys (do not commit to git!)
│
├── crawler/
│   ├── __init__.py
│   ├── sitemap.py       # Sitemap discovery, XML parsing, recursive crawl
│   └── fetcher.py       # Async HTTP client (httpx + hishel cache + retry)
│
├── extractor/
│   ├── __init__.py
│   ├── cleaner.py       # Removes UI noise (nav/footer/ads) via BeautifulSoup
│   └── content.py       # Content extraction (trafilatura → markdownify fallback)
│
└── formatter/
    ├── __init__.py
    ├── markdown.py      # Build YAML block, JSONL record, Table of Contents
    ├── splitter.py      # Auto-splits files by character limit
    └── ai_refiner.py    # Deepseek API integration (clean + summary)
```

### Pipeline Flow

```
URL Input
   │
   ├── sitemap.py → Find URL list (sitemap / recursive / urls.txt)
   │
   └── fetcher.py → Fetch HTML concurrently (async, cache, retry)
          │
          ├── cleaner.py → Remove HTML noise, apply CSS selector
          │
          ├── content.py → trafilatura → markdown content
          │              → markdownify (fallback)
          │
          ├── ai_refiner.py → (optional) AI clean + summary
          │
          └── splitter.py → Output to file (md/txt/jsonl), auto split
```

---

## Error Handling

### `error.log`

All crawl errors are logged to `error.log` in the current directory:

```
2026-02-23 17:00:01 WARNING [SKIPPED] https://example.com/page - HTTP 403
2026-02-23 17:00:05 WARNING [SKIPPED] https://example.com/other - Timeout
```

### Auto Retries

- **3 retries** with exponential backoff (1s → 2s → 4s)
- Applies to: timeouts, connection errors, HTTP 5xx
- HTTP 403, 404: skipped immediately, no retry

### Extraction Failures

- If `trafilatura` fails to extract → tries `markdownify`
- If both fail → logs `[SKIPPED]` to `error.log`, continues to next page
- Skipped pages **do not halt** the entire crawling process

---

## NotebookLM Tips

### Uploading multiple files

For large sites, Site2MD auto-splits into multiple files `_part1`, `_part2`... Upload all to NotebookLM at once.

### 500k Character Limit

NotebookLM rejects files > 500,000 characters. Site2MD defaults to `--split-limit 450000` to maintain a safe buffer.

### Optimizing Relevance

Use `--selector` to target only main content, ignoring nav/footers:

```bash
# Better results for Q&A
python main.py https://docs.example.com --selector "main article"
```

### Which Format is Best?

| Use Case | Format |
|---|---|
| NotebookLM | `md` (default) |
| LangChain / LlamaIndex | `jsonl` |
| Manual Reading | `txt` |
| Chroma / Pinecone | `jsonl` |

---

## Core Dependencies

| Package | Purpose |
|---|---|
| `typer` | CLI framework |
| `httpx` | Async HTTP client |
| `hishel` | HTTP cache for httpx |
| `beautifulsoup4` + `lxml` | HTML parsing & cleaning |
| `trafilatura` | Content extraction |
| `markdownify` | HTML → Markdown fallback |
| `openai` | Deepseek API client (AI features) |
| `tqdm` | Progress bar |
| `python-dotenv` | Read `.env` |

---

## License

MIT
