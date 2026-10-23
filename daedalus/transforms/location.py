"""Location transforms: geocoding with OpenStreetMap Nominatim."""

from __future__ import annotations

import asyncio
import time

from .. import __version__
from ..entities import L, latlon
from .base import Skip, Transform, register

NOMINATIM = "https://nominatim.openstreetmap.org"
_lock = asyncio.Lock()
_last = 0.0


async def nominatim(ctx, path: str, params: dict):
    """Nominatim's usage policy allows one request per second with an identifying User-Agent."""
    global _last
    async with _lock:
        wait = 1.1 - (time.monotonic() - _last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last = time.monotonic()
        return await ctx.get_json(f"{NOMINATIM}/{path}", params={**params, "format": "jsonv2"},
                                  headers={"User-Agent": f"DAEDALUS-OSINT/{__version__} (link analysis tool)"})


def map_links(lat: float, lon: float) -> list[list[str]]:
    return [["OpenStreetMap", f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"],
            ["Google Maps", f"https://www.google.com/maps?q={lat},{lon}"]]


@register
class Geocode(Transform):
    name = "geocode"
    title = L("To coordinates / address [OSM]", "A coordenadas / dirección [OSM]")
    description = L("Places a location on the map (or names the place for raw coordinates).",
                    "Sitúa la ubicación en el mapa (o pone nombre a unas coordenadas).")
    category = "location"
    inputs = ("location",)
    sources = ("OpenStreetMap Nominatim",)

    async def run(self, ctx):
        coords = latlon(ctx.value)
        if coords is None and ctx.props.get("_lat") is not None and ctx.props.get("_lon") is not None:
            # already placed (e.g. by GeoIP): just name it
            coords = (float(ctx.props["_lat"]), float(ctx.props["_lon"]))
            if not ctx.props.get("address"):
                return await self._reverse(ctx, coords)
            return
        if coords:
            return await self._reverse(ctx, coords)
        st, d = await nominatim(ctx, "search", {"q": ctx.value, "limit": 1, "addressdetails": 1})
        if st != 200 or not isinstance(d, list):
            raise Skip(f"Nominatim HTTP {st}")
        if not d:
            ctx.log("Place not found")
            return
        hit = d[0]
        lat, lon = float(hit["lat"]), float(hit["lon"])
        addr = hit.get("address") or {}
        ctx.enrich({"_lat": lat, "_lon": lon, "address": hit.get("display_name"), "country": addr.get("country"),
                    "country_code": (addr.get("country_code") or "").upper() or None, "place_type": hit.get("type"),
                    "_links": map_links(lat, lon)})

    async def _reverse(self, ctx, coords):
        lat, lon = coords
        st, d = await nominatim(ctx, "reverse", {"lat": lat, "lon": lon, "zoom": 16, "addressdetails": 1})
        if st != 200 or not isinstance(d, dict) or d.get("error"):
            ctx.enrich({"_lat": lat, "_lon": lon, "_links": map_links(lat, lon)})
            return
        addr = d.get("address") or {}
        ctx.enrich({"_lat": lat, "_lon": lon, "address": d.get("display_name"), "country": addr.get("country"),
                    "country_code": (addr.get("country_code") or "").upper() or None, "_links": map_links(lat, lon)})
