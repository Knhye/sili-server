"""부팅 시 기본 admin 사용자 시드.

이미 존재하면 no-op. 비밀번호는 반드시 환경 변수 `ADMIN_PASSWORD` 로 지정해야 한다.
환경 변수가 없으면 시드를 건너뛰고 경고 로그를 남긴다.
"""

import logging
import os

from app.models.user import UserRole
from app.services.user_service import create_user, get_user_by_username

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_DISPLAY_NAME = "관리자"


async def seed_default_admin() -> None:
    password = os.environ.get("ADMIN_PASSWORD")
    if not password:
        logger.warning(
            "ADMIN_PASSWORD env var is not set — skipping default admin seed. "
            "Set ADMIN_PASSWORD in .env to create the initial admin account."
        )
        return

    existing = await get_user_by_username(DEFAULT_ADMIN_USERNAME)
    if existing is not None:
        logger.info("admin user already present (id=%s)", existing.id)
        return

    await create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password=password,
        display_name=DEFAULT_ADMIN_DISPLAY_NAME,
        role=UserRole.ADMIN,
    )
    logger.info("default admin user seeded (username=%s)", DEFAULT_ADMIN_USERNAME)
