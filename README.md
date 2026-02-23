# Site2MD — Website to Markdown CLI

> Crawl bất kỳ trang web nào → Markdown/JSONL/TXT tối ưu cho **NotebookLM**, **RAG**, và các hệ thống AI khác.

---

## Mục lục

- [Tính năng](#tính-năng)
- [Yêu cầu](#yêu-cầu)
- [Cài đặt](#cài-đặt)
- [Cấu hình](#cấu-hình)
- [Sử dụng cơ bản](#sử-dụng-cơ-bản)
- [Tất cả tùy chọn](#tất-cả-tùy-chọn)
- [Output formats](#output-formats)
- [Tính năng nâng cao](#tính-năng-nâng-cao)
  - [Crawl qua sitemap](#crawl-qua-sitemap)
  - [Crawl đệ quy](#crawl-đệ-quy)
  - [Fallback urls.txt](#fallback-urlstxt)
  - [CSS Selector](#css-selector)
  - [File splitting](#file-splitting)
  - [HTTP Caching](#http-caching)
  - [AI Refinement](#ai-refinement)
- [Ví dụ thực tế](#ví-dụ-thực-tế)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Xử lý lỗi](#xử-lý-lỗi)
- [NotebookLM Tips](#notebooklm-tips)

---

## Tính năng

| Tính năng | Mô tả |
|---|---|
| **Sitemap crawler** | Tự động tìm `sitemap.xml` qua `robots.txt` hoặc đường dẫn mặc định |
| **Recursive crawl** | Crawl đệ quy theo độ sâu với `--depth` khi không có sitemap |
| **Multi-format** | Xuất ra Markdown (`.md`), plain text (`.txt`), JSON Lines (`.jsonl`) |
| **File splitting** | Tự động chia file khi vượt giới hạn ký tự (tối ưu cho NotebookLM 500k) |
| **YAML front-matter** | Mỗi trang được gắn metadata `source_url`, `title`, `collected_at` |
| **Table of Contents** | Tự động tạo mục lục liên kết cho toàn bộ tài liệu |
| **HTTP caching** | Cache HTTP 24h để tránh crawl lại (`--cache`) |
| **Concurrency** | Crawl song song nhiều trang cùng lúc (`--concurrency`) |
| **CSS Selector** | Trích xuất đúng vùng nội dung qua CSS selector (`--selector`) |
| **AI Cleaning** | Dùng Deepseek AI để chuẩn hóa Markdown (`--ai-clean`) |
| **AI Summary** | Tự động tóm tắt từng trang bằng tiếng Việt (`--ai-summary`) |
| **URL Exclusion** | Lọc bỏ URL theo chuỗi con như ngôn ngữ, tags (`--exclude`) |
| **Short Filter** | Bỏ qua các trang rỗng hoặc nội dung quá ngắn (`--min-length`) |
| **Deduplication** | Thuật toán MD5 ngăn chặn việc xuất ra các trang trùng lặp nội dung |
| **Dry run** | Preview danh sách URLs và ước tính kết quả (`--dry-run`) |
| **Error handling** | Tự retry (3 lần, exponential backoff), log lỗi vào `error.log` |

---

## Yêu cầu

- **Python 3.10+**
- Kết nối internet

---

## Cài đặt

### 1. Clone hoặc tải về dự án

```bash
git clone https://github.com/yourname/site2md.git
cd site2md
```

### 2. Cài đặt dependencies

```bash
pip install -r requirements.txt
```

Hoặc nếu pip không nhận diện:

```bash
python -m pip install -r requirements.txt
```

### 3. Cấu hình API (tùy chọn — chỉ cần cho AI features)

```bash
cp .env.example .env
# Chỉnh sửa .env và điền DEEPSEEK_API_KEY nếu muốn dùng --ai-clean / --ai-summary
```

---

## Cấu hình

### `.env`

```env
# Chỉ cần cho --ai-clean và --ai-summary
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com  # Mặc định, có thể bỏ qua
```

### `config.py`

Các hằng số toàn cục có thể điều chỉnh:

| Hằng số | Mặc định | Mô tả |
|---|---|---|
| `DEFAULT_SPLIT_LIMIT` | `450_000` | Giới hạn ký tự mỗi file |
| `MIN_CONTENT_LENGTH` | `50` ký tự | Chiều dài văn bản tối thiểu (có thể ghi đè) |
| `REQUEST_TIMEOUT` | `30` giây | Timeout HTTP request |
| `MAX_RETRIES` | `3` | Số lần retry khi lỗi mạng |
| `CACHE_TTL` | `86400` giây | Thời gian sống của cache (24h) |
| `AI_MAX_CHUNK` | `12_000` | Max token mỗi lần gọi AI |

---

## Sử dụng cơ bản

```bash
# Crawl toàn bộ site qua sitemap, xuất ra output.md
python main.py https://docs.example.com

# Crawl đệ quy depth=2, đặt tên output là "laravel_docs"
python main.py https://laravel.com/docs -o laravel_docs --depth 2

# Xuất JSONL (cho RAG vector store)
python main.py https://docs.example.com --format jsonl

# Xem trước URLs trước khi crawl
python main.py https://docs.example.com --dry-run
```

---

## Tất cả tùy chọn

```
Usage: python main.py [URL] [OPTIONS]

Arguments:
  URL  [required]  URL gốc cần crawl (ví dụ: https://docs.example.com/)

Options:
  -o, --output    TEXT     Tên file đầu ra (không extension) [default: output]
  -f, --format    TEXT     Format: md | txt | jsonl          [default: md]
  -c, --concurrency INT   Số request song song               [default: 5]
      --cache              Bật HTTP cache 24h
      --split-limit INT    Giới hạn ký tự mỗi file          [default: 450000]
      --selector  TEXT     CSS selector vùng nội dung
      --depth     INT      Độ sâu crawl đệ quy (0 = dùng sitemap)
      --ai-clean           Dùng AI chuẩn hóa Markdown
      --ai-summary         Dùng AI tạo tóm tắt tiếng Việt
      --dry-run            Preview URLs không crawl
      --min-length INT     Bỏ qua các trang ngắn hơn mức này [default: 50]
  -x, --exclude   TEXT     Bỏ qua các URL chứa chuỗi này (VD: -x zh-CN)
      --help               Hiển thị trợ giúp
```

---

## Output formats

### `--format md` (mặc định)

Phù hợp nhất cho **NotebookLM** và đọc bởi người.

```markdown
# 📑 MỤC LỤC

Tổng số trang: **42**

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

Nội dung trang...
```

### `--format jsonl`

Phù hợp cho **RAG vector stores**, **LangChain**, **LlamaIndex**.

Mỗi dòng là một JSON object:

```json
{"url": "https://docs.example.com/page", "title": "Page Title", "content": "# Heading\n\nContent...", "collected_at": "2026-02-23T17:00:00+07:00"}
```

### `--format txt`

Xuất plain text đơn giản, không có Markdown formatting.

```
SITE2MD — https://docs.example.com
Thu thập: 2026-02-23T17:00:00+07:00
============================================================

[Getting Started] https://docs.example.com/getting-started
Nội dung trang...
```

---

## Tính năng nâng cao

### Crawl qua sitemap

Mặc định, Site2MD tự tìm sitemap theo thứ tự:

1. Đọc `robots.txt` để tìm `Sitemap:` directive
2. Thử `/sitemap.xml`
3. Thử `/sitemap_index.xml`
4. Fallback sang `urls.txt` nếu không tìm thấy

```bash
python main.py https://docs.example.com
```

### Crawl đệ quy

Dùng khi site không có sitemap, hoặc muốn giới hạn số trang:

```bash
# Crawl tối đa depth=1 (chỉ các link trực tiếp từ trang gốc)
python main.py https://docs.example.com --depth 1

# Crawl sâu hơn
python main.py https://docs.example.com --depth 3
```

> **Lưu ý:** `--depth` chỉ theo dõi link nội bộ (cùng domain).  
> **[⚡ Tính năng Tối ưu]:** Khi kết hợp `--depth` chung với bộ lọc `--include` hoặc `--exclude`, Tool sẽ thông minh rà soát và loại bỏ ngay các nhánh con không hợp lệ *ngay trong quá trình đệ quy*. Điều này giúp tốc độ rà quét nhanh hơn hàng trăm lần vì Tool không phải mất thời gian chui vào những ngõ cụt mà sau này đằng nào cũng bị loại bỏ.

### Fallback `urls.txt`

Nếu không tìm thấy sitemap, tạo file `urls.txt` trong thư mục chạy lệnh:

```
https://docs.example.com/page1
https://docs.example.com/page2
https://docs.example.com/page3
```

```bash
python main.py https://docs.example.com
# Tự động đọc urls.txt khi sitemap không tìm thấy
```

### CSS Selector

Khi trang có nhiều UI noise (nav, footer, sidebar), dùng `--selector` để trỏ đúng vùng nội dung:

```bash
# Chỉ lấy nội dung trong <article class="content">
python main.py https://docs.example.com --selector "article.content"

# Lấy main content
python main.py https://docs.example.com --selector "main"

# Lấy div có id cụ thể
python main.py https://docs.example.com --selector "#page-content"
```

**Cách tìm selector:**
1. Mở DevTools trong trình duyệt (F12)
2. Click vào vùng nội dung chính
3. Inspect element → copy selector

> **Lưu ý Heuristic Tự Động:** Nếu bạn không cung cấp `--selector`, Tool vẫn sẽ tự động tìm kiếm các thẻ nội dung phổ biến như `<article>`, `<main>`, hoặc `[role="main"]` để cố gắng cô lập nội dung, do đó giảm rác từ Menu/Sidebar một cách hệ thống.

### Lọc nội dung và URL

1. **URL Inclusion/Exclusion (`--include` / `--exclude`)**:
   Bạn có thể chỉ giữ lại các URL chứa chuỗi nhất định (`-i`) hoặc loại trừ các URL chứa chuỗi không mong muốn (`-x`). Công cụ sẽ tự chặn/lọc URL từ giai đoạn "URL Discovery" để tránh tốn thời gian tải trang giả.
   ```bash
   # Loại bỏ các trang tiếng Trung và trang Tag của người dùng
   python main.py https://docs.example.com -x zh-CN -x /tag/

   # CHỈ TẢI các trang nằm trong thư mục /docs/
   python main.py https://docs.example.com -i /docs/
   ```

2. **Lọc nội dung quá ngắn (`--min-length`)**:
   Sẽ có nhiều URL như `/search`, thẻ Tags... chỉ sinh ra layout mà không có nội dung văn bản. Nếu kết quả sau khi trích xuất nhỏ hơn giới hạn này (Mặc định: 50 ký tự), nội dung đó sẽ bị loại bỏ hoàn toàn.
   ```bash
   python main.py https://docs.example.com --min-length 300
   ```

3. **Ngăn chặn nội dung trùng lặp (Deduplication)**:
   Các framework làm Web đôi khi đưa cùng một văn bản (như trang License, Error 404) lên rất nhiều URL khác nhau. Công cụ sử dụng hàm băm mã **MD5** để lưu giữ dấu vân tay của mỗi bài viết. Nó đảm bảo không ghi đè cùng văn bản vào file Output ngay cả khi nó thấy nó trên hàng tá URL.

### File splitting

NotebookLM giới hạn **500,000 ký tự** mỗi file. Site2MD tự động chia file khi vượt ngưỡng:

```
output.md        (450,000 chars)
output_part2.md  (tiếp theo...)
output_part3.md  (nếu cần...)
```

Tùy chỉnh ngưỡng:

```bash
# Chia nhỏ hơn (200k chars/file)
python main.py https://docs.example.com --split-limit 200000

# Không chia (cho Google Drive, etc.)
python main.py https://docs.example.com --split-limit 999999999
```

### HTTP Caching

Bật cache để tránh crawl lại trang đã fetch, tiết kiệm thời gian khi chạy nhiều lần:

```bash
python main.py https://docs.example.com --cache
```

Cache được lưu tại `.cache/` trong thư mục hiện tại, TTL = 24h.

### AI Refinement

Yêu cầu `DEEPSEEK_API_KEY` trong `.env`.

#### `--ai-clean` — Chuẩn hóa Markdown

Dùng AI để:
- Sửa indentation code blocks
- Chuẩn hóa bảng Markdown
- Loại bỏ ký tự rác
- Thống nhất heading levels

```bash
python main.py https://docs.example.com --ai-clean
```

> Xử lý thêm ~1-2 giây/trang. Có chunking tự động cho trang dài.

#### `--ai-summary` — Tóm tắt trang

Thêm tóm tắt ~50 từ bằng tiếng Việt vào đầu mỗi trang:

```bash
python main.py https://docs.example.com --ai-summary
```

#### Kết hợp cả hai

```bash
python main.py https://docs.example.com --ai-clean --ai-summary
```

---

## Ví dụ thực tế

### Scrape Python docs để hỏi NotebookLM

```bash
python main.py https://docs.python.org/3/ --depth 1 -o python_docs --concurrency 10
```

→ Tạo `python_docs.md` + `python_docs_part2.md`, upload cả 2 lên NotebookLM.

### Scrape docs framework cho RAG

```bash
python main.py https://fastapi.tiangolo.com --format jsonl -o fastapi_docs
```

→ Tạo `fastapi_docs.jsonl`, import vào LangChain/LlamaIndex.

### Site có sidebar phức tạp

```bash
python main.py https://docs.rust-lang.org/book/ \
  --selector "div#content main" \
  --depth 2 \
  -o rust_book
```

### Xử lý khối Sitemap/Trang Web khổng lồ (Tránh Timeout)

Một số trang web rất lớn (như `ubuntu.com`) sở hữu sitemap chứa hàng trăm nghìn URL, dẫn đến việc Tool có thể bị **Timeout** ngay lúc tải sitemap. Thay vì tải toàn bộ sitemap của công ty, bạn có thể kết hợp `--depth` và `--include` để khoanh vùng và ép Tool chỉ crawl đúng thư mục bạn cần:

```bash
# Chỉ lấy tài liệu trong nhánh /server/docs/ bằng cách đi theo link nội bộ sâu 2 tầng, 
# đồng thời chặn đứng các URL lạc ra ngoài nhánh này.
python main.py https://ubuntu.com/server/docs/ \
  --depth 2 \
  --include /server/docs/
```

### Crawl nhanh với cache (lần 2 trở đi)

```bash
# Lần đầu: crawl thực tế
python main.py https://docs.example.com --cache -o docs

# Lần sau: đọc từ cache (<1 giây)
python main.py https://docs.example.com --cache -o docs_v2
```

### Preview trước khi crawl site lớn

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

## Cấu trúc dự án

```
Site2md CLI Tool/
├── main.py              # CLI entry point (Typer)
├── config.py            # Hằng số và cấu hình
├── requirements.txt     # Dependencies
├── .env.example         # Template biến môi trường
├── .env                 # API keys (không commit git!)
│
├── crawler/
│   ├── __init__.py
│   ├── sitemap.py       # Tìm sitemap, parse XML, crawl đệ quy
│   └── fetcher.py       # Async HTTP client (httpx + hishel cache + retry)
│
├── extractor/
│   ├── __init__.py
│   ├── cleaner.py       # Xóa UI noise (nav/footer/ads) bằng BeautifulSoup
│   └── content.py       # Trích xuất nội dung (trafilatura → markdownify fallback)
│
└── formatter/
    ├── __init__.py
    ├── markdown.py      # Build YAML block, JSONL record, Table of Contents
    ├── splitter.py      # Chia file tự động theo giới hạn ký tự
    └── ai_refiner.py    # Deepseek API integration (clean + summary)
```

### Luồng xử lý

```
URL Input
   │
   ├── sitemap.py → Tìm danh sách URLs (sitemap / đệ quy / urls.txt)
   │
   └── fetcher.py → Fetch HTML song song (async, cache, retry)
          │
          ├── cleaner.py → Xóa noise HTML, áp dụng CSS selector
          │
          ├── content.py → trafilatura → markdown content
          │              → markdownify (fallback)
          │
          ├── ai_refiner.py → (tùy chọn) AI clean + summary
          │
          └── splitter.py → Ghi ra file (md/txt/jsonl), tự split
```

---

## Xử lý lỗi

### `error.log`

Mọi lỗi crawl được ghi vào `error.log` trong thư mục hiện tại:

```
2026-02-23 17:00:01 WARNING [SKIPPED] https://example.com/page - HTTP 403
2026-02-23 17:00:05 WARNING [SKIPPED] https://example.com/other - Timeout
```

### Retry tự động

- **3 lần retry** với exponential backoff (1s → 2s → 4s)
- Áp dụng cho: timeout, connection error, HTTP 5xx
- HTTP 403, 404: skip ngay, không retry

### Trang không extract được

- Nếu `trafilatura` không extract được → thử `markdownify`
- Nếu cả hai thất bại → ghi `[SKIPPED]` vào `error.log`, tiếp tục trang khác
- Trang bị skip **không làm dừng** toàn bộ quá trình crawl

---

## NotebookLM Tips

### Upload nhiều file

Khi site có nhiều trang, Site2MD tự chia thành nhiều file `_part1`, `_part2`... Upload tất cả lên NotebookLM cùng một lúc.

### Giới hạn 500k ký tự

NotebookLM từ chối file > 500,000 ký tự. Mặc định Site2MD dùng `--split-limit 450000` để có buffer an toàn.

### Tối ưu hóa độ liên quan

Dùng `--selector` để chỉ lấy nội dung chính, bỏ qua nav/footer:

```bash
# Kết quả tốt hơn cho Q&A
python main.py https://docs.example.com --selector "main article"
```

### Format nào tốt nhất?

| Use case | Format |
|---|---|
| NotebookLM | `md` (mặc định) |
| LangChain / LlamaIndex | `jsonl` |
| Đọc thủ công | `txt` |
| Chroma / Pinecone | `jsonl` |

---

## Dependencies chính

| Package | Mục đích |
|---|---|
| `typer` | CLI framework |
| `httpx` | Async HTTP client |
| `hishel` | HTTP cache cho httpx |
| `beautifulsoup4` + `lxml` | HTML parsing & cleaning |
| `trafilatura` | Content extraction |
| `markdownify` | HTML → Markdown fallback |
| `openai` | Deepseek API client (AI features) |
| `tqdm` | Progress bar |
| `python-dotenv` | Đọc `.env` |

---

## License

MIT
