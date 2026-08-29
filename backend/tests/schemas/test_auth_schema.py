import pytest
from pydantic import ValidationError

from app.schemas.auth_schema import SignupRequest

VALID_PASSWORD = "correct-password"


def make_signup_request(
    **overrides: object,
) -> dict[str, object]:
    """정상 회원가입 요청 데이터를 생성한다."""

    request: dict[str, object] = {
        "login_id": "trend_user01",
        "password": VALID_PASSWORD,
        "password_confirm": VALID_PASSWORD,
        "name": "김트렌드",
        "email": "trend@example.com",
    }

    request.update(overrides)

    return request


@pytest.mark.parametrize(
    "login_id",
    [
        "user",
        "user123",
        "trend_user01",
        "a___",
        "a" * 50,
    ],
)
def test_signup_request_accepts_valid_login_id(
    login_id: str,
) -> None:
    """정책에 맞는 로그인 ID를 허용한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            login_id=login_id,
        )
    )

    assert request.login_id == login_id


@pytest.mark.parametrize(
    "login_id",
    [
        "abc",
        "a" * 51,
        "Trend_user",
        "1trend_user",
        "_trend_user",
        "trend-user",
        "한재user",
        "trend user",
    ],
)
def test_signup_request_rejects_invalid_login_id(
    login_id: str,
) -> None:
    """정책에 맞지 않는 로그인 ID를 거부한다."""

    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            make_signup_request(
                login_id=login_id,
            )
        )


@pytest.mark.parametrize(
    "password",
    [
        "a" * 15,
        "a" * 128,
    ],
)
def test_signup_request_accepts_password_length_boundaries(
    password: str,
) -> None:
    """15~128자의 비밀번호를 허용한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            password=password,
            password_confirm=password,
        )
    )

    assert (
        request.password.get_secret_value()
        == password
    )


@pytest.mark.parametrize(
    "password",
    [
        "a" * 14,
        "a" * 129,
    ],
)
def test_signup_request_rejects_invalid_password_length(
    password: str,
) -> None:
    """15~128자를 벗어난 비밀번호를 거부한다."""

    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            make_signup_request(
                password=password,
                password_confirm=password,
            )
        )


def test_signup_request_does_not_trim_password() -> None:
    """비밀번호의 앞뒤 공백을 임의로 제거하지 않는다."""

    password = " abcdefghijklm "

    request = SignupRequest.model_validate(
        make_signup_request(
            password=password,
            password_confirm=password,
        )
    )

    assert (
        request.password.get_secret_value()
        == password
    )


def test_signup_request_rejects_password_confirm_mismatch() -> None:
    """비밀번호 확인 값이 다르면 거부한다."""

    with pytest.raises(
        ValidationError,
    ) as exc_info:
        SignupRequest.model_validate(
            make_signup_request(
                password_confirm="different-password",
            )
        )

    assert (
        exc_info.value.errors()[0]["loc"]
        == ("password_confirm",)
    )


def test_signup_request_trims_name() -> None:
    """사용자 이름의 앞뒤 공백을 제거한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            name="   김트렌드   ",
        )
    )

    assert request.name == "김트렌드"


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "   ",
    ],
)
def test_signup_request_rejects_blank_name(
    name: str,
) -> None:
    """빈 이름과 공백으로만 이루어진 이름을 거부한다."""

    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            make_signup_request(
                name=name,
            )
        )


def test_signup_request_validates_name_after_trim() -> None:
    """이름을 trim한 뒤 최대 길이를 검증한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            name=f"  {'가' * 50}  ",
        )
    )

    assert request.name == "가" * 50


@pytest.mark.parametrize(
    "email",
    [
        None,
        "",
        " ",
        "   ",
    ],
)
def test_signup_request_normalizes_empty_email_to_none(
    email: str | None,
) -> None:
    """비어 있는 선택 이메일을 None으로 정규화한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            email=email,
        )
    )

    assert request.email is None


def test_signup_request_allows_omitted_email() -> None:
    """이메일 필드 자체가 누락되어도 회원가입 요청을 허용한다."""

    request_data = make_signup_request()
    del request_data["email"]

    request = SignupRequest.model_validate(
        request_data
    )

    assert request.email is None


def test_signup_request_normalizes_email() -> None:
    """이메일의 앞뒤 공백과 대소문자를 정규화한다."""

    request = SignupRequest.model_validate(
        make_signup_request(
            email="  Trend.User@Example.COM  ",
        )
    )

    assert (
        str(request.email)
        == "trend.user@example.com"
    )


def test_signup_request_rejects_invalid_email() -> None:
    """형식이 올바르지 않은 이메일을 거부한다."""

    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            make_signup_request(
                email="not-an-email",
            )
        )


def test_signup_request_rejects_email_longer_than_255_characters() -> None:
    """255자를 초과하는 이메일을 거부한다."""

    email = f"{'a' * 244}@example.com"

    assert len(email) == 256

    with pytest.raises(ValidationError):
        SignupRequest.model_validate(
            make_signup_request(
                email=email,
            )
        )
