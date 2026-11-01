
"""RSS 기술 PoC의 순수 제목·URL 정규화."""
import re
from dataclasses import dataclass
from hashlib import sha256
from ipaddress import ip_address
from unicodedata import category, normalize
from urllib.parse import urlsplit, urlunsplit

MAX_TITLE_LENGTH = 255

_ASCII_LOWER_TABLE = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
)

_HOSTNAME_LABEL = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z"
)

_LEGACY_IP_LABEL = re.compile(
    r"(?:0[xX][0-9a-fA-F]+|[0-9]+)\Z"
)

@dataclass(frozen=True, slots=True)
class NormalizedTitle:
    display_title: str
    normalized_title: str


def normalize_title(raw_title: str) -> NormalizedTitle | None:
    """NFC·Unicode 공백·ASCII 소문자 규칙에 따라 제목을 정규화한다."""
    if not isinstance(raw_title, str):
        raise TypeError("raw_title must be str")

    display_title = " ".join(normalize("NFC", raw_title).split())

    if not display_title or len(display_title) > MAX_TITLE_LENGTH:
        return None

    normalized_title = display_title.translate(_ASCII_LOWER_TABLE)

    if len(normalized_title) > MAX_TITLE_LENGTH:
        return None

    return NormalizedTitle(
        display_title=display_title,
        normalized_title=normalized_title,
    )



_UTM_TRACKING_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    }
)


def remove_utm_tracking_query(raw_query: str) -> str:
    """쿼리 원문에서 정확히 일치하는 UTM 키 5종만 제거한다."""
    return "&".join(
        part
        for part in raw_query.split("&")
        if part.partition("=")[0] not in _UTM_TRACKING_KEYS
    )

def remove_utm_tracking_from_url_unchecked(raw_url: str) -> str:
    """URL 안전성 검증 없이 UTM 쿼리만 제거하는 중간 변환."""
    if not isinstance(raw_url, str):
        raise TypeError("raw_url must be str")

    parts = urlsplit(raw_url)
    cleaned_query = remove_utm_tracking_query(parts.query)

    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            cleaned_query,
            parts.fragment,
        )
    )



def extract_candidate_hostname(raw_url: str) -> str | None:
    """URL에서 검토 대상 호스트를 추출한다. 도메인 승인은 수행하지 않는다."""
    if not isinstance(raw_url, str):
        raise TypeError("raw_url must be str")

    if len(raw_url) > 4_096:
        return None

    # urlsplit이 입력 일부를 조용히 제거하기 전에 검사한다.
    if any(
        char.isspace()
        or category(char) == "Cc"
        or char == "\\"
        for char in raw_url
    ):
        return None

    try:
        parts = urlsplit(raw_url)
        parsed_hostname = parts.hostname
        port = parts.port
    except ValueError:
        return None

    # 절대 HTTP(S) URL만 허용한다.
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None

    # 사용자 정보, 인코딩된 호스트, 빈 포트를 거부한다.
    if (
        not parsed_hostname
        or "@" in parts.netloc
        or "%" in parts.netloc
        or parts.netloc.endswith(":")
    ):
        return None

    # 대괄호 기반 IP 주소 표기를 거부한다.
    if parts.netloc.startswith("["):
        return None

    # 파서의 Unicode 소문자 변환 결과를 그대로 사용하지 않는다.
    # 원래 호스트에서 ASCII A~Z만 소문자로 변환한다.
    hostname = parts.netloc.split(":", 1)[0].translate(
        _ASCII_LOWER_TABLE
    )

    # localhost 및 끝 점이 붙은 모호한 호스트를 거부한다.
    if hostname.endswith(".") or hostname == "localhost":
        return None

    if hostname.endswith(".localhost"):
        return None

    # 일반적인 IPv4·IPv6 주소를 거부한다.
    try:
        ip_address(hostname)
    except ValueError:
        pass
    else:
        return None

    labels = hostname.split(".")

    if len(labels) < 2:
        return None

    # ASCII 도메인에 대해서만 호스트 레이블 형식을 검증한다.
    if hostname.isascii():
        if not all(
            _HOSTNAME_LABEL.fullmatch(label)
            for label in labels
        ):
            return None

        # 숫자로 끝나는 모호한 호스트를 거부한다.
        if labels[-1].isdigit():
            return None

        # 16진수·숫자 레이블만으로 구성된 IP 우회 표현을 거부한다.
        if all(
            _LEGACY_IP_LABEL.fullmatch(label)
            for label in labels
        ):
            return None

    # HTTP 80 / HTTPS 443 이외의 포트는 허용하지 않는다.
    default_port = 80 if parts.scheme == "http" else 443

    if port is not None and port != default_port:
        return None

    return hostname

@dataclass(frozen=True, slots=True)
class NormalizedUrl:
    hostname: str
    canonical_url: str
    source_key: str


def normalize_source_url(raw_url: str) -> NormalizedUrl | None:
    """URL 형식 검증 후 canonical URL과 source_key를 생성한다."""
    hostname = extract_candidate_hostname(raw_url)

    if hostname is None:
        return None

    parts = urlsplit(raw_url)
    cleaned_query = remove_utm_tracking_query(parts.query)

    canonical_url = urlunsplit(
        (
            parts.scheme,
            hostname,
            parts.path,
            cleaned_query,
            parts.fragment,
        )
    )

    source_key = sha256(
        canonical_url.encode("utf-8")
    ).hexdigest()

    return NormalizedUrl(
        hostname=hostname,
        canonical_url=canonical_url,
        source_key=source_key,
    )
