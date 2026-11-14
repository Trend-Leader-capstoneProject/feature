"""서버 신뢰 경계의 이미지 검증·가공·파일 저장."""

import io
import os
import re
import threading
import warnings
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.exceptions import ApplicationException

MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGE_PIXELS = 20_000_000
MAX_MULTIPART_BYTES = 6_000_000
_PROCESSING = threading.BoundedSemaphore(1)
_FILE_KEY = re.compile(r"[0-9a-f]{32}\.(?:jpg|png)\Z")


def image_error(status: int, reason: str) -> ApplicationException:
    error = ApplicationException(data={"reason": reason})
    error.status_code = status
    return error


def process_image(raw: bytes) -> tuple[bytes, str]:
    if len(raw) > MAX_IMAGE_BYTES:
        raise image_error(413, "PROFILE_IMAGE_TOO_LARGE")
    if not _PROCESSING.acquire(timeout=5):
        raise image_error(503, "PROFILE_IMAGE_PROCESSING_BUSY")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            try:
                with Image.open(io.BytesIO(raw)) as source:
                    if (
                        source.format not in {"JPEG", "PNG"}
                        or getattr(source, "n_frames", 1) != 1
                    ):
                        raise image_error(415, "PROFILE_IMAGE_UNSUPPORTED")
                    if source.width * source.height > MAX_IMAGE_PIXELS:
                        raise image_error(413, "PROFILE_IMAGE_PIXEL_LIMIT_EXCEEDED")
                    source.load()
                    image = ImageOps.exif_transpose(source)
                    image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
                    is_png = source.format == "PNG"
                    mode = (
                        "RGBA"
                        if is_png
                        and ("A" in image.getbands() or "transparency" in image.info)
                        else "RGB"
                    )
                    # 새 픽셀 버퍼에 복사해 입력 메타데이터를 계승하지 않는다.
                    converted = image.convert(mode)
                    clean = Image.new(mode, converted.size)
                    clean.paste(converted)
                    output = io.BytesIO()
                    clean.save(
                        output,
                        format="PNG" if is_png else "JPEG",
                        **({} if is_png else {"quality": 90}),
                    )
                    return output.getvalue(), "png" if is_png else "jpg"
            except (
                Image.DecompressionBombWarning,
                Image.DecompressionBombError,
            ) as exc:
                raise image_error(413, "PROFILE_IMAGE_PIXEL_LIMIT_EXCEEDED") from exc
            except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
                raise image_error(400, "PROFILE_IMAGE_INVALID") from exc
    finally:
        _PROCESSING.release()


class ImageStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("Profile image root must be absolute")
        self.root = root.resolve()

    @staticmethod
    def new_key(extension: str) -> str:
        if extension not in {"jpg", "png"}:
            raise ValueError("Invalid encoding")
        return f"{uuid4().hex}.{extension}"

    def path(self, key: str) -> Path:
        if not _FILE_KEY.fullmatch(key):
            raise ValueError("Invalid file key")
        target = (self.root / key).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("Image path outside storage root")
        return target

    def write(self, key: str, data: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.path(key).open("xb") as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        if hasattr(os, "O_DIRECTORY"):
            fd = os.open(self.root, os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def delete(self, key: str) -> None:
        self.path(key).unlink(missing_ok=True)

    def read(self, key: str) -> bytes:
        target = self.path(key)
        if target.stat().st_size > MAX_IMAGE_BYTES:
            raise OSError("Stored image exceeds limit")
        return target.read_bytes()
