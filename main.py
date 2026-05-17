"""
Instagram Comment-to-DM Automation — FastAPI Entry Point
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from database import init_db
from routes.api import router as api_router
from routes.dashboard import router as dashboard_router
from routes.webhook import router as webhook_router

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


# ---------------------------------------------------------------------------
# App lifespan (startup/shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising database…")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down.")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Instagram Automation",
    description="Comment-to-DM automation powered by the Instagram Graph API",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(webhook_router)
app.include_router(api_router)
app.include_router(dashboard_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}
