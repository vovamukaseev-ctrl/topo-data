#!/bin/zsh
# Build a contour PMTiles pack from data/contours.gpkg with Planetiler's custom YAML schema.
# usage: scripts/contours_pack.sh <region-id>   (belarus | brest-oblast | …) → out/contours-<region>.pmtiles
set -e
cd "$(dirname $0)/.."
JAVA=${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}
id=$1
bbox=$(.venv/bin/python -c "import json,sys;print(','.join(map(str,json.load(open('data/regions/regions.json'))[sys.argv[1]]['bbox'])))" $id)
args=(generate-custom --schema=scripts/contours.yml --bounds=$bbox --output=out/contours-$id.pmtiles --force --tmpdir=data/tmp/contours-$id)
[[ $id != belarus ]] && args+=(--polygon=data/regions/$id.poly)
$JAVA -Xmx${PLANETILER_XMX:-12g} -jar tools/planetiler.jar "${args[@]}"
rm -rf data/tmp/contours-$id
