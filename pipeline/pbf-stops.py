#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cuts the bus-stop NODES of the Zgierz area out of the Geofabrik lodzkie
extract into data/osm/zgierz-stops.json.

MUK Zgierz publishes its timetables as web pages with stop names and pole
numbers but no coordinates (pipeline/zgierz-gtfs.py), so the poles have to be
geocoded — the Ruse method: OSM's own stop nodes, matched by name.
"""
import json, os, sys
import osmium

ROOT = os.path.join(os.path.dirname(__file__), '..')
PBF = os.path.join(ROOT, 'data', 'lodzkie-latest.osm.pbf')
BOX = (51.66, 19.18, 52.02, 19.62)   # S, W, N, E — Zgierz, Ozorkow and the Lodz ends
OUT = os.path.join(ROOT, 'data/osm/zgierz-stops.json')

if os.path.exists(OUT):
    sys.exit(0)
if not os.path.exists(PBF):
    sys.exit(f'brak {PBF} — pobierz go (pipeline/download.sh)')
out = []


class H(osmium.SimpleHandler):
    def node(self, n):
        t = n.tags
        if t.get('highway') != 'bus_stop' and t.get('public_transport') not in ('platform', 'stop_position'):
            return
        if 'name' not in t:
            return
        la, lo = n.location.lat, n.location.lon
        if not (BOX[0] <= la <= BOX[2] and BOX[1] <= lo <= BOX[3]):
            return
        out.append({'type': 'node', 'id': n.id, 'lat': la, 'lon': lo,
                    'tags': {x.k: x.v for x in t}})


print('czytam', os.path.basename(PBF), flush=True)
H().apply_file(PBF)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump({'version': 0.6, 'generator': 'pbf-stops.py (Geofabrik lodzkie)', 'elements': out}, open(OUT, 'w'))
print(f'słupki: {len(out)}', flush=True)
