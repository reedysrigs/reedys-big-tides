# Does HYCOM already contain the tide?

Generated 2026-10-01T01:00:00Z

Method: least-squares harmonic fit of mean + trend + M2/S2/N2/K1/O1 to a
14-day HYCOM time series, against the M2 amplitude FES2014 gives at the
same point. If HYCOM has no tide its fitted M2 is near zero and the two
fields can be added. If its M2 is the same order as FES's, they cannot.

### Endpoint discovery

| endpoint | dataset.xml | note |
|---|---|---|
| `ncss.hycom.org/thredds/ncss/grid/ESPC-D-V02/uv3z` | 200 | 200 but unrecognised body: '' |
| `tds.hycom.org/thredds/ncss/grid/ESPC-D-V02/uv3z` | 200 | 200 but unrecognised body: '' |
| `ncss.hycom.org/thredds/ncss/ESPC-D-V02/uv3z` | 200 | 200 but unrecognised body: '' |
| `tds.hycom.org/thredds/ncss/ESPC-D-V02/uv3z` | 200 | 200 but unrecognised body: '' |
| `ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |
| `tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |
| `ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |
| `tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |
| `ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |
| `tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z` | 200 | grid dataset description returned |

First usable endpoint: `https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z`

- variables advertised: `water_u`, `water_u_bottom`, `water_v`, `water_v_bottom`
- time range advertised: 2024-09-05T09:00:00Z

## Banks Strait - COULD NOT FETCH

```
no HYCOM endpoint and query combination worked.
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-40.7000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
```

## Mid Bass Strait - COULD NOT FETCH

```
no HYCOM endpoint and query combination worked.
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.5000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
```

## Shelf off Portland - COULD NOT FETCH

```
no HYCOM endpoint and query combination worked.
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-39.2000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
```

## Deep Tasman (control) - COULD NOT FETCH

```
no HYCOM endpoint and query combination worked.
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  tds.hycom.org/thredds/ncss/GLBy0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-12-04T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  ncss.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
  tds.hycom.org/thredds/ncss/grid/GLBv0.08/expt_93.0/uv3z [var=water_u&var=water_v&latitude=-36.0000&long] -> 400 Requested time range 2026-09-17T01:00:00Z - 2026-10-01T01:00:00Z does not intersect actual time range 2018-01-01T12:00:0
```

## Verdict

**INCONCLUSIVE** - no point produced both a HYCOM fit and an FES value.
Do not change the page on the strength of this run.

