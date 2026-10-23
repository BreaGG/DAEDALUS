"""Image metadata extraction (EXIF, GPS) for uploaded photos."""

from __future__ import annotations

import hashlib
import io

from PIL import Image

BASE_TAGS = {0x010F: "camera_make", 0x0110: "camera_model", 0x0131: "software", 0x0132: "modified",
             0x013B: "artist", 0x8298: "copyright", 0x010E: "description"}
EXIF_TAGS = {0x9003: "taken", 0x9004: "digitized", 0xA434: "lens", 0xA431: "camera_serial",
             0xA430: "camera_owner", 0x9010: "timezone_offset"}
XP_AUTHOR = 0x9C9D


def _rational(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError, ZeroDivisionError):
        num, den = x
        return num / den if den else 0.0


def _dms(values, ref: str) -> float | None:
    try:
        d, m, s = (_rational(v) for v in values)
    except (TypeError, ValueError):
        return None
    out = d + m / 60 + s / 3600
    return -out if ref in ("S", "W") else out


def _text(v) -> str | None:
    if isinstance(v, bytes):
        v = v.decode("utf-8", "replace")
    v = str(v or "").replace("\x00", "").strip()
    return v or None


def _exif_date(v: str | None) -> str | None:
    # "2023:06:01 18:22:10" -> "2023-06-01 18:22:10"
    if v and len(v) >= 10 and v[4] == ":" and v[7] == ":":
        return v[:10].replace(":", "-") + v[10:]
    return v


def analyze_image(data: bytes, filename: str) -> dict:
    """Properties for an image entity; GPS coordinates land in _lat/_lon."""
    img = Image.open(io.BytesIO(data))
    props: dict = {
        "filename": filename,
        "format": img.format,
        "dimensions": f"{img.width}x{img.height}",
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "md5": hashlib.md5(data).hexdigest(),  # noqa: S324  identification only
    }
    exif = img.getexif()
    for tag, key in BASE_TAGS.items():
        if exif.get(tag):
            props[key] = _text(exif.get(tag))
    if exif.get(XP_AUTHOR):
        raw = exif.get(XP_AUTHOR)
        try:
            props["windows_author"] = bytes(raw).decode("utf-16-le").rstrip("\x00") or None
        except (TypeError, ValueError):
            pass
    try:
        sub = exif.get_ifd(0x8769)
    except (KeyError, AttributeError):
        sub = {}
    for tag, key in EXIF_TAGS.items():
        if sub.get(tag):
            props[key] = _text(sub.get(tag))
    for key in ("taken", "digitized", "modified"):
        if props.get(key):
            props[key] = _exif_date(props[key])
    try:
        gps = exif.get_ifd(0x8825)
    except (KeyError, AttributeError):
        gps = {}
    if gps.get(2) and gps.get(4):
        lat = _dms(gps[2], _text(gps.get(1)) or "N")
        lon = _dms(gps[4], _text(gps.get(3)) or "E")
        if lat is not None and lon is not None and (lat or lon):
            props["_lat"], props["_lon"] = round(lat, 6), round(lon, 6)
            if gps.get(6) is not None:
                props["gps_altitude_m"] = round(_rational(gps[6]), 1)
    dates = [[label, props[k][:10]] for k, label in (("taken", "Photo taken"), ("modified", "Photo edited"))
             if props.get(k) and props[k][:4].isdigit()]
    if dates:
        props["_dates"] = dates
    return {k: v for k, v in props.items() if v not in (None, "")}
