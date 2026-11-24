"""Extract real oblast boundaries (admin_level=4) of Belarus from the Geofabrik OSM extract.

Writes data/regions/<id>.poly (Osmosis format, for planetiler --polygon), data/regions/<id>.geojson,
the country outline data/regions/belarus.{poly,geojson} and data/regions/regions.json (bbox per region).
Minsk city (also admin_level=4) is merged into Минская область.
Usage: python scripts/oblasts.py data/belarus-latest.osm.pbf data/regions
"""
import json, sys, os
import osmium
import shapely.wkb
from shapely.geometry import mapping
from shapely.ops import unary_union

# id, Russian name, OSM names (ru) that belong to it
REGIONS = [
    ("brest-oblast", "Брестская область", ["Брестская область"]),
    ("vitebsk-oblast", "Витебская область", ["Витебская область"]),
    ("gomel-oblast", "Гомельская область", ["Гомельская область"]),
    ("grodno-oblast", "Гродненская область", ["Гродненская область"]),
    ("minsk-oblast", "Минская область и Минск", ["Минская область", "Минск"]),
    ("mogilev-oblast", "Могилёвская область", ["Могилёвская область", "Могилевская область"]),
]


class H(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.fab = osmium.geom.WKBFactory()
        self.found = {}

    def area(self, a):
        t = a.tags
        if t.get("boundary") != "administrative" or a.from_way():
            return
        lvl = t.get("admin_level")
        if lvl not in ("2", "4"):
            return
        if lvl == "2" and t.get("ISO3166-1") != "BY":
            return
        name = t.get("name:ru") or t.get("name")
        try:
            g = shapely.wkb.loads(self.fab.create_multipolygon(a), hex=True)
        except Exception as e:  # broken relation
            print("skip", name, e, file=sys.stderr)
            return
        key = "BY" if lvl == "2" else name
        print("found", lvl, name, round(g.area, 3), file=sys.stderr)
        self.found[key] = g


def write_poly(path, name, geom):
    geoms = getattr(geom, "geoms", [geom])
    with open(path, "w") as f:
        f.write(name + "\n")
        n = 1
        for p in geoms:
            for i, ring in enumerate([p.exterior, *p.interiors]):
                f.write(("!" if i else "") + str(n) + "\n")
                n += 1
                for x, y in ring.coords:
                    f.write(f"   {x:.7f}   {y:.7f}\n")
                f.write("END\n")
        f.write("END\n")


def main(pbf, out):
    os.makedirs(out, exist_ok=True)
    h = H()
    h.apply_file(pbf, locations=True, idx="flex_mem")
    regions = {}

    def save(rid, name, g):
        g = g.buffer(0)
        # small outward buffer (~1 km) so border tiles are surely included; simplified for a compact .poly
        poly = g.buffer(0.01).simplify(0.002)
        write_poly(f"{out}/{rid}.poly", rid, poly)
        with open(f"{out}/{rid}.geojson", "w") as f:
            json.dump({"type": "Feature", "properties": {"id": rid, "name": name},
                       "geometry": mapping(g.simplify(0.0005))}, f)
        w, s, e, n = g.bounds
        regions[rid] = {"name": name, "bbox": [round(w, 4), round(s, 4), round(e, 4), round(n, 4)]}

    for rid, name, osm_names in REGIONS:
        parts = [h.found[n] for n in osm_names if n in h.found]
        if not parts:
            sys.exit(f"region not found in OSM: {name}")
        save(rid, name, unary_union(parts))
    if "BY" not in h.found:
        sys.exit("country boundary not found")
    save("belarus", "Беларусь", h.found["BY"])
    with open(f"{out}/regions.json", "w") as f:
        json.dump(regions, f, ensure_ascii=False, indent=1)
    print(json.dumps(regions, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
