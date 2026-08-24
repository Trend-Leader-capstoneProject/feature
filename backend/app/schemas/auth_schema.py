from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    ValidationInfo,
    field_validator,
)

from app.models.db_enums import UserStatus

AuthNextStep = Literal[
    "MAIN",
    "INTEREST_SELECTION",
]

SignupConflictField = Literal[
    "login_id",
    "email",
]

SignupConflictReason = Literal[
    "DUPLICATED_LOGIN_ID",
    "DUPLICATED_EMAIL",
]

LoginIdAvailabilityReason = Literal[
    "DUPLICATED_LOGIN_ID",
]

LOGIN_ID_PATTERN = r"^[a-z][a-z0-9_]*$"

class LoginRequest(BaseModel):
    """일반 로그인 요청 Schema."""

    login_id: str = Field(
        min_length=1,
        max_length=50,
        description="로그인 ID",
    )

    password: SecretStr


class SignupRequest(BaseModel):
    """일반 회원가입 요청 Schema."""

    login_id: str = Field(
        min_length=4,
        max_length=50,
        pattern=LOGIN_ID_PATTERN,
        description="로그인 ID",
    )

    password: SecretStr
    password_confirm: SecretStr

    name: str = Field(
        min_length=1,
        max_length=50,
        description="사용자 이름",
    )

    email: EmailStr | None = None

    @field_validator("password")
    @classmethod
    def validate_password_length(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        """비밀번호 길이를 검증하되 원문을 정규화하지 않는다."""

        password = value.get_secret_value()

        if not 15 <= len(password) <= 128:
            raise ValueError(
                "비밀번호는 15자 이상 128자 이하여야 합니다."
            )

        return value

    @field_validator("password_confirm")
    @classmethod
    def validate_password_confirm(
        cls,
        value: SecretStr,
        info: ValidationInfo,
    ) -> SecretStr:
        """비밀번호 확인 값이 비밀번호와 정확히 일치하는지 검증한다."""

        password = info.data.get("password")

        if (
            isinstance(password, SecretStr)
            and value.get_secret_value()
            != password.get_secret_value()
        ):
            raise ValueError(
                "비밀번호 확인이 일치하지 않습니다."
            )

        return value

    @field_validator(
        "name",
        mode="before",
    )
    @classmethod
    def normalize_name(
        cls,
        value: object,
    ) -> object:
        """사용자 이름의 앞뒤 공백을 제거한다."""

        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator(
        "email",
        mode="before",
    )
    @classmethod
    def normalize_email(
        cls,
        value: object,
    ) -> object:
        """선택 이메일을 정규화한다."""

        if value is None:
            return None

        if not isinstance(value, str):
            return value

        normalized_email = value.strip()

        if not normalized_email:
            return None

        return normalized_email.lower()


class LoginUserData(BaseModel):
    """로그인 성공 응답에 포함되는 사용자 기본 정보."""

    user_id: int
    login_id: str
    name: str
    status: UserStatus


class SessionData(BaseModel):
    """현재 인증 세션 조회 응답의 실제 데이터."""

    user: LoginUserData
    has_selected_interests: bool
    next_step: AuthNextStep

class LoginData(BaseModel):
    """로그인 성공 응답의 실제 데이터."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    user: LoginUserData
    has_selected_interests: bool
    next_step: AuthNextStep

class SignupData(LoginData):
    """회원가입 성공 응답의 실제 데이터."""


class CheckLoginIdData(BaseModel):
    """로그인 ID 사용 가능 여부 조회 응답 데이터."""

    login_id: str
    is_available: bool
    reason: LoginIdAvailabilityReason | None = None


class SignupConflictData(BaseModel):
    """회원가입 중복 충돌의 machine-readable 오류 데이터."""

    field: SignupConflictField
    reason: SignupConflictReason
