"""
formatter/splitter.py — File splitting theo giới hạn ký tự
"""
import json
from pathlib import Path
from typing import Optional

from utils.logger import setup_logger

logger = setup_logger()


class FileSplitter:
    """
    Ghi nội dung vào file, tự động chia sang file mới khi vượt split_limit.
    
    Hỗ trợ 3 format: md, txt, jsonl.
    """

    def __init__(
        self,
        base_name: str,
        fmt: str = "md",
        split_limit: int = 450_000,
    ):
        """
        Args:
            base_name: Tên file cơ bản (không có extension). VD: "output".
            fmt: "md", "txt", hoặc "jsonl".
            split_limit: Giới hạn ký tự mỗi file.
        """
        self.base_name = base_name
        self.fmt = fmt.lower()
        self.split_limit = split_limit

        self._part = 1
        self._current_chars = 0
        self._current_file: Optional[object] = None
        self._all_files: list[str] = []

        self._open_new_file()

    def _get_filename(self, part: int) -> str:
        if part == 1:
            return f"{self.base_name}.{self.fmt}"
        return f"{self.base_name}_part{part}.{self.fmt}"

    def _open_new_file(self):
        if self._current_file:
            self._current_file.close()
        filename = self._get_filename(self._part)
        self._current_file = open(filename, "w", encoding="utf-8")
        self._all_files.append(filename)
        self._current_chars = 0
        logger.info(f"  [FILE] Writing to: {filename}")

    def write_header(self, content: str):
        """Ghi header/ToC vào file hiện tại (không tính vào split limit)."""
        if self._current_file:
            self._current_file.write(content)
            self._current_chars += len(content)

    def write_record(self, content: str, record_dict: Optional[dict] = None):
        """
        Ghi một record (trang) vào file.
        Tự động chuyển sang file mới nếu vượt split_limit.
        
        Args:
            content: String content (dùng cho md và txt).
            record_dict: Dict record (dùng cho jsonl).
        """
        if self.fmt == "jsonl":
            line = json.dumps(record_dict, ensure_ascii=False) + "\n"
            write_str = line
        else:
            write_str = content

        # Kiểm tra xem có cần split không
        if self._current_chars > 0 and (self._current_chars + len(write_str)) > self.split_limit:
            self._part += 1
            logger.info(
                f"  [SPLIT] Limit ({self.split_limit:,} chars) reached. "
                f"Opening part {self._part}..."
            )
            self._open_new_file()

        if self._current_file:
            self._current_file.write(write_str)
            self._current_chars += len(write_str)

    def close(self):
        """Đóng file hiện tại."""
        if self._current_file:
            self._current_file.close()
            self._current_file = None

    @property
    def output_files(self) -> list[str]:
        """Danh sách tất cả các file đã tạo."""
        return self._all_files

    @property
    def total_parts(self) -> int:
        return self._part

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
