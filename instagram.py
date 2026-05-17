"""
Instagram Graph API client.
Handles comment replies, DMs, and post detail fetching.
All calls are async, with retry/backoff on rate limits.
"""
import asyncio
import logging
import os
from typing import Any

import aiohttp
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("instagram")

GRAPH_BASE = "https://graph.facebook.com/v19.0"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_token() -> str:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    if not token:
        raise ValueError("INSTAGRAM_ACCESS_TOKEN is not set in environment / config.")
    return token


async def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    params: dict | None = None,
    json: dict | None = None,
    retries: int = 3,
) -> dict[str, Any]:
    """
    Perform an async HTTP request against the Graph API.
    Retries up to `retries` times on rate-limit (error code 4 / 32 / 613)
    or transient 5xx errors, with exponential back-off.
    """
    tok = token or _get_token()
    url = f"{GRAPH_BASE}{path}"
    base_params = {"access_token": tok}
    if params:
        base_params.update(params)

    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                req_kwargs: dict = {"params": base_params}
                if json is not None:
                    req_kwargs["json"] = json
                async with getattr(session, method)(url, **req_kwargs) as resp:
                    data = await resp.json()

                    # Log every API response for debugging
                    status = resp.status
                    logger.info("Graph API %s %s → %d | body=%s", method.upper(), path, status, data)

                    if status == 200:
                        return data

                    # Rate-limit codes: 4 (App-level), 32 (Page-level), 613 (Custom)
                    error = data.get("error", {})
                    ec = error.get("code", 0)
                    if status == 400 and ec in (4, 32, 613, 17):
                        wait = 2 ** attempt * 5  # 5 s, 10 s, 20 s …
                        logger.warning(
                            "Rate limited (code %d). Waiting %ds before retry %d/%d.",
                            ec, wait, attempt + 1, retries,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Non-retriable API error
                    raise RuntimeError(f"Graph API error {status}: {data}")

        except aiohttp.ClientError as exc:
            last_exc = exc
            wait = 2 ** attempt
            logger.warning("Network error: %s. Retrying in %ds…", exc, wait)
            await asyncio.sleep(wait)

    raise RuntimeError(f"Graph API request failed after {retries} retries.") from last_exc


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------

async def reply_to_comment(comment_id: str, message: str, token: str | None = None) -> dict:
    """
    Post a public reply to an Instagram comment.
    Docs: POST /{comment-id}/replies
    """
    logger.info("Replying to comment %s", comment_id)
    result = await _request(
        "post",
        f"/{comment_id}/replies",
        token=token,
        json={"message": message},
    )
    logger.info("Comment reply result: %s", result)
    return result


async def send_dm(instagram_user_id: str, message: str, ig_account_id: str, token: str | None = None) -> dict:
    """
    Send a private DM to a user via the Instagram Messaging API.

    IMPORTANT: The recipient must have previously messaged the business,
    OR the business has the 'instagram_manage_messages' permission approved
    for proactive messaging. See README for full details.

    Docs: POST /{ig-account-id}/messages
    """
    logger.info("Sending DM to user %s via account %s", instagram_user_id, ig_account_id)
    payload = {
        "recipient": {"id": instagram_user_id},
        "message": {"text": message},
    }
    result = await _request(
        "post",
        f"/{ig_account_id}/messages",
        token=token,
        json=payload,
    )
    logger.info("DM result: %s", result)
    return result


async def get_post_details(post_id: str, token: str | None = None) -> dict:
    """
    Fetch thumbnail URL and caption for a given Instagram media post ID.
    Docs: GET /{media-id}?fields=...
    """
    logger.info("Fetching post details for %s", post_id)
    data = await _request(
        "get",
        f"/{post_id}",
        token=token,
        params={
            "fields": "id,caption,media_type,media_url,thumbnail_url,timestamp,permalink"
        },
    )
    return {
        "id": data.get("id"),
        "caption": data.get("caption", ""),
        "media_type": data.get("media_type", ""),
        "thumbnail_url": data.get("thumbnail_url") or data.get("media_url", ""),
        "timestamp": data.get("timestamp", ""),
        "permalink": data.get("permalink", ""),
    }


async def verify_credentials(token: str, ig_account_id: str) -> dict:
    """
    Quick check that the provided credentials are valid.
    Returns basic account info or raises on error.
    """
    data = await _request(
        "get",
        f"/{ig_account_id}",
        token=token,
        params={"fields": "id,name,username,followers_count"},
    )
    return data
