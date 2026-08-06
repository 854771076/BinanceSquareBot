from typing import Any, Literal

from pydantic import BaseModel, Field

PostType = Literal["text", "image", "article", "video"]


class TweetSourceItem(BaseModel):
    """Normalized source content ready for tweet generation.

    Media fields are LOCAL file paths (already downloaded by the source adapter).
    coin_tags is a whitelist of $SYMBOL the generator is allowed to emit — this
    is how we guarantee accurate coin association for revenue sharing.
    """

    source_name: str
    content_type: str
    identifier: str
    title: str
    summary: str
    url: str | None = None
    post_type: PostType = "text"
    body: str | None = None  # long-form draft for article posts
    images: list[str] = Field(default_factory=list)
    cover: str | None = None
    video: str | None = None
    video_duration: float | None = None
    coin_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_payload(self) -> dict[str, Any]:
        payload = self.model_dump()
        if payload.get("url") is None:
            payload.pop("url", None)
        if not payload.get("metadata"):
            payload.pop("metadata", None)
        if not payload.get("images"):
            payload.pop("images", None)
        if payload.get("cover") is None:
            payload.pop("cover", None)
        if payload.get("video") is None:
            payload.pop("video", None)
        if not payload.get("coin_tags"):
            payload.pop("coin_tags", None)
        if payload.get("body") is None:
            payload.pop("body", None)
        # Never leak local file paths into the LLM prompt.
        payload.pop("video_duration", None)
        return payload
