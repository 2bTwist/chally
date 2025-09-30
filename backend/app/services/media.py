from __future__ import annotations
from typing import Tuple, Any
from PIL import Image, UnidentifiedImageError
import imagehash
import piexif
import io


ALLOWED_MIME = {"image/jpeg", "image/png"}
EXT_FOR_MIME = {"image/jpeg": "jpg", "image/png": "png"}

def sniff_mime(data: bytes) -> str | None:
    # Use PIL to detect image format instead of deprecated imghdr
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format == "JPEG":
                return "image/jpeg"
            elif img.format == "PNG":
                return "image/png"
            return None
    except Exception:
        return None

def analyze_image(data: bytes) -> Tuple[str, str, dict]:
    """
    Returns (mime, phash_hex, exif_dict_or_empty).
    - mime: detected content-type
    - phash_hex: perceptual hash hex string
    - exif: parsed EXIF dict (may be empty for PNGs)
    """
    mime = sniff_mime(data)
    if mime not in ALLOWED_MIME:
        raise ValueError("Unsupported image type")
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()  # basic integrity
        with Image.open(io.BytesIO(data)) as img2:
            ph = imagehash.phash(img2)
        exif = {}
        if mime == "image/jpeg":
            try:
                exif = piexif.load(io.BytesIO(data))
            except Exception:
                exif = {}
        return mime, str(ph), exif
    except UnidentifiedImageError:
        raise ValueError("Invalid image file")

def ext_for_mime(mime: str) -> str:
    return EXT_FOR_MIME.get(mime, "bin")