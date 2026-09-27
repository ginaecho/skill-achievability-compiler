---
name: geocode-offline
description: Reverse-geocode a CSV of GPS points to the nearest city and country without calling any web API.
---
# Offline reverse geocoding

1. Install the `reverse_geocoder` Python package (it bundles the GeoNames city data).
2. Read `points.csv` (id, lat, lon) and look up the nearest city, admin region and country code for each point.
3. Write `points_geocoded.csv` with the added columns.
