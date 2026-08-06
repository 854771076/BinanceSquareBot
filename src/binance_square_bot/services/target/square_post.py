"""Binance Square post payload model shared across target and generator."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, field_validator

PostType = Literal["text", "image", "article", "video"]

# contentType values used by /content/add:
#   0 -> text-only short post
#   1 -> short post with imageList (1-4 images)
#   2 -> long article with title + cover
#   3 -> video post
CONTENT_TYPE_MAP: dict[str, int] = {
    "text": 0,
    "image": 1,
    "article": 2,
    "video": 3,
}


class SquarePost(BaseModel):
    """Publish-ready Binance Square post.

    Media fields carry LOCAL file paths; the target uploads them before publishing.
    """

    post_type: PostType
    body: str
    title: str | None = None
    images: list[str] = []      # 1-4 local paths for post_type=image
    cover: str | None = None    # 1 local path for post_type=article
    video: str | None = None    # local path for post_type=video
    video_duration: float | None = None

    @field_validator("body")
    @classmethod
    def _body_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("body must not be empty")
        return v

    def validate_media(self) -> None:
        if self.post_type == "image":
            if not 1 <= len(self.images) <= 4:
                raise ValueError("image post requires 1-4 images")
            for p in self.images:
                if not Path(p).is_file():
                    raise ValueError(f"image not found: {p}")
        elif self.post_type == "article":
            if not self.title or not self.title.strip():
                raise ValueError("article post requires title")
            if not self.cover:
                raise ValueError("article post requires cover")
            if not Path(self.cover).is_file():
                raise ValueError(f"cover not found: {self.cover}")
        elif self.post_type == "video":
            if not self.video:
                raise ValueError("video post requires video path")
            if not Path(self.video).is_file():
                raise ValueError(f"video not found: {self.video}")
