import hashlib
import hmac
import json
import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import instagram as ig
from database import get_db
from models import Campaign, Config, ProcessedComment

logger = logging.getLogger("webhook")
router = APIRouter()
WEBHOOK_VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "")
APP_SECRET = os.getenv("FACEBOOK_APP_SECRET", "")

def _validate_signature(body: bytes, signature_header: str | None) -> bool:
    if not APP_SECRET:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_sig = "sha256=" + hmac.new(APP_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_sig, signature_header)

@router.get("/webhook/instagram")
async def verify_webhook(request: Request):
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook/instagram")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not _validate_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") == "comments":
                await _handle_comment_event(change.get("value", {}), db)
    return {"status": "ok"}

async def _handle_comment_event(value: dict, db: AsyncSession):
    comment_id = value.get("id")
    post_id = value.get("media", {}).get("id") or value.get("post_id")
    commenter_id = value.get("from", {}).get("id")
    comment_text = value.get("text", "").strip()
    if not comment_id or not post_id or not comment_text:
        return
    existing = await db.scalar(select(ProcessedComment).where(ProcessedComment.comment_id == comment_id))
    if existing:
        return
    result = await db.execute(select(Campaign).where(Campaign.post_id == post_id, Campaign.is_active == True))
    campaigns = result.scalars().all()
    if not campaigns:
        return
    config = await db.scalar(select(Config).where(Config.id == 1))
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN") or (config.access_token if config else None)
    ig_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID") or (config.instagram_account_id if config else None)
    if not token or not ig_account_id:
        return
    for campaign in campaigns:
        matched_kw = _find_matching_keyword(comment_text, campaign.keyword_list())
        if not matched_kw:
            continue
        comment_ok = False
        dm_ok = False
        try:
            await ig.reply_to_comment(comment_id, campaign.comment_reply, token=token)
            comment_ok = True
        except Exception as exc:
            logger.error("Failed to reply: %s", exc)
        if commenter_id:
            try:
                await ig.send_dm(commenter_id, campaign.dm_message, ig_account_id, token=token)
                dm_ok = True
            except Exception as exc:
                logger.error("Failed to send DM: %s", exc)
        record = ProcessedComment(comment_id=comment_id, campaign_id=campaign.id, commenter_id=commenter_id, matched_keyword=matched_kw, comment_reply_sent=comment_ok, dm_sent=dm_ok)
        db.add(record)
        campaign.trigger_count = (campaign.trigger_count or 0) + 1
        await db.commit()
        break

def _find_matching_keyword(text: str, keywords: list[str]) -> str | None:
    lower = text.lower()
    for kw in keywords:
        if kw in lower:
            return kw
    return None
