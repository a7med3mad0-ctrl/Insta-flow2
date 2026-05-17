import logging
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import instagram as ig
from database import get_db
from models import Campaign, Config, ProcessedComment

logger = logging.getLogger("api")
router = APIRouter(prefix="/api")

class ConfigIn(BaseModel):
    access_token: str
    page_id: str
    instagram_account_id: str

class CampaignIn(BaseModel):
    name: str
    post_id: str
    keywords: str
    comment_reply: str
    dm_message: str
    is_active: bool = True
    post_thumbnail_url: str | None = None
    post_caption: str | None = None

class CampaignUpdate(BaseModel):
    name: str | None = None
    post_id: str | None = None
    keywords: str | None = None
    comment_reply: str | None = None
    dm_message: str | None = None
    is_active: bool | None = None
    post_thumbnail_url: str | None = None
    post_caption: str | None = None

@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db)):
    config = await db.scalar(select(Config).where(Config.id == 1))
    if not config:
        return {"access_token_set": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN")), "page_id": os.getenv("FACEBOOK_PAGE_ID", ""), "instagram_account_id": os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", ""), "source": "environment"}
    return {"access_token_set": bool(config.access_token), "page_id": config.page_id or "", "instagram_account_id": config.instagram_account_id or "", "updated_at": config.updated_at.isoformat() if config.updated_at else None, "source": "database"}

@router.post("/config")
async def save_config(data: ConfigIn, db: AsyncSession = Depends(get_db)):
    config = await db.scalar(select(Config).where(Config.id == 1))
    if not config:
        config = Config(id=1)
        db.add(config)
    config.access_token = data.access_token
    config.page_id = data.page_id
    config.instagram_account_id = data.instagram_account_id
    config.updated_at = datetime.utcnow()
    await db.commit()
    return {"status": "saved"}

@router.post("/config/verify")
async def verify_config(db: AsyncSession = Depends(get_db)):
    config = await db.scalar(select(Config).where(Config.id == 1))
    token = (config.access_token if config else None) or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    ig_id = (config.instagram_account_id if config else None) or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")
    if not token or not ig_id:
        raise HTTPException(status_code=400, detail="Credentials not configured")
    try:
        account = await ig.verify_credentials(token, ig_id)
        return {"status": "valid", "account": account}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/campaigns")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(desc(Campaign.created_at)))
    return [_campaign_dict(c) for c in result.scalars().all()]

@router.post("/campaigns")
async def create_campaign(data: CampaignIn, db: AsyncSession = Depends(get_db)):
    campaign = Campaign(**data.model_dump())
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return _campaign_dict(campaign)

@router.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: int, data: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    campaign = await db.scalar(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    campaign.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(campaign)
    return _campaign_dict(campaign)

@router.patch("/campaigns/{campaign_id}/toggle")
async def toggle_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    campaign = await db.scalar(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    campaign.is_active = not campaign.is_active
    campaign.updated_at = datetime.utcnow()
    await db.commit()
    return {"id": campaign.id, "is_active": campaign.is_active}

@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: int, db: AsyncSession = Depends(get_db)):
    campaign = await db.scalar(select(Campaign).where(Campaign.id == campaign_id))
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.delete(campaign)
    await db.commit()
    return {"status": "deleted"}

@router.get("/post-preview")
async def post_preview(post_id: str, db: AsyncSession = Depends(get_db)):
    config = await db.scalar(select(Config).where(Config.id == 1))
    token = (config.access_token if config else None) or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token:
        raise HTTPException(status_code=400, detail="Token not configured")
    try:
        return await ig.get_post_details(post_id, token=token)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.get("/activity")
async def get_activity(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProcessedComment).order_by(desc(ProcessedComment.processed_at)).limit(limit))
    return [{"id": r.id, "comment_id": r.comment_id, "campaign_id": r.campaign_id, "commenter_id": r.commenter_id, "matched_keyword": r.matched_keyword, "comment_reply_sent": r.comment_reply_sent, "dm_sent": r.dm_sent, "processed_at": r.processed_at.isoformat()} for r in result.scalars().all()]

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    total = await db.scalar(select(func.count()).select_from(Campaign))
    active = await db.scalar(select(func.count()).select_from(Campaign).where(Campaign.is_active == True))
    triggers = await db.scalar(select(func.count()).select_from(ProcessedComment))
    dms = await db.scalar(select(func.count()).select_from(ProcessedComment).where(ProcessedComment.dm_sent == True))
    return {"total_campaigns": total or 0, "active_campaigns": active or 0, "total_triggers": triggers or 0, "dms_sent": dms or 0}

def _campaign_dict(c: Campaign) -> dict:
    return {"id": c.id, "name": c.name, "post_id": c.post_id, "post_thumbnail_url": c.post_thumbnail_url, "post_caption": c.post_caption, "keywords": c.keywords, "comment_reply": c.comment_reply, "dm_message": c.dm_message, "is_active": c.is_active, "trigger_count": c.trigger_count or 0, "created_at": c.created_at.isoformat() if c.created_at else None, "updated_at": c.updated_at.isoformat() if c.updated_at else None}
