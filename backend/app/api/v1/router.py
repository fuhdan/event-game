"""API v1 router — assembles all versioned sub-routers."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")

# Phase 1+: include sub-routers here as they are implemented
# from app.api.v1 import auth, teams, events
# router.include_router(auth.router)
# router.include_router(teams.router)
# router.include_router(events.router)
