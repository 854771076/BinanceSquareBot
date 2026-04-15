"""
@file hash.py
@description MD5哈希工具函数
@design-doc requirements
@task-id BE-07
@created-by fullstack-dev-workflow
"""

import hashlib


def url_md5(url: str) -> str:
    """计算URL的MD5哈希"""
    return hashlib.md5(url.encode("utf-8")).hexdigest()
