"""사용자 / 인증 — REST 엔드포인트.

- POST /api/v1/auth/login   : 로그인 → access_token 발급
- POST /api/v1/auth/logout  : 현재 세션 무효화
- GET  /api/v1/users/me     : 현재 로그인 사용자 정보 (사이드바·프로필·검사자 자동 채움)
- POST /api/v1/users        : 사용자 등록 (admin 전용)
"""

from fastapi import APIRouter, Depends, status

from app.core.response import ApiResponse, success_response
from app.models.user import User, UserRole
from app.schemas.user import LoginRequest, LoginResponse, UserCreate, UserRead
from app.services.auth import current_user, require_role
from app.services.user_service import create_user, login, logout

auth_router = APIRouter(prefix="/auth", tags=["auth"])
users_router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post(
    "/login",
    response_model=ApiResponse[LoginResponse],
    summary="로그인 (세션 토큰 발급)",
)
async def login_endpoint(payload: LoginRequest):
    user, token, expires_at = await login(
        username=payload.username, password=payload.password
    )
    body = LoginResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserRead.from_document(user),
    )
    return success_response(data=body.model_dump(mode="json"), message="OK")


@auth_router.post(
    "/logout",
    response_model=ApiResponse[dict],
    summary="로그아웃 (현재 세션 무효화)",
)
async def logout_endpoint(user: User = Depends(current_user)):
    await logout(user)
    return success_response(data={"username": user.username}, message="Logged out")


@users_router.get(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="현재 로그인 사용자 정보",
)
async def get_me_endpoint(user: User = Depends(current_user)):
    return success_response(
        data=UserRead.from_document(user).model_dump(mode="json")
    )


@users_router.post(
    "",
    response_model=ApiResponse[UserRead],
    status_code=status.HTTP_201_CREATED,
    summary="사용자 등록 (admin)",
)
async def create_user_endpoint(
    payload: UserCreate,
    _: User = Depends(require_role(UserRole.ADMIN)),
):
    user = await create_user(
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
    )
    return success_response(
        data=UserRead.from_document(user).model_dump(mode="json"),
        message="Created",
        code=201,
    )
