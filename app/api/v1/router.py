from fastapi import APIRouter

from app.api.v1 import config, parts

api_router = APIRouter()
api_router.include_router(config.router)
api_router.include_router(parts.router)
