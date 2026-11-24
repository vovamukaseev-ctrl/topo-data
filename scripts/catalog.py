"""Write out/catalog.json (format: ../topo-android DESIGN.md §3.3, parser core/PackCatalog.kt).

Env: TAG (release tag, e.g. v2026-11-23), BASE_URL (default https://github.com/foxyclaw/topo-data/releases/download/$TAG/),
VERSION (default today). Sizes and sha256 are measured from the files in out/; avg_tile_bytes of the extract
sources are measured from the PMTiles directories (all addressed tiles, duplicates included).
"""
import datetime, hashlib, json, os, sys
from pmtiles.reader import MmapSource
from pmtiles.tile import deserialize_header, deserialize_directory, tileid_to_zxy

OUT = "out"
VERSION = os.environ.get("VERSION") or datetime.date.today().isoformat()
TAG = os.environ.get("TAG") or "v" + VERSION
BASE_URL = os.environ.get("BASE_URL") or f"https://github.com/foxyclaw/topo-data/releases/download/{TAG}/"
OSM = "© OpenMapTiles © участники OpenStreetMap (ODbL)"
DEM = ("Copernicus DEM © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 "
       "provided under COPERNICUS by the European Union and ESA")
REGIONS = json.load(open("data/regions/regions.json"))
OBLASTS = ["brest-oblast", "vitebsk-oblast", "gomel-oblast", "grodno-oblast", "minsk-oblast", "mogilev-oblast"]
SHORT = {"brest-oblast": "Брестская", "vitebsk-oblast": "Витебская", "gomel-oblast": "Гомельская",
         "grodno-oblast": "Гродненская", "minsk-oblast": "Минская и Минск", "mogilev-oblast": "Могилёвская"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def header(path):
    with open(path, "rb") as f:
        return deserialize_header(f.read(127))


def avg_tile_bytes(path):
    """Average bytes per addressed tile, per zoom."""
    tot, cnt = {}, {}
    with open(path, "rb") as f:
        get = MmapSource(f)
        h = deserialize_header(get(0, 127))

        def walk(off, ln):
            for e in deserialize_directory(get(off, ln)):
                if e.run_length == 0:
                    walk(h["leaf_directory_offset"] + e.offset, e.length)
                else:
                    z = tileid_to_zxy(e.tile_id)[0]
                    # a run covers consecutive tile ids, which stay within one zoom level
                    tot[z] = tot.get(z, 0) + e.length * e.run_length
                    cnt[z] = cnt.get(z, 0) + e.run_length
        walk(h["root_offset"], h["root_length"])
    return {str(z): round(tot[z] / cnt[z]) for z in sorted(tot)}


def pack(file, id, name, kind, group, region, attribution, description):
    path = f"{OUT}/{file}"
    h = header(path)
    print(f"  {file}: {os.path.getsize(path) / 1e6:.1f} MB", file=sys.stderr)
    return {
        "id": id, "name": name, "kind": kind, "format": "pmtiles",
        "bbox": REGIONS[region]["bbox"],
        "minzoom": h["min_zoom"], "maxzoom": h["max_zoom"],
        "size": os.path.getsize(path), "url": BASE_URL + file, "sha256": sha256(path),
        "version": VERSION, "group": group, "attribution": attribution, "description": description,
    }


def main():
    packs = []
    for r in OBLASTS:
        packs.append(pack(f"{r}.pmtiles", r, REGIONS[r]["name"], "base", "Области", r, OSM,
                          "дороги, леса, болота, вода, здания, нас. пункты, подписи по-русски"))
    if os.path.exists(f"{OUT}/belarus.pmtiles"):
        packs.append(pack("belarus.pmtiles", "belarus", "Беларусь целиком", "base", "Вся страна", "belarus", OSM,
                          "основная карта всей страны одним файлом (z0–14)"))
    for r in OBLASTS:
        f = f"contours-{r}.pmtiles"
        if os.path.exists(f"{OUT}/{f}"):
            packs.append(pack(f, f"contours-{r}", f"Горизонтали: {SHORT[r]}", "contours", "Рельеф", r, DEM,
                              "горизонтали через 5 м, основные через 25 м (Copernicus DEM GLO-30)"))
    if os.path.exists(f"{OUT}/hillshade-belarus.pmtiles"):
        packs.append(pack("hillshade-belarus.pmtiles", "hillshade-belarus", "Отмывка рельефа: Беларусь", "hillshade",
                          "Рельеф", "belarus", DEM, "теневая отмывка рельефа, WebP с прозрачностью"))
    extract = [{
        "id": "belarus", "name": "Беларусь (векторная)", "kind": "base", "url": BASE_URL + "belarus.pmtiles",
        "maxzoom": header(f"{OUT}/belarus.pmtiles")["max_zoom"],
        "avg_tile_bytes": avg_tile_bytes(f"{OUT}/belarus.pmtiles"), "attribution": OSM,
    }]
    if os.path.exists(f"{OUT}/contours-belarus.pmtiles"):
        extract.append({
            "id": "contours-belarus", "name": "Беларусь (горизонтали)", "kind": "contours",
            "url": BASE_URL + "contours-belarus.pmtiles",
            "maxzoom": header(f"{OUT}/contours-belarus.pmtiles")["max_zoom"],
            "avg_tile_bytes": avg_tile_bytes(f"{OUT}/contours-belarus.pmtiles"), "attribution": DEM,
        })
    cat = {"version": 1, "title": "Карты Беларуси", "updated": VERSION, "packs": packs, "extract": extract}
    with open(f"{OUT}/catalog.json", "w") as f:
        json.dump(cat, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"catalog: {len(packs)} packs, {len(extract)} extract sources, base {BASE_URL}", file=sys.stderr)


if __name__ == "__main__":
    main()
