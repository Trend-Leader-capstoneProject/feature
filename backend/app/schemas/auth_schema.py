from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from app.models.db_enums import UserStatus


class LoginRequest(BaseModel):
    """일반 로그인 요청 Schema."""

    login_id: str = Field(
        min_length=1,
        max_length=50,
        description="로그인 ID",
    )
    
    password: SecretStr


class LoginUserData(BaseModel):
    """로그인 성공 응답에 포함되는 사용자 기본 정보."""
    
    user_id: int
    login_id: str
    name: str
    status: UserStatus
    
    
class LoginData(BaseModel):
    """로그인 성공 응답의 실제 데이터."""
    
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    user: LoginUserData
    has_selected_interests: bool
    next_step: Literal[
        "MAIN",
        "INTEREST_SELECTION",
    ]
    
