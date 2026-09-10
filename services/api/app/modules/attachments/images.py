import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.errors import UnsupportedMediaTypeError, ValidationError

ALLOWED_IMAGE_MIME_TYPES = frozenset({"image/jpeg", "image/png", "image/webp"})
_FORMAT_TO_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


@dataclass(frozen=True, slots=True)
class SanitizedImage:
    data: bytes
    mime_type: str


def _magic_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


def sanitize_image(data: bytes, *, max_pixels: int) -> SanitizedImage:
    """Decode and reconstruct an image from pixels, discarding all source metadata."""

    magic_format = _magic_type(data)
    if magic_format is None:
        raise UnsupportedMediaTypeError("Only JPEG, PNG, and WEBP images are supported.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as source:
                source_format = source.format
                if source_format != magic_format or source_format not in _FORMAT_TO_MIME:
                    raise UnsupportedMediaTypeError(
                        "Only valid JPEG, PNG, and WEBP images are supported."
                    )
                if getattr(source, "n_frames", 1) != 1:
                    raise ValidationError("Animated images are not supported.")
                width, height = source.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ValidationError("Image dimensions are too large.")
                source.load()
                oriented = ImageOps.exif_transpose(source)
                has_supported_alpha = source_format in {"PNG", "WEBP"} and "A" in oriented.mode
                target_mode = "RGBA" if has_supported_alpha else "RGB"
                converted = oriented.convert(target_mode)
                clean = Image.frombytes(target_mode, converted.size, converted.tobytes())
                output = BytesIO()
                if source_format == "JPEG":
                    clean.save(output, format="JPEG", quality=90, optimize=True)
                elif source_format == "PNG":
                    clean.save(output, format="PNG", optimize=True)
                else:
                    clean.save(output, format="WEBP", quality=90, method=6)
                clean.close()
                converted.close()
                if oriented is not source:
                    oriented.close()
    except UnsupportedMediaTypeError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("Image dimensions are too large.") from exc
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ValidationError("The image is corrupt or invalid.") from exc
    return SanitizedImage(data=output.getvalue(), mime_type=_FORMAT_TO_MIME[magic_format])
