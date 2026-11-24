"""Contour lines from the smoothed DEM mosaic → data/contours.gpkg (layer `contour`, fields ele, index).

Interval 5 m, index (основные) every 25 m. Computed per 1°x1° chunk with a shared edge row/column so
lines of neighbouring chunks meet exactly. Clipped to Belarus + ~3 km. Small closed rings (< MIN_RING m)
— DSM bumps of single buildings / tree groups — are dropped.
Usage: python scripts/contours.py [interval] [index_every]
"""
import json, math, os, sys
from multiprocessing import Pool
import numpy as np
import contourpy
import fiona
import shapely
from shapely.geometry import LineString, MultiLineString, box, shape
from shapely.prepared import prep

INTERVAL = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
INDEX = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
MIN_RING = 300.0  # m
SIMPLIFY = 0.00003  # degrees (~2-3 m)
META = json.load(open("data/dem_mosaic.json"))
COUNTRY = shape(json.load(open("data/regions/belarus.geojson"))["geometry"]).buffer(0.03)
CPREP = prep(COUNTRY)


def length_m(coords, lat):
    d = np.diff(coords, axis=0)
    kx = 111320 * math.cos(math.radians(lat))
    return float(np.hypot(d[:, 0] * kx, d[:, 1] * 110540).sum())


def chunk(args):
    lon0, lat0 = args  # south-west corner of the 1° chunk
    cb = box(lon0, lat0, lon0 + 1, lat0 + 1)
    if not CPREP.intersects(cb):
        return []
    inside = CPREP.contains(cb)
    clip = None if inside else COUNTRY.intersection(cb)
    g = np.load("data/dem_mosaic.npy", mmap_mode="r")
    dx, dy = META["dx"], META["dy"]
    c0 = round((lon0 - META["west"]) / dx)
    r0 = round((META["north"] - (lat0 + 1)) / dy)
    nx, ny = round(1 / dx) + 1, round(1 / dy) + 1
    z = np.array(g[r0:r0 + ny, c0:c0 + nx], dtype=np.float64)
    x = META["west"] + (c0 + np.arange(z.shape[1])) * dx
    y = META["north"] - (r0 + np.arange(z.shape[0])) * dy
    gen = contourpy.contour_generator(x, y, z, line_type=contourpy.LineType.Separate)
    out = []
    lo = math.ceil(z.min() / INTERVAL) * INTERVAL
    for lev in np.arange(lo, z.max() + 1e-9, INTERVAL):
        ele = int(round(lev))
        idx = 1 if ele % INDEX == 0 else 0
        for line in gen.lines(lev):
            if len(line) < 2:
                continue
            if len(line) > 2 and np.allclose(line[0], line[-1]) and length_m(line, lat0 + .5) < MIN_RING:
                continue
            geom = LineString(line).simplify(SIMPLIFY)
            if clip is not None:
                if not CPREP.intersects(geom):
                    continue
                geom = geom.intersection(clip)
            if geom.is_empty:
                continue
            geom = shapely.set_precision(geom, 1e-6)
            parts = [p for p in getattr(geom, "geoms", [geom]) if p.geom_type == "LineString" and not p.is_empty]
            if parts:
                out.append((shapely.to_wkb(MultiLineString(parts)), ele, idx))
    return out


def main():
    jobs = [(lon, lat) for lat in range(51, 57) for lon in range(23, 33)]
    os.makedirs("data", exist_ok=True)
    path = "data/contours.gpkg"
    if os.path.exists(path):
        os.remove(path)
    schema = {"geometry": "MultiLineString", "properties": {"ele": "int", "index": "int"}}
    n = 0
    with fiona.open(path, "w", driver="GPKG", layer="contour", crs="EPSG:4326", schema=schema) as dst, \
            Pool(max(1, os.cpu_count() - 2)) as pool:
        for res in pool.imap_unordered(chunk, jobs):
            dst.writerecords({"geometry": shapely.geometry.mapping(shapely.from_wkb(w)),
                              "properties": {"ele": e, "index": i}} for w, e, i in res)
            n += len(res)
            print("features:", n, flush=True)
    print("done", n)


if __name__ == "__main__":
    main()
