"""사용자 / 인증 — Pydantic DTO."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import User, UserRole


class LoginRequest(BaseModel):
    """`POST /api/v1/auth/login` 요청 본문."""

    username: str = Field(
        ..., min_length=3, max_length=64, examples=["admin"]
    )
    password: str = Field(
        ..., min_length=1, max_length=200, examples=["admin1234"]
    )


class LoginResponse(BaseModel):
    """`POST /api/v1/auth/login` 응답 본문."""

    access_token: str = Field(
        ..., description="Authorization: Bearer 헤더에 그대로 사용."
    )
    token_type: str = Field(default="bearer")
    expires_at: datetime = Field(..., description="토큰 만료 시각 (UTC).")
    user: "UserRead"


class UserCreate(BaseModel):
    """`POST /api/v1/users` 요청 본문 (admin)."""

    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=4, max_length=200)
    display_name: str = Field(..., max_length=120)
    role: UserRole = Field(default=UserRole.WORKER)


class UserRead(BaseModel):
    """`GET /api/v1/users/me` 등 응답 본문 (민감 필드 제외)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    display_name: str
    role: UserRole
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def from_document(cls, doc: User) -> "UserRead":
        return cls(
            id=str(doc.id),
            username=doc.username,
            display_name=doc.display_name,
            role=doc.role,
            created_at=doc.created_at,
            last_login_at=doc.last_login_at,
        )


# 순환 참조 해소.
LoginResponse.model_rebuild()
