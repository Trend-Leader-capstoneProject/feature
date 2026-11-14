"""회원가입·프로필·백필에서 공유하는 닉네임 정책."""

import re
import unicodedata

_PATTERN = re.compile(r"[가-힣A-Za-z0-9_]{2,10}\Z")


def normalize_nickname(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("닉네임은 문자열이어야 합니다.")
    nickname = unicodedata.normalize("NFC", value.strip())
    if not _PATTERN.fullmatch(nickname):
        raise ValueError("닉네임은 2~10자 한글·영문·숫자·밑줄만 사용할 수 있습니다.")
    return nickname


def nickname_key(value: str) -> str:
    return normalize_nickname(value).lower()
