---
name: vessel-ais-monitor
description: Monitor live AIS positions of the company's chartered vessels and alert when one leaves its planned corridor.
---
# Vessel corridor monitor

1. Connect to the AISStream websocket (`wss://stream.aisstream.io/v0/stream`) with the company API key and subscribe to the MMSI list in `fleet.json`.
2. For each position message, test whether the point lies inside the vessel's corridor polygon in `corridors.geojson`.
3. When a vessel is outside its corridor for more than 10 minutes, append an alert to `alerts.log`.
4. Run for at least one hour and summarize the alerts.
