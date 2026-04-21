"""
ColdPilot API — FastAPI entry point.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from backend import db
from backend.scheduler.scheduler import start_scheduler, stop_scheduler
from backend.routers import campaigns, prospects, emails, activity, settings, tracking


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await db.init_db()
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="ColdPilot",
    description="Autonomous cold outreach agent API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[dashboard_url, "http://localhost:3000", "https://coldpilot-dashboard.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(campaigns.router)
app.include_router(prospects.router)
app.include_router(emails.router)
app.include_router(activity.router)
app.include_router(settings.router)
app.include_router(tracking.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "coldpilot"}
