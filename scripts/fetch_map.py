"""One-time: the base map for the David lens, from Natural Earth (public domain).

Downloads land, lakes and rivers (1:10m), clips them to the region of the
events, simplifies them and writes data/map_shapes.json (lon/lat rings).
The site then draws the map as inline SVG at build time: no map server,
no request to any third party when a page is viewed.

Requires shapely (only for this script): pip install shapely
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import box, mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sefaria  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
BBOX = (34.25, 30.85, 35.75, 32.05)  # lon/lat: from the coastal plain to the Jordan, the Dead Sea to Samaria
RIVER_NAMES = {"Jordan"}


def layer(name: str) -> list[dict]:
    return json.loads(sefaria.get_text(BASE + name + ".geojson"))["features"]


def rings(geom) -> list[list[list[float]]]:
    g = mapping(geom)
    out = []
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
    for poly in polys:
        for ring in poly[:1]:  # outer ring is enough at this scale
            out.append([[round(x, 4), round(y, 4)] for x, y in ring])
    lines = [g["coordinates"]] if g["type"] == "LineString" else g["coordinates"] if g["type"] == "MultiLineString" else []
    for line in lines:
        out.append([[round(x, 4), round(y, 4)] for x, y in line])
    return out


def main() -> int:
    clip = box(*BBOX)
    out = {"bbox": BBOX, "source": "Natural Earth 1:10m (public domain)", "land": [], "lakes": [], "rivers": []}
    for key, name, keep in (("land", "ne_10m_land", None), ("lakes", "ne_10m_lakes", None),
                            ("rivers", "ne_10m_rivers_lake_centerlines", RIVER_NAMES)):
        for f in layer(name):
            if keep and (f["properties"].get("name") or f["properties"].get("name_en")) not in keep:
                continue
            g = shape(f["geometry"])
            if not g.intersects(clip):
                continue
            g = g.intersection(clip).simplify(0.003, preserve_topology=True)
            if not g.is_empty:
                out[key] += rings(g)
    path = ROOT / "data" / "map_shapes.json"
    path.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print({k: len(v) for k, v in out.items() if isinstance(v, list)}, path.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
