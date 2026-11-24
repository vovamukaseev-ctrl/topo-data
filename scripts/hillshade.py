"""Hillshade raster PMTiles (WebP, 256 px) from the DEM mosaic.

The shade is «shadow only»: black with alpha — flat ground and lit slopes are transparent, shaded slopes
darker, so the app can lay it over the map (raster-opacity) without washing the colours out. Max-zoom tiles are sampled (bilinear) from a geographic hillshade grid;
lower zooms are 2x2 averages of their children (no aliasing). Only tiles touching Belarus (+3 km) are written.
Usage: python scripts/hillshade.py out/hillshade-belarus.pmtiles [minzoom] [maxzoom] [webp_quality]
"""
import io, json, math, os, sys
from multiprocessing import Pool
import numpy as np
from PIL import Image
from scipy.ndimage import map_coordinates
from shapely.geometry import box, shape
from shapely.prepared import prep
from pmtiles.tile import zxy_to_tileid, TileType, Compression
from pmtiles.writer import Writer

OUT = sys.argv[1]
MINZ = int(sys.argv[2]) if len(sys.argv) > 2 else 8
MAXZ = int(sys.argv[3]) if len(sys.argv) > 3 else 13
QUALITY = int(sys.argv[4]) if len(sys.argv) > 4 else 70
Z_FACTOR, AZIMUTH, ALTITUDE = 3.0, 315.0, 45.0
META = json.load(open("data/dem_mosaic.json"))
SHADE = "data/hillshade.npy"
TS = 256


def make_shade():
    dem = np.load("data/dem_mosaic.npy", mmap_mode="r")
    out = np.lib.format.open_memmap(SHADE, mode="w+", dtype=np.uint8, shape=dem.shape)
    az, alt = math.radians(360 - AZIMUTH + 90), math.radians(ALTITUDE)
    flat = math.sin(alt)
    step = 1200
    for r0 in range(0, dem.shape[0], step):
        a0, a1 = max(0, r0 - 1), min(dem.shape[0], r0 + step + 1)
        z = np.asarray(dem[a0:a1], dtype=np.float64) * Z_FACTOR
        lat = META["north"] - (np.arange(a0, a1) * META["dy"])
        dxm = (META["dx"] * 111320 * np.cos(np.radians(lat)))[:, None]
        dym = META["dy"] * 110540
        gy, gx = np.gradient(z)
        gx, gy = gx / dxm, -gy / dym  # gy: northward gradient (rows go south)
        slope = np.arctan(np.hypot(gx, gy))
        aspect = np.arctan2(gy, -gx)
        s = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
        v = np.clip(s / flat, 0, 1) * 255
        out[r0:min(r0 + step, dem.shape[0])] = v[r0 - a0:r0 - a0 + min(step, dem.shape[0] - r0)].astype(np.uint8)
    out.flush()


def tile_bounds(z, x, y):
    n = 2 ** z
    lon = lambda xx: xx / n * 360 - 180
    lat = lambda yy: math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))
    return lon(x), lat(y + 1), lon(x + 1), lat(y)


def lonlat_tile(lon, lat, z):
    n = 2 ** z
    return int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def render(zxy):
    z, x, y = zxy
    sh = np.load(SHADE, mmap_mode="r")
    n = 2 ** z
    px = (x + (np.arange(TS) + 0.5) / TS) / n * 360 - 180
    py = y + (np.arange(TS) + 0.5) / TS
    lat = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * py / n))))
    cols = (px - META["west"]) / META["dx"]
    rows = (META["north"] - lat) / META["dy"]
    r0, r1 = int(rows.min()) - 2, int(rows.max()) + 3
    c0, c1 = int(cols.min()) - 2, int(cols.max()) + 3
    sub = np.asarray(sh[max(r0, 0):r1, max(c0, 0):c1], dtype=np.float32)
    rr, cc = np.meshgrid(rows - max(r0, 0), cols - max(c0, 0), indexing="ij")
    return zxy, map_coordinates(sub, [rr, cc], order=1, mode="nearest").astype(np.uint8)


def encode(a):
    if a.min() >= 250:
        return None  # all-white tile: nothing to draw
    # black with alpha = darkness: flat ground is fully transparent, so the map is never washed out
    rgba = np.zeros(a.shape + (4,), np.uint8)
    rgba[..., 3] = 255 - a
    b = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(b, "WEBP", quality=QUALITY, alpha_quality=QUALITY, method=6)
    return b.getvalue()


def main():
    if not os.path.exists(SHADE) or os.path.getmtime(SHADE) < os.path.getmtime("data/dem_mosaic.npy"):
        make_shade()
    country = shape(json.load(open("data/regions/belarus.geojson"))["geometry"]).buffer(0.03)
    cp = prep(country)
    w, s, e, n = country.bounds
    x0, y0 = lonlat_tile(w, n, MAXZ)
    x1, y1 = lonlat_tile(e, s, MAXZ)
    todo = [(MAXZ, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1) if cp.intersects(box(*tile_bounds(MAXZ, x, y)))]
    print("max-zoom tiles:", len(todo), flush=True)
    tiles = {}
    with Pool(max(1, os.cpu_count() - 2)) as pool:
        for zxy, a in pool.imap_unordered(render, todo, chunksize=64):
            tiles[zxy] = a
    levels = {MAXZ: tiles}
    for z in range(MAXZ - 1, MINZ - 1, -1):
        child, cur = levels[z + 1], {}
        for (_, cx, cy) in child:
            cur.setdefault((z, cx // 2, cy // 2), None)
        for key in cur:
            _, x, y = key
            big = np.full((2 * TS, 2 * TS), 255, np.float32)
            for dx in (0, 1):
                for dy in (0, 1):
                    c = child.get((z + 1, 2 * x + dx, 2 * y + dy))
                    if c is not None:
                        big[dy * TS:(dy + 1) * TS, dx * TS:(dx + 1) * TS] = c
            cur[key] = big.reshape(TS, 2, TS, 2).mean(axis=(1, 3)).astype(np.uint8)
        levels[z] = cur
        print("z", z, len(cur), flush=True)
    allt = [(zxy_to_tileid(*k), a) for lvl in levels.values() for k, a in lvl.items()]
    allt.sort(key=lambda t: t[0])
    sizes = {}
    with Pool(max(1, os.cpu_count() - 2)) as pool:
        encoded = pool.map(encode, [a for _, a in allt], chunksize=64)
    with open(OUT, "wb") as f:
        wr = Writer(f)
        for (tid, _), data in zip(allt, encoded):
            if data is None:
                continue
            wr.write_tile(tid, data)
        wr.finalize(
            {"tile_type": TileType.WEBP, "tile_compression": Compression.NONE,
             "min_zoom": MINZ, "max_zoom": MAXZ,
             "min_lon_e7": int(w * 1e7), "min_lat_e7": int(s * 1e7), "max_lon_e7": int(e * 1e7), "max_lat_e7": int(n * 1e7),
             "center_zoom": 8, "center_lon_e7": int((w + e) / 2 * 1e7), "center_lat_e7": int((s + n) / 2 * 1e7)},
            {"name": "Отмывка рельефа Беларуси", "format": "webp", "type": "overlay", "tileSize": 256,
             "minzoom": MINZ, "maxzoom": MAXZ,
             "attribution": "Copernicus DEM © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA"},
        )
    print("written", OUT, os.path.getsize(OUT))


if __name__ == "__main__":
    main()
