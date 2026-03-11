import re
import os
import json
import asyncio
import html as html_module
from typing import Optional, List, Dict, Any, AsyncGenerator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="YouTube Comment Finder",
    description="Find all comments made by a specific user on a YouTube video.",
    version="1.0.0",
)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# ─── Constants ────────────────────────────────────────────────────────────────

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_VIDEO_URL = "https://www.youtube.com/shorts/VMsevyvXOAc"
MAX_RESULTS_PER_PAGE = 100  # YouTube API maximum

YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video/short ID from various URL formats."""
    patterns = [
        r"youtube\.com/watch\?(?:.*&)?v=([a-zA-Z0-9_-]{11})",
        r"youtube\.com/shorts/([a-zA-Z0-9_-]{11})",
        r"youtu\.be/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        r"youtube\.com/v/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def build_thumbnail_url(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"


async def fetch_video_info(video_id: str, api_key: str, client: httpx.AsyncClient) -> Dict[str, Any]:
    """Fetch video title and total comment count from YouTube Data API."""
    resp = await client.get(
        f"{YOUTUBE_API_BASE}/videos",
        params={"part": "snippet,statistics", "id": video_id, "key": api_key},
    )
    data = resp.json()
    items = data.get("items", [])
    if items:
        title = items[0]["snippet"]["title"]
        stats = items[0].get("statistics", {})
        comment_count = int(stats.get("commentCount", 0))
        return {"title": title, "comment_count": comment_count}
    return {"title": "Unknown Video", "comment_count": 0}


async def fetch_all_comments(
    video_id: str, api_key: str
) -> List[Dict[str, Any]]:
    """
    Paginate through all top-level comments for a video.
    Returns a flat list of comment dicts.
    """
    comments: List[Dict[str, Any]] = []
    next_page_token: Optional[str] = None

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Also grab the video title in parallel on the first iteration
        info = await fetch_video_info(video_id, api_key, client)
        video_title = info["title"]

        while True:
            params: Dict[str, Any] = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": MAX_RESULTS_PER_PAGE,
                "order": "time",
                "key": api_key,
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            resp = await client.get(
                f"{YOUTUBE_API_BASE}/commentThreads",
                params=params,
            )

            if resp.status_code != 200:
                error_detail = resp.json().get("error", {})
                msg = error_detail.get("message", "Unknown API error")
                raise RuntimeError(f"YouTube API error {resp.status_code}: {msg}")

            data = resp.json()

            for item in data.get("items", []):
                thread_id = item["id"]
                top_snippet = item["snippet"]["topLevelComment"]["snippet"]
                total_replies = item["snippet"].get("totalReplyCount", 0)
                d = make_comment_dict(top_snippet)
                d["reply_count"] = total_replies
                comments.append(d)

                # Inline replies (API returns up to 20)
                inline = item.get("replies", {}).get("comments", [])
                for r in inline:
                    comments.append(make_comment_dict(r["snippet"], reply_to_id=thread_id))

                # If there are more replies than what came inline, fetch the rest
                if total_replies > len(inline) and len(inline) > 0:
                    extra = await fetch_replies_for_thread(thread_id, api_key, client)
                    # avoid duplicates: extra already contains all replies
                    comments.extend(extra[len(inline):])

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break

    return comments, video_title


def filter_comments_by_user(
    comments: List[Dict[str, Any]], username: str
) -> List[Dict[str, Any]]:
    """Case-insensitive search for username in author display name."""
    query = username.strip().lower()
    return [c for c in comments if query in c["author"].lower()]


def make_comment_dict(snippet: dict, reply_to_id: str = "") -> dict:
    """Build a unified comment dict from an API snippet block."""
    return {
        "author":              snippet.get("authorDisplayName", "Unknown"),
        "author_channel_url":  snippet.get("authorChannelUrl", "#"),
        "author_profile_image":snippet.get("authorProfileImageUrl", ""),
        "text":               snippet.get("textDisplay", ""),
        "text_plain":         snippet.get("textOriginal", snippet.get("textDisplay", "")),
        "likes":              snippet.get("likeCount", 0),
        "published_at":       snippet.get("publishedAt", ""),
        "updated_at":         snippet.get("updatedAt", ""),
        "reply_count":        0,
        "is_reply":           bool(reply_to_id),
        "reply_to_id":        reply_to_id,
    }


async def fetch_replies_for_thread(
    parent_id: str, api_key: str, client: httpx.AsyncClient
) -> List[Dict[str, Any]]:
    """Fetch ALL replies for a single comment thread via comments.list."""
    replies: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            "part": "snippet",
            "parentId": parent_id,
            "maxResults": 100,
            "key": api_key,
        }
        if page_token:
            params["pageToken"] = page_token
        resp = await client.get(f"{YOUTUBE_API_BASE}/comments", params=params)
        if resp.status_code != 200:
            break  # best-effort; skip failed reply pages
        data = resp.json()
        for item in data.get("items", []):
            replies.append(make_comment_dict(item["snippet"], reply_to_id=parent_id))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return replies


def strip_html(text: str) -> str:
    """Strip HTML tags and decode HTML entities for reliable plain-text comparison."""
    # Decode HTML entities first (&amp; → &, &#39; → ', etc.)
    text = html_module.unescape(text)
    # Remove HTML tags (<a href="...">, <br>, etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def filter_comments_by_keyword(
    comments: List[Dict[str, Any]], keyword: str
) -> List[Dict[str, Any]]:
    """Case-insensitive search for keyword in comment text (HTML-stripped)."""
    query = keyword.strip().lower()
    return [
        c for c in comments
        if query in strip_html(c.get("text", "")).lower()
        or query in strip_html(c.get("text_plain", "")).lower()
    ]


def format_date(iso_str: str) -> str:
    """Convert ISO 8601 string to a readable format."""
    if not iso_str:
        return ""
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y, %H:%M UTC")
    except Exception:
        return iso_str

# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main search page with default values pre-filled."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_url": DEFAULT_VIDEO_URL,
            "results": None,
            "error": None,
            "total_comments": 0,
            "video_title": "",
            "video_thumbnail": "",
            "search_url": "",
            "search_username": "",
            "search_keyword": "",
        },
    )


# ─── SSE progress generator ───────────────────────────────────────────────────

def sse(event: str, data: Any) -> str:
    """Format a single SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def search_stream(
    request: Request, url: str, username: str, keyword: str
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields SSE events:
      stats   – { video_title, video_thumbnail, comment_count } (sent before scanning)
      log     – progress messages
      result  – a single comment dict
      done    – final summary { total, matched, video_title, video_thumbnail, stopped }
      error   – { message }
    """
    try:
        api_key = YOUTUBE_API_KEY
        if not api_key:
            yield sse("error", {"message": "YOUTUBE_API_KEY is not set in .env"})
            return

        url = url.strip()
        username = username.strip()
        keyword = keyword.strip()

        video_id = extract_video_id(url)
        if not video_id:
            yield sse("error", {"message": "Could not parse a valid YouTube video ID from the URL."})
            return

        yield sse("log", {"msg": f"Parsed video ID: {video_id}"})
        video_thumbnail = build_thumbnail_url(video_id)

        async with httpx.AsyncClient(timeout=20.0) as client:
            info = await fetch_video_info(video_id, api_key, client)
            video_title = info["title"]
            comment_count = info["comment_count"]

            # Send video metadata + total count before scanning starts
            yield sse("stats", {
                "video_title": video_title,
                "video_thumbnail": video_thumbnail,
                "comment_count": comment_count,
            })
            yield sse("log", {"msg": f"Video: {video_title}"})
            yield sse("log", {"msg": f"Total comments on video: {comment_count:,}"})

            page = 0
            total_fetched = 0
            matched = 0
            next_page_token: Optional[str] = None
            stopped = False

            while True:
                # Check if client closed the connection (Stop button)
                if await request.is_disconnected():
                    stopped = True
                    break

                page += 1
                yield sse("log", {"msg": f"Fetching page {page}…"})

                params: Dict[str, Any] = {
                    "part": "snippet,replies",
                    "videoId": video_id,
                    "maxResults": MAX_RESULTS_PER_PAGE,
                    "order": "time",
                    "key": api_key,
                }
                if next_page_token:
                    params["pageToken"] = next_page_token

                resp = await client.get(
                    f"{YOUTUBE_API_BASE}/commentThreads",
                    params=params,
                )

                if resp.status_code != 200:
                    error_detail = resp.json().get("error", {})
                    msg = error_detail.get("message", "Unknown API error")
                    yield sse("error", {"message": f"YouTube API error {resp.status_code}: {msg}"})
                    return

                data = resp.json()
                items = data.get("items", [])
                thread_count = len(items)
                reply_count_this_page = 0

                for item in items:
                    thread_id = item["id"]
                    top_snippet = item["snippet"]["topLevelComment"]["snippet"]
                    total_replies = item["snippet"].get("totalReplyCount", 0)

                    comment: Dict[str, Any] = make_comment_dict(top_snippet)
                    comment["reply_count"] = total_replies
                    comment["published_at_fmt"] = format_date(comment["published_at"])

                    # Apply filters to top-level comment
                    user_ok = (not username) or (username.lower() in comment["author"].lower())
                    _text_clean = strip_html(comment.get("text", "")) + " " + strip_html(comment.get("text_plain", ""))
                    kw_ok = (not keyword) or (keyword.lower() in _text_clean.lower())
                    if user_ok and kw_ok:
                        matched += 1
                        yield sse("result", comment)

                    # --- Replies ---
                    inline_replies = item.get("replies", {}).get("comments", [])
                    all_replies = [make_comment_dict(r["snippet"], reply_to_id=thread_id) for r in inline_replies]

                    # Fetch remaining replies if more than inline batch
                    if total_replies > len(inline_replies) and inline_replies:
                        extra = await fetch_replies_for_thread(thread_id, api_key, client)
                        all_replies = extra  # full set from API
                    elif total_replies > 0 and not inline_replies:
                        # No inline replies in response; fetch directly
                        all_replies = await fetch_replies_for_thread(thread_id, api_key, client)

                    reply_count_this_page += len(all_replies)
                    for reply in all_replies:
                        reply["published_at_fmt"] = format_date(reply["published_at"])
                        r_user_ok = (not username) or (username.lower() in reply["author"].lower())
                        r_text = strip_html(reply.get("text", "")) + " " + strip_html(reply.get("text_plain", ""))
                        r_kw_ok = (not keyword) or (keyword.lower() in r_text.lower())
                        if r_user_ok and r_kw_ok:
                            matched += 1
                            yield sse("result", reply)

                total_fetched += thread_count + reply_count_this_page
                pct = f" ({100*total_fetched//comment_count}%)" if comment_count else ""
                yield sse("log", {"msg": f"Page {page}: {thread_count} threads + {reply_count_this_page} replies — {total_fetched:,}/{comment_count:,} scanned{pct}"})
                yield sse("progress", {"scanned": total_fetched, "total": comment_count, "matched": matched})

                # small pause so the event loop can flush
                await asyncio.sleep(0)

                next_page_token = data.get("nextPageToken")
                if not next_page_token:
                    break

        status = "Stopped early" if stopped else "Done"
        yield sse("log", {"msg": f"{status}. Scanned {total_fetched:,} / {comment_count:,} comments, found {matched} match(es)."})
        yield sse("done", {
            "total": total_fetched,
            "comment_count": comment_count,
            "matched": matched,
            "video_title": video_title,
            "video_thumbnail": video_thumbnail,
            "stopped": stopped,
        })

    except Exception as exc:
        yield sse("error", {"message": str(exc)})


@app.get("/stream-search")
async def stream_search(
    request: Request,
    url: str = "",
    username: str = "",
    keyword: str = "",
):
    """SSE endpoint – streams search progress and results."""
    return StreamingResponse(
        search_stream(request, url, username, keyword),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/search", response_class=HTMLResponse)
async def search_comments(
    request: Request,
    url: str = Form(...),
    username: str = Form(...),
    keyword: str = Form(""),
):
    """
    Fallback non-JS search (POST). Fetches all comments then filters.
    """
    error: Optional[str] = None
    results: List[Dict[str, Any]] = []
    total_comments: int = 0
    video_title: str = ""
    video_thumbnail: str = ""

    try:
        url = url.strip()
        username = username.strip()
        keyword = keyword.strip()
        api_key = YOUTUBE_API_KEY

        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is not set. Add it to your .env file.")

        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError(
                "Could not parse a valid YouTube video ID from the URL. "
                "Supported formats: watch?v=, /shorts/, youtu.be/, /embed/"
            )

        video_thumbnail = build_thumbnail_url(video_id)
        all_comments, video_title = await fetch_all_comments(video_id, api_key)
        total_comments = len(all_comments)

        results = all_comments
        if username:
            results = filter_comments_by_user(results, username)
        if keyword:
            results = filter_comments_by_keyword(results, keyword)

        for c in results:
            c["published_at_fmt"] = format_date(c["published_at"])

    except RuntimeError as exc:
        error = str(exc)
    except ValueError as exc:
        error = str(exc)
    except Exception as exc:
        error = f"Unexpected error: {exc}"

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "default_url": DEFAULT_VIDEO_URL,
            "results": results,
            "error": error,
            "total_comments": total_comments,
            "video_title": video_title,
            "video_thumbnail": video_thumbnail,
            "search_url": url,
            "search_username": username,
            "search_keyword": keyword,
        },
    )
