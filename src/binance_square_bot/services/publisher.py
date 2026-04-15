"""
@file publisher.py
@description 币安广场API发布服务
@design-doc docs/01-architecture/system-architecture.md
@task-id BE-09
@created-by fullstack-dev-workflow
"""

import httpx
from typing import Optional

from ..models.tweet import Tweet


API_URL = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"


class PublishResult:
    """发布结果"""

    def __init__(
        self,
        success: bool,
        tweet_id: Optional[str] = None,
        error_message: str = "",
        api_key_index: int = 0,
    ) -> None:
        self.success = success
        self.tweet_id = tweet_id
        self.error_message = error_message
        self.api_key_index = api_key_index

    @property
    def tweet_url(self) -> Optional[str]:
        """生成推文URL"""
        if self.success and self.tweet_id:
            return f"https://www.binance.com/square/post/{self.tweet_id}"
        return None


class PublisherService:
    """币安广场发布服务"""

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=30.0)

    def publish_tweet(
        self,
        api_key: str,
        tweet: Tweet,
    ) -> PublishResult:
        """发布推文到币安广场"""

        headers = {
            "X-Square-OpenAPI-Key": api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }

        body = {
            "bodyTextOnly": tweet.content,
        }

        try:
            response = self.client.post(
                API_URL,
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            data = response.json()

            code = data.get("code")
            message = data.get("message")

            # 000000 表示成功
            if code == "000000" or code == 0:
                tweet_id = data.get("data", {}).get("id")
                return PublishResult(
                    success=True,
                    tweet_id=str(tweet_id) if tweet_id else None,
                )
            else:
                return PublishResult(
                    success=False,
                    error_message=message or f"API error code: {code}",
                )

        except httpx.HTTPError as e:
            return PublishResult(
                success=False,
                error_message=f"HTTP error: {str(e)}",
            )
        except Exception as e:
            return PublishResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
            )
