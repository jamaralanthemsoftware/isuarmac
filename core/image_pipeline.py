"""Bounded, storage-backed responsive image renditions.

The pipeline intentionally only accepts raster images Pillow can decode and always
emits WebP.  Renditions are deterministic, so repeated template renders do not
create duplicate files in the media store.
"""

from __future__ import annotations

import hashlib
import io
import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from PIL import Image, UnidentifiedImageError

MAX_SOURCE_PIXELS = 25_000_000
MAX_SOURCE_BYTES = 50_000_000
MAX_WIDTH = 2_000
RENDITION_WIDTHS = (320, 640, 960, 1280, 1600, MAX_WIDTH)


@dataclass(frozen=True)
class ImageRendition:
    url: str
    width: int
    height: int


def _source_name(image) -> str:
    return str(getattr(image, "name", "") or "")


def _source_version(image) -> str:
    image_field = getattr(image, "file", image)
    image_field.seek(0)
    digest = hashlib.sha256()
    total = 0
    while chunk := image_field.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_SOURCE_BYTES:
            raise ValueError("Image exceeds the responsive image byte limit.")
        digest.update(chunk)
    image_field.seek(0)
    return digest.hexdigest()[:24]


def _open_image(image) -> Image.Image:
    image_field = getattr(image, "file", image)
    image_field.seek(0)
    try:
        opened = Image.open(image_field)
        if opened.width * opened.height > MAX_SOURCE_PIXELS:
            raise ValueError("Image exceeds the responsive image pixel limit.")
        opened.load()
        return opened.convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("The uploaded file is not a supported image.") from exc


def _rendition_name(source_name: str, source_version: str, width: int) -> str:
    stem = PurePosixPath(source_name).stem or "image"
    safe_stem = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in stem
    )
    return posixpath.join(
        "responsive",
        f"{safe_stem}-{source_version}-{width}.webp",
    )


def _save_rendition(
    source_name: str,
    source_version: str,
    image: Image.Image,
    width: int,
) -> ImageRendition:
    ratio = width / image.width
    height = max(1, round(image.height * ratio))
    resized = image.resize((width, height), Image.Resampling.LANCZOS) if width < image.width else image
    output = io.BytesIO()
    resized.save(output, format="WEBP", quality=82, method=6)
    name = _rendition_name(source_name, source_version, width)
    saved_name = (
        name
        if default_storage.exists(name)
        else default_storage.save(name, ContentFile(output.getvalue()))
    )
    return ImageRendition(default_storage.url(saved_name), width, height)


def responsive_renditions(image, widths=RENDITION_WIDTHS) -> tuple[ImageRendition, ...]:
    """Return bounded WebP renditions for a Django FileField or uploaded file."""
    source_name = _source_name(image)
    if not source_name:
        return ()
    source_version = _source_version(image)
    source = _open_image(image)
    terminal_width = min(source.width, MAX_WIDTH)
    selected_widths = {
        min(MAX_WIDTH, int(width))
        for width in widths
        if int(width) > 0
    }
    selected_widths.add(terminal_width)
    selected_widths = sorted(
        width for width in selected_widths if width <= terminal_width
    )
    if not selected_widths:
        return ()
    return tuple(
        _save_rendition(source_name, source_version, source, width)
        for width in selected_widths
    )


def image_dimensions(image) -> tuple[int, int]:
    """Read numeric intrinsic dimensions without exposing arbitrary image metadata."""
    source = _open_image(image)
    return source.width, source.height