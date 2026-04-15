"""
@file tweet.py
@description Tweet数据模型，表示LLM生成的推文
@design-doc docs/03-backend-design/domain-model.md
@task-id BE-04
@created-by fullstack-dev-workflow
"""

from pydantic import BaseModel
from datetime import datetime
from typing import List


class Tweet(BaseModel):
    """LLM生成的币安广场推文"""

    content: str
    article_url: str
    generated_at: datetime
    validation_passed: bool
    validation_errors: List[str] = []
