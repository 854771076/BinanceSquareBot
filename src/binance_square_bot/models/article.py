"""
@file article.py
@description Article数据模型，表示从Fn爬取的新闻文章
@design-doc docs/03-backend-design/domain-model.md
@task-id BE-03
@created-by fullstack-dev-workflow
"""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Article(BaseModel):
    """从Fn网站爬取的新闻文章"""

    title: str
    url: str
    content: str
    published_at: Optional[datetime] = None
