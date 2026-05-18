"""부팅 시 기본 admin 사용자 시드.

이미 존재하면 no-op. 비밀번호는 환경 변수 `ADMIN_PASSWORD` 우선, 없으면
개발 기본값(`admin1234`). 프로덕션에서는 반드시 .env 로 덮어쓸 것.
"""

import logging
import os

from app.models.user import UserRole
from app.services.user_service import create_user, get_user_by_username

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_DISPLAY_NAME = "관리자"
DEFAULT_ADMIN_PASSWORD = "admin1234"


async def seed_default_admin() -> None:
    existing = await get_user_by_username(DEFAULT_ADMIN_USERNAME)
    if existing is not None:
        logger.info("admin user already present (id=%s)", existing.id)
        return

    password = os.environ.get("ADMIN_PASSWORD") or DEFAULT_ADMIN_PASSWORD
    await create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password=password,
        display_name=DEFAULT_ADMIN_DISPLAY_NAME,
        role=UserRole.ADMIN,
    )
    logger.info(
        "default admin user seeded (username=%s, password_from_env=%s)",
        DEFAULT_ADMIN_USERNAME,
        "ADMIN_PASSWORD" in os.environ,
    )
