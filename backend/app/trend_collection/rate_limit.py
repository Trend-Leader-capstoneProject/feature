"""Bounded GitHub REST rate-limit timing; independent of publication authority."""

import math
import re
from email.utils import parsedate_to_datetime


def retry_deadline(headers, now):
    """Return a UTC epoch second, or None if required timing is untrustworthy."""
    deadline = math.ceil(now) + 60
    retry = headers.get('Retry-After')
    if retry is not None:
        try:
            if re.fullmatch(r'[0-9]{1,12}', retry):
                deadline = max(deadline, math.ceil(now) + int(retry))
            else:
                value = parsedate_to_datetime(retry)
                if value is None or value.utcoffset() is None:
                    return None
                deadline = max(deadline, math.ceil(value.timestamp()) + 1)
        except (TypeError, ValueError, OverflowError, OSError):
            return None
    if headers.get('X-RateLimit-Remaining') == '0':
        reset = headers.get('X-RateLimit-Reset')
        if not isinstance(reset, str) or not re.fullmatch(r'[0-9]{1,12}', reset):
            return None
        deadline = max(deadline, int(reset) + 1)
    return deadline
