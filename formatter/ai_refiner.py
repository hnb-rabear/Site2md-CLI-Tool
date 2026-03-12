"""
formatter/ai_refiner.py — AI API integration cho --ai-clean và --ai-summary
"""
import re
import time
from typing import Optional

from config import (
    AI_MAX_CHUNK_CHARS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
)
from utils.logger import setup_logger

logger = setup_logger()

_client = None

# AI API retry settings
AI_MAX_RETRIES = 3
AI_RETRY_BACKOFF = 2.0  # seconds, exponential
AI_REQUEST_TIMEOUT = 60  # seconds


def _get_client():
    """Lazy init OpenAI client với Deepseek endpoint."""
    global _client
    if _client is None:
        if not DEEPSEEK_API_KEY:
            raise ValueError("DEEPSEEK_API_KEY chưa được set trong .env")
        try:
            from openai import OpenAI
            _client = OpenAI(
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                timeout=AI_REQUEST_TIMEOUT,
            )
        except ImportError:
            raise ImportError("Cần cài openai: pip install openai")
    return _client


def _call_api(system_prompt: str, user_content: str) -> str:
    """Gọi AI API với timeout và retry (exponential backoff)."""
    client = _get_client()

    for attempt in range(1, AI_MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,  # Ít creative, nhiều consistent
                max_tokens=4096,
            )
            return response.choices[0].message.content or ""

        except Exception as e:
            if attempt == AI_MAX_RETRIES:
                raise  # Re-raise on last attempt
            wait = AI_RETRY_BACKOFF * attempt
            logger.warning(f"  ⚠️  AI API error (attempt {attempt}/{AI_MAX_RETRIES}): {e} — retrying in {wait:.0f}s...")
            time.sleep(wait)

    return ""


def _chunk_text(text: str, max_chars: int = AI_MAX_CHUNK_CHARS) -> list[str]:
    """Chia text thành các chunk, ưu tiên cắt tại paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# ---------------------------------------------------------------------------
# --ai-clean: Làm sạch và chuẩn hóa Markdown
# ---------------------------------------------------------------------------

_CLEAN_SYSTEM_PROMPT = """Bạn là một Markdown formatter chuyên nghiệp.
Task: Nhận Markdown thô được extract từ HTML, trả về Markdown đã được chuẩn hóa.

Quy tắc QUAN TRỌNG:
1. GIỮ NGUYÊN toàn bộ nội dung, không thêm/bớt thông tin.
2. Fix lỗi thụt lề code blocks (đảm bảo dùng ``` không phải indent).
3. Chuẩn hóa bảng Markdown (| col | col |).
4. Xóa các ký tự noise: \\xa0, ​ (zero-width space), ký tự không in được.
5. Đảm bảo có blank line trước/sau mỗi code block và table.
6. Chỉ trả về Markdown, KHÔNG giải thích thêm gì."""


def clean_markdown(text: str, url: str = "") -> str:
    """
    Dùng AI để chuẩn hóa Markdown (--ai-clean).
    Tự động chunk nếu content lớn.
    Fallback về text gốc nếu API lỗi.
    """
    if not text.strip():
        return text

    try:
        chunks = _chunk_text(text)
        cleaned_chunks = []

        for i, chunk in enumerate(chunks):
            if len(chunks) > 1:
                logger.info(f"    🤖 AI clean chunk {i+1}/{len(chunks)}...")
            result = _call_api(_CLEAN_SYSTEM_PROMPT, chunk)
            cleaned_chunks.append(result)

        return "\n\n".join(cleaned_chunks)

    except Exception as e:
        logger.warning(f"  ⚠️  AI clean thất bại cho {url}: {e} — dùng kết quả thô.")
        return text  # Fallback về text gốc


# ---------------------------------------------------------------------------
# --ai-summary: Tạo tóm tắt ngắn (~50 từ) đầu mỗi trang
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM_PROMPT = """Bạn là assistant tóm tắt tài liệu kỹ thuật.
Task: Đọc nội dung trang web và viết tóm tắt ngắn gọn bằng tiếng Việt.

Quy tắc:
1. Tóm tắt KHÔNG quá 60 từ.
2. Tập trung vào nội dung chính, không đề cập navigation hay UI.
3. Viết dạng câu đơn, rõ ràng.
4. Chỉ trả về đoạn tóm tắt, KHÔNG tiêu đề, KHÔNG giải thích thêm."""


def summarize_page(title: str, content: str, url: str = "") -> Optional[str]:
    """
    Tạo tóm tắt ~50 từ cho một trang (--ai-summary).
    Chỉ dùng 3000 ký tự đầu để tóm tắt (tiết kiệm tokens).
    Fallback về None nếu API lỗi.
    """
    if not content.strip():
        return None

    # Giới hạn input để tiết kiệm tokens
    preview = content[:3000]
    user_content = f"Tiêu đề: {title}\n\nNội dung:\n{preview}"

    try:
        result = _call_api(_SUMMARY_SYSTEM_PROMPT, user_content)
        summary = result.strip()
        # Cắt nếu AI trả về quá dài
        words = summary.split()
        if len(words) > 70:
            summary = " ".join(words[:60]) + "..."
        return summary
    except Exception as e:
        logger.warning(f"  ⚠️  AI summary thất bại cho {url}: {e}")
        return None
