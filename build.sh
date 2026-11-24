#!/bin/zsh
# Rebuild all map packs of «Топо» into ./out/ (see README.md).
# No Homebrew, no sudo: Java 21 by full path, jars in ./tools, Python venv in ./.venv.
#   TAG=v2026-11-23 ./build.sh          # release tag used in catalog URLs
#   SKIP_DOWNLOAD=1 ./build.sh          # reuse data/belarus-latest.osm.pbf and data/dem
set -euo pipefail
cd "$(dirname $0)"

# ---- settings ---------------------------------------------------------------------------------
export VERSION=${VERSION:-$(date +%Y-%m-%d)}
export TAG=${TAG:-v$VERSION}                       # GitHub release tag with the .pmtiles assets
export BASE_URL=${BASE_URL:-https://github.com/vovamukaseev-ctrl/topo-data/releases/download/$TAG/}
export JAVA=${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}
PLANETILER_VERSION=0.10.2
PYTHON_BOOT=${PYTHON_BOOT:-/opt/homebrew/bin/python3.12}   # only used to create .venv
CONTOUR_INTERVAL=5; CONTOUR_INDEX=25; DEM_SIGMA=2
HILLSHADE_MINZOOM=8; HILLSHADE_MAXZOOM=12             # 12 ≈ native 30 m DEM resolution; 13 = 2.8x size, no new detail
OBLASTS=(brest-oblast vitebsk-oblast gomel-oblast grodno-oblast minsk-oblast mogilev-oblast)
# -----------------------------------------------------------------------------------------------

mkdir -p tools data out logs
TIMES=out/build-times.txt; : > $TIMES
step() { local name=$1; shift; local t0=$SECONDS; echo "== $name"; "$@"; echo "$name: $((SECONDS - t0)) s" | tee -a $TIMES; }

setup() {
  [[ -x .venv/bin/python ]] || $PYTHON_BOOT -m venv .venv
  .venv/bin/pip -q install -r requirements.txt
  [[ -s tools/planetiler.jar ]] || curl -fL -o tools/planetiler.jar \
    https://github.com/onthegomap/planetiler/releases/download/v$PLANETILER_VERSION/planetiler.jar
  $JAVA -version
}
download() {
  if [[ -z ${SKIP_DOWNLOAD:-} || ! -s data/belarus-latest.osm.pbf ]]; then
    curl -fL -o data/belarus-latest.osm.pbf.part https://download.geofabrik.de/europe/belarus-latest.osm.pbf
    mv data/belarus-latest.osm.pbf.part data/belarus-latest.osm.pbf
  fi
  scripts/fetch_dem.sh
}
base_all() {
  scripts/base.sh belarus > logs/base-belarus.log 2>&1   # first run also downloads Planetiler sources (--download)
  for r in $OBLASTS; do scripts/base.sh $r > logs/base-$r.log 2>&1; done
}
contour_packs() {
  for r in belarus $OBLASTS; do scripts/contours_pack.sh $r > logs/contours-$r.log 2>&1; done
}

T0=$SECONDS
step setup setup
step download download
step regions .venv/bin/python scripts/oblasts.py data/belarus-latest.osm.pbf data/regions
step base-packs base_all
step dem-mosaic .venv/bin/python scripts/dem_mosaic.py $DEM_SIGMA
step contours .venv/bin/python scripts/contours.py $CONTOUR_INTERVAL $CONTOUR_INDEX
step contour-packs contour_packs
step hillshade .venv/bin/python scripts/hillshade.py out/hillshade-belarus.pmtiles $HILLSHADE_MINZOOM $HILLSHADE_MAXZOOM 70
step catalog .venv/bin/python scripts/catalog.py
echo "total: $((SECONDS - T0)) s" | tee -a $TIMES
cp out/catalog.json catalog.json   # committed copy
ls -l out/
