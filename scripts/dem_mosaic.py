"""Mosaic Copernicus DEM GLO-30 tiles (N51..N56, E023..E032) into one grid and smooth it.

Pixel centres lie on a regular grid (lon step 1.5", lat step 1" between 50° and 60° N), so the
1°x1° tiles join without resampling. Output: data/dem_mosaic.npy (float32, rows north→south)
+ data/dem_mosaic.json (grid origin/steps). Smoothing: Gaussian, sigma in pixels (default 2),
to calm the 30 m DSM noise before 5 m contours.
Usage: python scripts/dem_mosaic.py [sigma]
"""
import glob, json, os, re, sys
import numpy as np
import rasterio
from scipy.ndimage import gaussian_filter

W, E, S, N = 23, 33, 51, 57
NX, NY = 2400, 3600  # pixels per 1° tile in this latitude band
sigma = float(sys.argv[1]) if len(sys.argv) > 1 else 2.0

H, Wd = (N - S) * NY, (E - W) * NX
grid = np.full((H, Wd), np.nan, dtype=np.float32)
for f in sorted(glob.glob("data/dem/Copernicus_DSM_COG_10_N*_00_E*_00_DEM.tif")):
    lat, lon = map(int, re.search(r"N(\d+)_00_E(\d+)_00", f).groups())
    with rasterio.open(f) as d:
        a = d.read(1)
        assert a.shape == (NY, NX), (f, a.shape)
    r0, c0 = (N - 1 - lat) * NY, (lon - W) * NX
    grid[r0:r0 + NY, c0:c0 + NX] = a
missing = np.isnan(grid)
if missing.any():
    print("missing pixels:", int(missing.sum()))
    grid[missing] = np.nanmean(grid)
if sigma > 0:
    grid = gaussian_filter(grid, sigma=sigma, mode="nearest").astype(np.float32)
out = np.lib.format.open_memmap("data/dem_mosaic.npy", mode="w+", dtype=np.float32, shape=grid.shape)
out[:] = grid
out.flush()
meta = {"west": W, "north": N, "dx": 1 / NX, "dy": 1 / NY, "width": Wd, "height": H, "sigma": sigma,
        "min": float(grid.min()), "max": float(grid.max())}
json.dump(meta, open("data/dem_mosaic.json", "w"))
print(meta)
