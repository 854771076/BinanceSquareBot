"""Binance Square media upload helpers (image + video).

Mirrors the behavior of the reference Node.js skill scripts
(~/Downloads/binance-skills-hub-main/skills/binance/square-post/scripts/lib.mjs)
using httpx so the Python CLI does not need a Node subprocess.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import time
from typing import Any

import httpx
from loguru import logger

BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"

IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
VIDEO_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
}

# Fatal OpenAPI error codes — do not retry.
FATAL_CODES = {
    "20002",
    "20013",
    "20020",
    "20022",
    "220003",
    "220004",
    "220009",
    "220011",
    "220014",
    "30008",
    "2000001",
    "2000002",
}


class BinanceMediaError(RuntimeError):
    """Raised when media upload / processing fails fatally."""


class BinanceApi:
    """Thin async-friendly sync client for Square OpenAPI media endpoints."""

    def __init__(self, client: httpx.Client, api_key: str, poll_interval: float = 3.0, max_poll_retries: int = 10) -> None:
        self.client = client
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.max_poll_retries = max_poll_retries

    def _headers(self) -> dict[str, str]:
        return {
            "X-Square-OpenAPI-Key": self.api_key,
            "Content-Type": "application/json",
            "clienttype": "binanceSkill",
        }

    def api(self, endpoint: str, body: dict[str, Any], base_url: str = BASE_URL_V2) -> dict[str, Any]:
        response = self.client.post(
            f"{base_url}{endpoint}",
            headers=self._headers(),
            json=body,
        )
        # /content/add may 504 after submission — treat as success without id (handled by caller).
        if endpoint == "/content/add" and response.status_code == 504:
            return {"id": None, "shareLink": None, "publishStatus": "success_without_post_id"}
        response.raise_for_status()
        data = response.json()
        code = str(data.get("code"))
        if code != "000000" and code != "0":
            message = data.get("message", "")
            raise BinanceMediaError(f"API error [{code}]: {message}")
        return data.get("data") or {}

    # ----- images -----

    def upload_image(self, path: str | pathlib.Path) -> str:
        path = pathlib.Path(path)
        ext = path.suffix.lower()
        content_type = IMAGE_CONTENT_TYPES.get(ext)
        if not content_type:
            raise BinanceMediaError(f"Unsupported image type: {ext}")
        logger.debug(f"Uploading image: {path.name}")
        ticket = self.api("/image/presignedUrl", {"imageName": path.name})
        presigned_url = ticket["presignedUrl"]
        file_ticket = ticket["fileTicket"]
        self._put_s3(presigned_url, path, content_type)
        return self._poll_image(file_ticket)

    def _poll_image(self, file_ticket: str) -> str:
        for i in range(self.max_poll_retries):
            data = self.api("/image/imageStatus", {"fileTicket": file_ticket})
            status = data.get("status")
            if status == 1:
                url = data["imageUrl"]
                logger.debug(f"Image ready: {url}")
                return url
            if status == 2:
                raise BinanceMediaError(f"Processing failed: {data.get('failedReason', 'unknown')}")
            logger.debug(f"Image processing... ({i + 1}/{self.max_poll_retries})")
            time.sleep(self.poll_interval)
        raise BinanceMediaError("Image processing poll timed out")

    # ----- video -----

    def upload_video(self, path: str | pathlib.Path) -> tuple[str, str]:
        """Returns (file_ticket, cover_url). Extracts first frame as cover."""
        path = pathlib.Path(path)
        ext = path.suffix.lower()
        content_type = VIDEO_CONTENT_TYPES.get(ext)
        if not content_type:
            raise BinanceMediaError(f"Unsupported video type: {ext}")
        size = path.stat().st_size
        logger.info(f"Uploading video: {path.name} ({size / 1024 / 1024:.1f}MB)")
        ticket = self.api("/video/preSign", {"fileName": path.name, "size": size})
        self._put_s3(ticket["presignedUrl"], path, content_type)
        file_ticket = ticket["fileTicket"]
        self._poll_image(file_ticket)  # video uses the same status endpoint
        cover_path = _extract_video_cover(path)
        try:
            cover_url = self.upload_image(cover_path)
        finally:
            try:
                os.unlink(cover_path)
                os.rmdir(os.path.dirname(cover_path))
            except OSError:
                pass
        return file_ticket, cover_url

    # ----- s3 -----

    def _put_s3(self, presigned_url: str, path: pathlib.Path, content_type: str) -> None:
        with path.open("rb") as fh:
            response = self.client.put(
                presigned_url,
                content=fh.read(),
                headers={"Content-Type": content_type},
            )
        response.raise_for_status()


def _extract_video_cover(video_path: pathlib.Path) -> str:
    """Extract the first frame of a video using ffmpeg. Returns cover path."""
    temp_dir = tempfile.mkdtemp(prefix="square-video-cover-")
    cover_path = os.path.join(temp_dir, f"{video_path.stem}-cover.png")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            cover_path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not os.path.exists(cover_path) or os.path.getsize(cover_path) == 0:
        raise BinanceMediaError(f"ffmpeg failed to extract cover: {result.stderr.strip()}")
    return cover_path


def probe_video_duration(video_path: str | pathlib.Path) -> float:
    """Use ffprobe to get video duration in seconds."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BinanceMediaError(f"ffprobe failed: {result.stderr.strip()}")
    return float(result.stdout.strip())
