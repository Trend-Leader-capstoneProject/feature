"""Trend Leader ORM 모델에서 사용하는 데이터베이스 Enum."""

from enum import Enum


def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """SQLAlchemy Enum에 저장할 실제 문자열 값 목록을 반환한다."""

    return [str(member.value) for member in enum_class]


class OAuthProvider(str, Enum):
    """지원하는 OAuth 제공자."""

    GOOGLE = "GOOGLE"


class UserStatus(str, Enum):
    """사용자 계정 상태."""

    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    SUSPENDED = "SUSPENDED"


class TrendStatus(str, Enum):
    """트렌드 조회 가능 상태."""

    ACTIVE = "ACTIVE"
    HIDDEN = "HIDDEN"


class TrendSourcePlatform(str, Enum):
    """트렌드 출처 플랫폼 허용값."""

    GOOGLE = "GOOGLE"
    YOUTUBE = "YOUTUBE"
    SNS = "SNS"
    ETC = "ETC"


class RelatedKeywordType(str, Enum):
    """AI 분석 관련 키워드 유형."""

    RELATED = "RELATED"
    HASHTAG = "HASHTAG"
    RECOMMENDED = "RECOMMENDED"
    
class CategoryCode(str, Enum):
    """대분류 식별 코드."""

    FASHION = "FASHION"
    FOOD = "FOOD"
    IT_DIGITAL = "IT_DIGITAL"
    ENTERTAINMENT = "ENTERTAINMENT"
    BEAUTY = "BEAUTY"
    GAME = "GAME"
    