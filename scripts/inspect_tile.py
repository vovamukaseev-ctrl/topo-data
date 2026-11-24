"""Print layers/feature counts of a tile: python scripts/inspect_tile.py file.pmtiles z lon lat"""
import gzip, math, sys, collections
from pmtiles.reader import Reader, MmapSource
import mapbox_vector_tile
f, z, lon, lat = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
n = 2 ** z
x = int((lon + 180) / 360 * n)
y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
with open(f, "rb") as fh:
    r = Reader(MmapSource(fh))
    print(r.header())
    print(r.metadata().get("vector_layers") and [l["id"] for l in r.metadata()["vector_layers"]])
    data = r.get(z, x, y)
    if data is None:
        sys.exit("no tile")
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    t = mapbox_vector_tile.decode(data)
    for name, layer in t.items():
        c = collections.Counter(tuple(sorted((k, v) for k, v in ft["properties"].items() if k in ("index", "class"))) for ft in layer["features"])
        print(name, len(layer["features"]), dict(list(c.items())[:8]))
        if name == "contour":
            print(sorted({ft["properties"]["ele"] for ft in layer["features"]})[:30])
