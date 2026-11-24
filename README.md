# topo-data — офлайн-пакеты карт Беларуси для «Топо»

Скрипты, которые собирают пакеты карт (PMTiles) и каталог `catalog.json` для Android-приложения «Топо»
(формат — `topo-android/DESIGN.md` §3.3, разбор — `core/PackCatalog.kt`). Готовые файлы публикуются
как ассеты GitHub-релиза (поддерживают HTTP Range, нужны для «вырезать район»).

## Состав

| Файл | Вид | Масштабы | Размер |
|---|---|---|---|
| `brest-oblast.pmtiles` | base, Брестская область | z0–14 | 122,3 МБ |
| `vitebsk-oblast.pmtiles` | base, Витебская область | z0–14 | 155,0 МБ |
| `gomel-oblast.pmtiles` | base, Гомельская область | z0–14 | 98,0 МБ |
| `grodno-oblast.pmtiles` | base, Гродненская область | z0–14 | 95,8 МБ |
| `minsk-oblast.pmtiles` | base, Минская область и г. Минск | z0–14 | 166,8 МБ |
| `mogilev-oblast.pmtiles` | base, Могилёвская область | z0–14 | 96,1 МБ |
| `belarus.pmtiles` | base, вся страна (+ источник `extract` для «вырезать район») | z0–14 | 501,6 МБ |
| `contours-<область>.pmtiles` ×6 | contours, горизонтали по областям | z10–14 | 35,0 / 55,2 / 44,4 / 35,5 / 63,0 / 46,9 МБ |
| `contours-belarus.pmtiles` | contours, вся страна (только `extract`) | z10–14 | 187,2 МБ |
| `hillshade-belarus.pmtiles` | hillshade, отмывка, WebP с прозрачностью | z8–12 | 79,2 МБ |
| `catalog.json` | каталог | | 12 КБ |

Размеры — сборка 2026-11-23 (OSM-выгрузка Geofabrik того же дня). Всего в каталоге 14 пакетов, 1,59 ГБ.

* **base** — схема OpenMapTiles (Planetiler `0.10.2`), подписи `name`, `name:ru`, `name:be`, `name:en`
  (`--languages=ru,be,en`). Области ограничены настоящими границами из OSM (`admin_level=4`, Минск
  объединён с Минской областью): `--polygon` оставляет только плитки, касающиеся области (+~1 км).
  `belarus.pmtiles` покрывает весь прямоугольник страны.
* **contours** — слой `contour`, атрибуты `ele` (м, целое) и `index` (1 — основная, кратная 25 м; 0 —
  промежуточная). Сечение 5 м. Основные — с z10, все — с z12 (так их и рисует стиль приложения).
  Целиком страна весит 187 МБ (> 150 МБ), поэтому в `packs` — по областям, а страна — только как
  источник `extract` (вырезать горизонтали для своего района).
* **hillshade** — «только тени»: чёрный с альфой (ровные места прозрачны, карта не белеет), освещение
  с северо-запада, высота 45°, вертикальное преувеличение ×3 (рельеф Беларуси плоский). z8–12: на z12
  пиксель ≈ 23 м — это уже разрешение DEM; z13 был бы лишь интерполяцией и раздувал пакет в 2,8 раза
  (220 МБ против 79 МБ), поэтому по умолчанию не делается (`HILLSHADE_MAXZOOM=13` в `build.sh` — вернуть).

## Источники и лицензии

* **OpenStreetMap** — © участники OpenStreetMap, [ODbL 1.0](https://opendatacommons.org/licenses/odbl/).
  Выгрузка `https://download.geofabrik.de/europe/belarus-latest.osm.pbf`. Пакеты — производная база
  данных: по условию share-alike **этот репозиторий должен быть публичным**, с указанием источника и
  лицензии. Схема плиток — OpenMapTiles (CC-BY 4.0): в приложении нужно показывать
  «© OpenMapTiles © участники OpenStreetMap».
* **Natural Earth / OSM water polygons / lake centerlines** — подгружаются Planetiler (`--download`) для
  мелких масштабов и моря (public domain / ODbL).
* **Copernicus DEM GLO-30** — публичный бакет AWS `copernicus-dem-30m` (без ключей), 60 листов 1°×1°
  N51–N56, E023–E032. «Copernicus DEM © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018
  provided under COPERNICUS by the European Union and ESA». Свободное использование с указанием авторства.

Важно: GLO-30 — модель **поверхности** (DSM): в лесах и городах в высоту входят деревья и здания. Перед
построением горизонталей DEM сглаживается (Гаусс, σ = 2 пикселя ≈ 50 м), мелкие замкнутые горизонтали
(< 300 м длиной) отбрасываются, но у опушек и в городах горизонтали всё равно «облизывают» лес и
кварталы. Для настоящей топоосновы со временем стоит перейти на DTM (например, FABDEM — но у него
лицензия CC BY-NC-SA, только некоммерческое использование).

## Сборка

Нужно: macOS/Linux, Java 21 (по умолчанию `/opt/homebrew/opt/openjdk@21/bin/java`, задаётся `JAVA=`),
Python 3.12 для создания `.venv` (`PYTHON_BOOT=`), ~10 ГБ диска, 16+ ГБ ОЗУ. Ни Homebrew-пакетов, ни
GDAL, ни tippecanoe не нужно: всё — Planetiler (jar в `./tools`) и колёса Python (rasterio/fiona несут
свой GDAL) в `./.venv`.

```sh
TAG=v2026-11-23 ./build.sh               # всё с нуля в ./out/
SKIP_DOWNLOAD=1 TAG=v2026-11-23 ./build.sh   # не перекачивать OSM (листы DEM всегда докачиваются только недостающие)
```

Шаги (`build.sh`):

1. `setup` — `.venv` (`requirements.txt`), `tools/planetiler.jar`.
2. `download` — OSM-выгрузка Geofabrik, листы Copernicus DEM (`scripts/fetch_dem.sh`).
3. `regions` — границы областей и страны из OSM (`scripts/oblasts.py`, pyosmium) → `data/regions/*.poly|geojson`, `regions.json` (bbox).
4. `base-packs` — Planetiler OpenMapTiles: страна и 6 областей (`scripts/base.sh <id>`).
5. `dem-mosaic` — сшивка листов DEM в одну сетку + сглаживание (`scripts/dem_mosaic.py`).
6. `contours` — горизонтали contourpy по листам 1° с общим краем (линии соседних листов стыкуются точно),
   обрезка по стране +3 км → `data/contours.gpkg` (`scripts/contours.py`).
7. `contour-packs` — Planetiler `generate-custom` со схемой `scripts/contours.yml` → PMTiles по областям
   и на всю страну (`scripts/contours_pack.sh <id>`).
8. `hillshade` — отмывка в numpy, плитки WebP, пирамида усреднением → PMTiles (`scripts/hillshade.py`).
9. `catalog` — `out/catalog.json`: размеры, sha256, bbox, масштабы, средний размер плитки по уровням для `extract`
   (`scripts/catalog.py`).

Время на Mac (18 ядер, 64 ГБ), 2026-11-23: загрузка OSM 352 МБ ≈ 2 мин, DEM 1,7 ГБ ≈ 45 с;
границы 14 с; base-пакеты 6 мин 12 с (страна ≈ 3 мин 25 с, область ≈ 50–70 с); мозаика DEM 16 с;
горизонтали 13 с; пакеты горизонталей 26 с; отмывка 24 с; каталог 1 с. **Итого ≈ 7 мин 46 с** без загрузок
(`out/build-times.txt`).

`scripts/inspect_tile.py file.pmtiles z lon lat` — показать слои и число объектов в плитке.

## Публикация (вручную)

Все `url` в каталоге абсолютные: `https://github.com/foxyclaw/topo-data/releases/download/$TAG/<файл>`
(тег задаётся одной переменной `TAG`). Приложение по умолчанию читает каталог из релиза с тегом `catalog`,
поэтому `catalog.json` кладётся и туда:

```sh
gh release create $TAG out/*.pmtiles out/catalog.json --title "Карты $TAG" --notes "OSM $VERSION, Copernicus DEM GLO-30"
gh release upload catalog out/catalog.json --clobber    # релиз `catalog` создать один раз
```

GitHub ограничивает ассет 2 ГБ — самый большой файл 0,5 ГБ.

## Заметки для приложения (`topo-android`)

* Стиль (`core/MapStyle.kt`) ждёт слой `contour` и атрибут `ele`, основные — `ele % 25 == 0`: совпадает,
  менять ничего не нужно. Дополнительный атрибут `index` можно использовать вместо вычисления остатка.
* Отмывка — прозрачная WebP 256 px; при `raster-opacity` 0,35 тени довольно слабые, можно поднять до 0,5–0,6.
* `extract` `contours-belarus` начинается с z10; `SizeEstimate` для z0–9 досчитает по кривой — небольшая
  переоценка, на сами вырезки не влияет (`Extract` берёт `minZoom` из заголовка PMTiles).
* В подписи авторства нужно и «© OpenMapTiles» (CC-BY схемы), каталог это уже передаёт в `attribution`.

---

## English summary

Build scripts for the offline map packs of the «Топо» Android app: OpenMapTiles-schema vector packs
(Planetiler, languages ru/be/en, z0–14) for each of the six Belarusian oblasts (clipped to the real OSM
boundaries via `--polygon`; Minsk city merged into Minsk oblast) plus one whole-country `belarus.pmtiles`
used as the "cut an area" extract source; contour packs (layer `contour`, attrs `ele`, `index`; 5 m interval,
index every 25 m; z10–14) from Copernicus DEM GLO-30, computed with contourpy and tiled by Planetiler's
custom YAML schema; a transparent WebP hillshade (z8–12); and `catalog.json` with sizes, sha256 and
per-zoom average tile sizes. No Homebrew, GDAL or tippecanoe required — only Java 21, the Planetiler jar
and Python wheels. Run `TAG=vYYYY-MM-DD ./build.sh`; output goes to `./out/` (≈ 8 min on an 18-core Mac,
downloads excluded).

Licences: OSM data © OpenStreetMap contributors, ODbL 1.0 — the packs are a derivative database, so this
repository must stay public (share-alike). Tile schema © OpenMapTiles (CC-BY 4.0). Copernicus DEM © DLR e.V.
2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and
ESA. Note that GLO-30 is a surface model (trees and buildings included); contours are smoothed but still
follow forest edges and city blocks.
