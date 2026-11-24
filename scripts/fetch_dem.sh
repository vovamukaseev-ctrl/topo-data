#!/bin/zsh
# Download Copernicus DEM GLO-30 tiles (public AWS bucket, no auth) covering Belarus: N51..N56, E023..E032.
set -e
cd "$(dirname $0)/.."
mkdir -p data/dem
BUCKET=https://copernicus-dem-30m.s3.amazonaws.com
fetch() {
  local n=Copernicus_DSM_COG_10_N$1_00_E$2_00_DEM
  [[ -s data/dem/$n.tif ]] && return 0
  if curl -sf -o data/dem/$n.tif.part "$BUCKET/$n/$n.tif"; then mv data/dem/$n.tif.part data/dem/$n.tif
  else rm -f data/dem/$n.tif.part; echo "missing $n"; fi
}
for lat in 51 52 53 54 55 56; do
  for lon in 023 024 025 026 027 028 029 030 031 032; do
    fetch $lat $lon &
    while (( $(jobs -r | wc -l) >= 8 )); do sleep 0.2; done
  done
done
wait
ls data/dem/*.tif | wc -l
