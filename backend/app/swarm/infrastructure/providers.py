"""Live discovery providers for DaSwarm.

Provider code performs real network retrieval. It returns structured items only;
Candidate creation remains in the application layer.
"""
from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urlencode

import httpx


@dataclass
class DiscoveredItem:
    provider: str
    external_id: str
    title: str
    page_url: str
    media_url: str | None
    thumbnail_url: str | None
    published_at: str | None
    creator: str | None
    duration_seconds: float | None
    topic: str
    provenance_status: str
    license_name: str | None = None
    license_url: str | None = None
    description: str | None = None
    metrics: dict[str, Any] | None = None
    media_type: str = "video"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _plain(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", str(value))
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip() or None


class WikimediaCommonsProvider:
    name = "wikimedia_commons"
    API = "https://commons.wikimedia.org/w/api.php"

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={
                "User-Agent": os.environ.get(
                    "SWARM_HTTP_USER_AGENT",
                    "DaSwarm/0.2 live discovery (local operator; Wikimedia Commons API)",
                )
            },
        )

    def discover(self, query: str, budget: int = 10) -> list[dict[str, Any]]:
        budget = max(1, min(int(budget), 25))
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "search",
            "gsrsearch": f"{query} filetype:video",
            "gsrnamespace": "6",
            "gsrlimit": str(budget),
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata|timestamp|user",
            "iiextmetadatafilter": "LicenseShortName|LicenseUrl|UsageTerms|Artist|DateTimeOriginal|ImageDescription|Credit",
        }
        response = self.client.get(self.API, params=params)
        response.raise_for_status()
        pages = response.json().get("query", {}).get("pages", [])
        items: list[dict[str, Any]] = []
        for page in pages:
            title = page.get("title", "")
            info_list = page.get("imageinfo") or []
            if not info_list:
                continue
            info = info_list[0]
            mime = str(info.get("mime") or "")
            if not mime.startswith("video/"):
                continue
            media_url = info.get("url")
            if not media_url:
                continue
            meta = info.get("extmetadata") or {}
            license_name = _plain(meta.get("LicenseShortName")) or _plain(meta.get("UsageTerms"))
            license_url = _plain(meta.get("LicenseUrl"))
            description = _plain(meta.get("ImageDescription"))
            creator = _plain(meta.get("Artist")) or info.get("user")
            original_date = _plain(meta.get("DateTimeOriginal")) or info.get("timestamp")
            page_url = info.get("descriptionurl") or (
                "https://commons.wikimedia.org/wiki/" + title.replace(" ", "_")
            )
            external_id = str(page.get("pageid") or title)
            item = DiscoveredItem(
                provider=self.name,
                external_id=external_id,
                title=title.removeprefix("File:"),
                page_url=page_url,
                media_url=media_url,
                thumbnail_url=info.get("thumburl"),
                published_at=original_date,
                creator=creator,
                duration_seconds=None,
                topic=query,
                provenance_status="LICENSED" if license_name else "UNKNOWN",
                license_name=license_name,
                license_url=license_url,
                description=description,
                metrics=None,
            )
            items.append(item.to_dict())
        return items


class YouTubeDataProvider:
    """Live metadata discovery only.

    The official Data API is intentionally not used to download/cache YouTube
    audiovisual content. Candidates from this provider are metadata-only until
    an authorized media path is configured.
    """

    name = "youtube_data"
    SEARCH = "https://www.googleapis.com/youtube/v3/search"
    VIDEOS = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self) -> None:
        self.api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("YOUTUBE_API_KEY is not configured")
        self.client = httpx.Client(timeout=20, follow_redirects=True)

    def discover(self, query: str, budget: int = 10) -> list[dict[str, Any]]:
        budget = max(1, min(int(budget), 50))
        search = self.client.get(
            self.SEARCH,
            params={
                "part": "snippet",
                "type": "video",
                "order": "date",
                "q": query,
                "maxResults": budget,
                "regionCode": os.environ.get("YOUTUBE_REGION", "US"),
                "key": self.api_key,
            },
        )
        search.raise_for_status()
        rows = search.json().get("items", [])
        ids = [x.get("id", {}).get("videoId") for x in rows]
        ids = [x for x in ids if x]
        stats: dict[str, Any] = {}
        if ids:
            video_response = self.client.get(
                self.VIDEOS,
                params={
                    "part": "snippet,contentDetails,statistics",
                    "id": ",".join(ids),
                    "key": self.api_key,
                },
            )
            video_response.raise_for_status()
            stats = {x["id"]: x for x in video_response.json().get("items", [])}
        out: list[dict[str, Any]] = []
        for row in rows:
            vid = row.get("id", {}).get("videoId")
            if not vid:
                continue
            detail = stats.get(vid, {})
            snip = detail.get("snippet") or row.get("snippet") or {}
            metrics = detail.get("statistics") or {}
            thumb_map = snip.get("thumbnails") or {}
            thumb = (thumb_map.get("high") or thumb_map.get("medium") or thumb_map.get("default") or {}).get("url")
            out.append(
                DiscoveredItem(
                    provider=self.name,
                    external_id=vid,
                    title=snip.get("title") or vid,
                    page_url=f"https://www.youtube.com/watch?v={vid}",
                    media_url=None,
                    thumbnail_url=thumb,
                    published_at=snip.get("publishedAt"),
                    creator=snip.get("channelTitle"),
                    duration_seconds=None,
                    topic=query,
                    provenance_status="UNKNOWN",
                    description=snip.get("description"),
                    metrics={
                        "view_count": int(metrics["viewCount"]) if metrics.get("viewCount") else None,
                        "like_count": int(metrics["likeCount"]) if metrics.get("likeCount") else None,
                        "comment_count": int(metrics["commentCount"]) if metrics.get("commentCount") else None,
                    },
                ).to_dict()
            )
        return out


def capabilities() -> dict[str, Any]:
    return {
        "mode": "live",
        "simulation_user_flow": False,
        "discovery": {
            "wikimedia_commons": {
                "installed": True,
                "real": True,
                "media_access": "original_file",
                "credentials_required": False,
            },
            "youtube_data": {
                "installed": bool(os.environ.get("YOUTUBE_API_KEY", "").strip()),
                "real": True,
                "media_access": "metadata_only",
                "credentials_required": True,
                "credential_env": "YOUTUBE_API_KEY",
            },
        },
        "analysis": {
            "real_media_probe": True,
            "real_media_fingerprint": True,
            "transcription": "not_configured",
            "vision": "not_configured",
            "embedding": "not_configured",
        },
        "render": {"ffmpeg": True, "source": "candidate_media"},
        "publishing": {"real": False, "providers": []},
        "metrics": {"real": False, "providers": []},
    }


def get_provider(name: str):
    if name == "wikimedia_commons":
        return WikimediaCommonsProvider()
    if name == "youtube_data":
        return YouTubeDataProvider()
    raise ValueError(f"Discovery provider not installed: {name}")
