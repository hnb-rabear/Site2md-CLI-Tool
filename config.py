"""
config.py — Constants và settings toàn cục cho Site2MD
"""
import os
from dotenv import load_dotenv

load_dotenv()

# HTTP
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30          # seconds
RETRY_COUNT = 3
RETRY_BACKOFF = 2.0           # seconds (x2 mỗi lần retry)

# Cache
CACHE_TTL = 86400             # 24 giờ (seconds)
CACHE_DIR = ".site2md_cache"

# Content extraction
MIN_CONTENT_LENGTH = 50       # Bỏ qua các trang rỗng hoặc quá ngắn
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".pdf", ".zip", ".gz", ".tar", ".exe", ".dmg",
    ".mp4", ".mp3", ".avi", ".mov",
    ".css", ".js", ".json", ".xml",
}
IGNORE_URL_PATTERNS = [
    r"/search\.html", r"/genindex\.html", r"/download\.html", 
    r"\?print=1", r"/(tag|category|author)/",
    r"/page/\d+/?$", r"/page=\d+"
]

# Noise elements để xóa trước khi extract
NOISE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "noscript"]
NOISE_CLASSES = [
    "pagination", "sidebar", "edit-on-github", "next-page", "prev-page",
    "breadcrumb", "cookie-banner", "ad", "advertisement", "banner",
    "social-share", "related-posts", "comments", "feedback",
    "table-of-contents", "toc", "menu", "nav", "navigation", 
    "site-footer", "site-header", "announce", "announcement"
]

# File splitting
DEFAULT_SPLIT_LIMIT = 450_000  # ký tự (không phải từ)

# AI (Deepseek)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-chat"
AI_MAX_CHUNK_CHARS = 12_000   # ~3500 tokens, chia nhỏ nếu content lớn hơn

# Output formats
VALID_FORMATS = ["md", "txt", "jsonl"]
