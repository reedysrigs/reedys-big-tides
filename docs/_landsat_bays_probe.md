# Landsat thermal over Port Phillip Bay and Western Port

Generated 2026-10-01T02:10:39Z

Box searched: 144.35..145.60 E, 37.80..38.70 S, last 180 days

## 1. Catalog reachability

| catalog | collection | result |
|---|---|---|
| Planetary Computer | `landsat-c2-l2` | 90 scenes |
| Earth Search (AWS) | `landsat-c2-l2` | 90 scenes |
| Earth Search (AWS) | `landsat-c2l2-sr` | 0 scenes |

Using **Planetary Computer** / `landsat-c2-l2`

## 2. Scenes over the bays

90 scenes in the window. Ten most recent:

| date | platform | path/row | cloud % | has thermal |
|---|---|---|---|---|
| 2026-09-27T00:10:06 | landsat-9 | 093/087 | 28.6 | `lwir11` |
| 2026-09-27T00:09:42 | landsat-9 | 093/086 | 18.1 | `lwir11` |
| 2026-09-20T00:03:51 | landsat-9 | 092/087 | 0.1 | `lwir11` |
| 2026-09-20T00:03:27 | landsat-9 | 092/086 | 0.0 | `lwir11` |
| 2026-09-19T00:09:57 | landsat-8 | 093/087 | 21.7 | `lwir11` |
| 2026-09-19T00:09:33 | landsat-8 | 093/086 | 20.1 | `lwir11` |
| 2026-09-12T00:03:41 | landsat-8 | 092/087 | 72.8 | `lwir11` |
| 2026-09-12T00:03:18 | landsat-8 | 092/086 | 9.1 | `lwir11` |
| 2026-09-11T00:10:00 | landsat-9 | 093/087 | 2.7 | `lwir11` |
| 2026-09-11T00:09:36 | landsat-9 | 093/086 | 1.0 | `lwir11` |

Scenes under 25% cloud: **31 of 90**
Distinct pass dates: 45. Median gap between passes: **7 days**

Asset names on the newest scene:

```
ang, atran, blue, cdist, coastal, drad, emis, emsd, green, lwir11, mtl.json, mtl.txt, mtl.xml, nir08, qa, qa_aerosol, qa_pixel, qa_radsat, red, rendered_preview, swir16, swir22, tilejson, trad, urad
```

## 3-4. Signing, and a WINDOWED read of the thermal band

A whole Landsat scene is ~1 GB. This only works on a free runner if a
sub-window can be read directly from the COG over HTTPS.

Trying scene `LC09_L2SP_093086_20260927_02_T1` (2026-09-27T00:09:42, cloud 18.12%)

Thermal asset key: `lwir11`
Signing: planetary_computer.sign() succeeded

Opened the COG. size 7661 x 7701, crs EPSG:32655, dtype uint16
Window over the bays: 3719 x 3409 pixels
Pixel size: **30 m**
Bytes actually read: roughly 20.4 MB (whole scene would be far more)

## 5. What the numbers look like

6667323 valid pixels of 10175184 in the window (66%)

| statistic | value |
|---|---|
| min | -1.99 degC |
| 1st pct | 1.45 degC |
| median | 14.10 degC |
| 99th pct | 22.76 degC |
| max | 49.10 degC |

Values in a physically plausible range for land+water: **yes**

## Verdict

**VIABLE.** 30 m thermal over the bays, windowed read, 90 scenes in the
last 180 days and 31 of them under 25% cloud.

Next: bake the water pixels only (cloud + land masked) into a PNG the
offshore page can load, the same way the tide field works.
