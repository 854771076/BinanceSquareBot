"""
@file test_storage.py
@description 存储服务单元测试
@design-doc docs/03-backend-design/domain-model.md
@task-id BE-12
@created-by fullstack-dev-workflow
"""

import tempfile
import os
import shutil

# 设置测试环境变量 before import
os.environ["BINANCE_API_KEYS"] = '["test-key"]'
os.environ["LLM_API_KEY"] = "test-llm-key"

from src.binance_square_bot.services.storage import StorageService


def test_init_database():
    """测试初始化数据库"""
    # 创建临时目录和文件
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        storage = StorageService(db_path=db_path)
        storage.init_database()
        assert storage.count_processed() == 0
    finally:
        # Windows上SQLite可能仍持有文件锁，使用shutil删除整个目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_is_url_processed():
    """测试检查URL是否已处理"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        storage = StorageService(db_path=db_path)
        url = "https://example.com/news/1"

        # 初始未处理
        assert not storage.is_url_processed(url)

        # 标记为已处理
        storage.mark_url_processed(url)
        assert storage.is_url_processed(url)
    finally:
        # Windows上SQLite可能仍持有文件锁，使用shutil删除整个目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_clean_all():
    """测试清空所有记录"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        storage = StorageService(db_path=db_path)
        storage.mark_url_processed("https://example.com/news/1")
        storage.mark_url_processed("https://example.com/news/2")
        assert storage.count_processed() == 2

        storage.clean_all()
        assert storage.count_processed() == 0
    finally:
        # Windows上SQLite可能仍持有文件锁，使用shutil删除整个目录
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_unique_constraint():
    """测试URL MD5唯一约束"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    try:
        storage = StorageService(db_path=db_path)
        url = "https://example.com/news/1"

        # 第一次标记
        storage.mark_url_processed(url, processed=False)
        assert storage.count_processed() == 1

        # 第二次标记相同URL，应该更新processed状态而不增加计数
        storage.mark_url_processed(url, processed=True)
        assert storage.count_processed() == 1
    finally:
        # Windows上SQLite可能仍持有文件锁，使用shutil删除整个目录
        shutil.rmtree(temp_dir, ignore_errors=True)
