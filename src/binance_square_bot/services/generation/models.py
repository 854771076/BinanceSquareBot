from typing import Any

from pydantic import BaseModel, Field


class TweetSourceItem(BaseModel):
    """Normalized source content ready for tweet generation."""

    source_name: str
    content_type: str
    identifier: str
    title: str
    summary: str
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_prompt_payload(self) -> dict[str, Any]:
        payload = self.model_dump()
        if payload.get("url") is None:
            payload.pop("url", None)
        if not payload.get("metadata"):
            payload.pop("metadata", None)
        return payload
