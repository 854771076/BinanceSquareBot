"""
@file storage.py
@description SQLite存储服务，用于存储已处理文章URL的MD5实现增量去重
@design-doc docs/01-architecture/system-architecture.md
@task-id BE-05
@created-by fullstack-dev-workflow
"""

import sqlite3
import hashlib
from pathlib import Path
from typing import Optional

from ..config import config


class StorageService:
    """SQLite存储服务，用于增量去重"""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = db_path or config.sqlite_db_path
        # 确保目录存在
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def init_database(self) -> None:
        """初始化数据库，创建表结构如果不存在"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url_md5 TEXT NOT NULL UNIQUE,
                    url TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            """)
            # 创建唯一索引加速去重查询
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_url_md5 ON processed_urls (url_md5)
            """)
            conn.commit()

    def _get_url_md5(self, url: str) -> str:
        """计算URL的MD5哈希"""
        return hashlib.md5(url.encode("utf-8")).hexdigest()

    def is_url_processed(self, url: str) -> bool:
        """检查URL是否已经处理过"""
        url_md5 = self._get_url_md5(url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_urls WHERE url_md5 = ?",
                (url_md5,)
            )
            return cursor.fetchone() is not None

    def mark_url_processed(self, url: str, processed: bool = True) -> None:
        """标记URL为已处理"""
        url_md5 = self._get_url_md5(url)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 如果不存在则插入，存在则更新processed状态
            cursor.execute("""
                INSERT INTO processed_urls (url_md5, url, processed)
                VALUES (?, ?, ?)
                ON CONFLICT(url_md5)
                DO UPDATE SET processed = ?
            """, (url_md5, url, processed, processed))
            conn.commit()

    def clean_all(self) -> None:
        """清空所有已处理记录（用于cli clean命令）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM processed_urls")
            conn.commit()

    def count_processed(self) -> int:
        """统计已处理URL数量"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM processed_urls")
            result = cursor.fetchone()
            return result[0] if result else 0
