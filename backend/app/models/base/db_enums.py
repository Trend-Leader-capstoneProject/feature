"""Trend Leader ORM 모델에서 사용하는 데이터베이스 Enum."""

from enum import Enum

def get_enum_values(enum_class: type[Enum]) -> list[str]:
    """SQLAlchemy Enum에 저장할 실제 문자열 값 목록을 반환한다."""
    
    return [str(member.value) for member in enum_class]


class CategoryDepth(str, Enum):
    MAIN = "1:대분류"
    SUB = "2:세부분류"


class OAuthProvider(str, Enum):
    GOOGLE = "GOOGLE"


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    SUSPENDED = "SUSPENDED"


class TrendStatus(str, Enum):
    ACTIVE = "ACTIVE"
    HIDDEN = "HIDDEN"


class RankChange(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    SAME = "SAME"
    NEW = "NEW"


class AiModelName(str, Enum):
    GPT = "GPT"
    GEMINI = "GEMINI"
    CLAUDE = "CLAUDE"
    ETC = "ETC"


class TrendSourcePlatform(str, Enum):
    GOOGLE = "GOOGLE"
    YOUTUBE = "YOUTUBE"
    SNS = "SNS"
    ETC = "ETC"


class RelatedKeywordType(str, Enum):
    RELATED = "RELATED"
    HASHTAG = "HASHTAG"
    RECOMMENDED = "RECOMMENDED"