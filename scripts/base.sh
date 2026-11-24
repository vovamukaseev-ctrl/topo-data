#!/bin/zsh
# Build one OpenMapTiles-schema base pack with Planetiler.
# usage: scripts/base.sh <id> [<bounds-or-empty>]  — polygon/bounds are taken from data/regions/<id>.*
set -e
cd "$(dirname $0)/.."
JAVA=${JAVA:-/opt/homebrew/opt/openjdk@21/bin/java}
id=$1
bbox=$(.venv/bin/python -c "import json,sys;print(','.join(map(str,json.load(open('data/regions/regions.json'))[sys.argv[1]]['bbox'])))" $id)
args=(--osm-path=data/belarus-latest.osm.pbf --bounds=$bbox --maxzoom=14 --languages=ru,be,en
      --output=out/$id.pmtiles --force --tmpdir=data/tmp/$id --nodemap-type=array --storage=mmap)
# the country pack covers the whole bbox (for «вырезать район»); oblasts are limited to tiles touching the oblast polygon
[[ $id != belarus ]] && args+=(--polygon=data/regions/$id.poly)
[[ -s data/sources/water-polygons-split-3857.zip ]] || args+=(--download)
$JAVA -Xmx${PLANETILER_XMX:-12g} -jar tools/planetiler.jar "${args[@]}"
rm -rf data/tmp/$id
