from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, SecretStr, field_validator

from app.core.nickname import normalize_nickname

Nickname = Annotated[str, BeforeValidator(normalize_nickname)]


class NicknameRequest(BaseModel):
    nickname: Nickname


class NicknameAvailability(BaseModel):
    nickname: str
    is_available: bool
    reason: Literal["DUPLICATED_NICKNAME"] | None = None


class ProfileData(BaseModel):
    user_id: int
    nickname: str
    profile_image_url: str | None


class VerifyPasswordRequest(BaseModel):
    current_password: SecretStr


class PasswordChangeRequest(VerifyPasswordRequest):
    new_password: SecretStr
    new_password_confirm: SecretStr

    @field_validator("new_password")
    @classmethod
    def validate_length(cls, value: SecretStr) -> SecretStr:
        if not 8 <= len(value.get_secret_value()) <= 128:
            raise ValueError("비밀번호는 8~128자여야 합니다.")
        return value

    @field_validator("new_password_confirm")
    @classmethod
    def validate_confirmation(cls, value: SecretStr, info) -> SecretStr:
        password = info.data.get("new_password")
        if password and value.get_secret_value() != password.get_secret_value():
            raise ValueError("비밀번호 확인이 일치하지 않습니다.")
        return value
