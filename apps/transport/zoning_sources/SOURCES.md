# Public zoning snapshots

Downloaded 2026-09-25 from the Google My Maps KML exports publicly linked by
Encipedia. Copyright/attribution: UTCB / CCERS. Informational reproductions of
the named standards; retain attribution and verify against applicable project
codes. These snapshots are local for this application, not an official service.

| File | Google My Maps ID | Reference |
|---|---|---|
| ag.kml | 10fjg3Umd1FjX_eCkpEHev9eDh0qCiVmA | P100-1/2013, ag |
| tc.kml | 1zJiK00TmZYujq_74-1x_jBEvotUirmKq | P100-1/2013, Tc |
| snow.kml | 1sWbu-MzbKmy-AmqMc7HFYRku2RU0GI5L | CR 1-1-3/2012, sk; altitude <1000 m |
| wind.kml | 15rQJ5Bqzu6Kuv5VfHLZTrjW9184uo_Bz | CR 1-1-4/2012, qb; altitude <1000 m |

KML URL form: `https://www.google.com/maps/d/kml?forcekml=1&mid=MAP_ID`

Source articles:
- https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/harta-de-zonare-seismica-din-p100-1-2013.html
- https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/harta-de-zonare-seismica-tc-din-p100-2013.html
- https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/harta-de-zonare-a-incarcarii-din-zapada-pe-sol-conform-cr-1-1-3-2012.html
- https://www.encipedia.org/articole/proiectare/resurse-utile/harti-de-zonare/harta-de-zonare-a-presiunii-dinamice-a-vantului-conform-cr-1-1-4-2012.html

Polygon holes and all multipolygon components must be retained. `qb ≥0.7` is
a lower bound, never rewritten as equality. No nearest-city assignments.
The 250 m boundary warning is an application tolerance, not a code rule.

## Coastline screening fallback

`black_sea_coast.json` contains regional line features from Natural Earth
1:10 million coastline, retrieved 2026-09-25. This generalized cartographic
dataset is public domain. It supports a `Possible` coastal exposure hint and
approximate map distance only, not measured salinity or engineering exposure.
It never establishes that an inland point has no marine exposure.

- https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-coastline/
- https://www.naturalearthdata.com/about/terms-of-use/
- https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson

The OSM Overpass regional export returned HTTP 504 during this update; it was
not used as the source of this bundled fallback. Outside the regional coverage,
the existing live Overpass lookup remains available.
