from fastapi import APIRouter

from app.api.v1 import config, parts, reinspection, weld_events

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(parts.router)
api_router.include_router(weld_events.router)
api_router.include_router(reinspection.router)
