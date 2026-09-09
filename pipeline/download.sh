#!/usr/bin/env bash
# Downloads input data: three GTFS feeds, the OSM networks (Geofabrik +
# pyosmium) and MapLibre GL. Everything is cached — re-running only fetches
# what is missing.
#
# Łódź: THREE feeds. The city's own bundle from the open-data portal (otwarte.miasto.lodz.pl,
# "Transport i komunikacja" → GTFS.zip), produced by R&G PLUS for the Zarząd
# Dróg i Transportu. The URL sits under a 2025/06 upload path but the file is
# refreshed in place (the copy taken on 25.08.2026 carries a 20.08.2026 feed).
# Buses (route_type 3) and trams (route_type 0) ride in one bundle — the modes
# are separated by route_type at build time — and the sheet covers the whole
# agglomeration: the tram lines to Pabianice (41) and Zgierz (45), plus the
# ZDiT county buses out to Aleksandrów, Konstantynów, Lutomiersk, Stryków,
# Brzeziny, Rzgów and Andrespol. Beside it ride the two neighbouring town
# networks the ZDiT bundle does not carry: MZK Pabianice (its own GTFS) and
# MUK Zgierz (no GTFS anywhere — pipeline/zgierz-gtfs.py builds one out of the
# city's timetable site).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/gtfs data/gtfs-pabianice data/gtfs-zgierz data/osm web/vendor

# A downloaded extract is only accepted if it PARSES and carries a plausible
# number of elements. `grep -q '"elements"'` — the guard this family used
# everywhere — passes on a truncated response too: Brașov's roads arrived as a
# 65 kB fragment that still contained the string, was taken for complete, and
# silently skipped the city (16.08.2026).
ok_json () { # $1=file  $2=minimum element count
  python3 - "$1" "$2" <<'PYEOF' 2>/dev/null
import json, sys
try:
    sys.exit(0 if len(json.load(open(sys.argv[1])).get("elements", [])) >= int(sys.argv[2]) else 1)
except Exception:
    sys.exit(1)
PYEOF
}

# Kept for the day the mirrors come back (the OSM step below cuts a Geofabrik
# extract instead — see step 2).
# Overpass with patience: the public mirrors answer 504 ("Dispatcher_Client…
# timeout / server too busy") for minutes at a time, and a single pass over the
# three endpoints then leaves the city without a road graph (25.08.2026, the
# first Łódź run). Rounds with growing back-off, mirrors rotated inside each.
overpass () { # $1=outfile  $2=query  $3=minimum element count
  local out="$1" q="$2" floor="$3" round wait
  for round in 1 2 3 4 5 6 7 8; do
    for EP in "https://overpass-api.de/api/interpreter" \
              "https://maps.mail.ru/osm/tools/overpass/api/interpreter" \
              "https://overpass.kumi.systems/api/interpreter" \
              "https://overpass.private.coffee/api/interpreter"; do
      echo "-- round $round: $EP"
      if curl -fsS --max-time 900 -o "$out" --data-urlencode "data=$q" "$EP" && ok_json "$out" "$floor"; then
        return 0
      fi
      rm -f "$out"
    done
    wait=$((round * 45))
    echo "-- all mirrors busy, waiting ${wait}s"
    sleep "$wait"
  done
  echo "Overpass: all mirrors failed for $out" >&2
  return 1
}

# 1) GTFS — ZDiT Łódź (stable URL, refreshed in place)
if [ ! -f data/gtfs/routes.txt ]; then
  echo "== GTFS → data/gtfs =="
  curl -fL --retry 3 --max-time 600 \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36" \
    -o data/gtfs.zip "https://otwarte.miasto.lodz.pl/wp-content/uploads/2025/06/GTFS.zip"
  unzip -o data/gtfs.zip -d data/gtfs
fi

# 1b) GTFS — MZK Pabianice, the operator's own file (listed on odt.org.pl)
if [ ! -f data/gtfs-pabianice/routes.txt ]; then
  echo "== GTFS Pabianice =="
  curl -fL --retry 3 --max-time 300 -o data/pabianice-gtfs.zip "https://gtfs.mzkpabianice.pl/GTFS.zip"
  unzip -o data/pabianice-gtfs.zip -d data/gtfs-pabianice
fi

# 1c) GTFS — MUK Zgierz. No GTFS exists anywhere (not odt.org.pl, not
#     files.girlc.at, not cdn.zbiorkom.live), so pipeline/zgierz-gtfs.py builds
#     one from the city's own timetable site: stop sequences, running times and
#     departures per day type. The poles carry no coordinates there and are
#     geocoded against OSM's stop nodes (pipeline/pbf-stops.py) and the ZDiT
#     feed, so this step runs after the OSM cut below on a first run.
# (see step 4)

# 2) OSM — from the Geofabrik lodzkie extract, not Overpass. On 9.09.2026
#    every public mirror answered this 40 × 47 km road query with 504 for an
#    hour (the wall Berlin, London, São Paulo and Vienna hit before), so the
#    cut is made locally: pipeline/pbf-cut.py (needs `pip3 install --user
#    osmium`) writes exactly the JSON Overpass would have returned, node ids
#    included, for the same two boxes — roads over the region and the tram
#    tracks (Łódź has no metro and no light rail; railway=construction is
#    admitted for the stretches being rebuilt, the family's Sofia rule).
if [ ! -f data/osm/lodz.json ] || [ ! -f data/osm/lodz-rail.json ]; then
  python3 -c "import osmium" 2>/dev/null || { echo "brak pakietu osmium — zainstaluj: pip3 install --user osmium" >&2; exit 1; }
  if [ ! -f data/lodzkie-latest.osm.pbf ]; then
    echo "== Geofabrik lodzkie-latest.osm.pbf =="
    curl -fL --retry 5 --retry-delay 5 -C - --max-time 3600 -o data/lodzkie-latest.osm.pbf       "https://download.geofabrik.de/europe/poland/lodzkie-latest.osm.pbf"
  fi
  echo "== cutting OSM out of the extract =="
  python3 pipeline/pbf-cut.py
fi

# 2b) OSM — the bus-stop nodes of the Zgierz area, which geocode MUK's poles
if [ ! -f data/osm/zgierz-stops.json ]; then
  python3 pipeline/pbf-stops.py
fi

# 2c) MUK Zgierz → GTFS (needs the stop nodes above and the ZDiT stops)
if [ ! -f data/gtfs-zgierz/routes.txt ]; then
  echo "== MUK Zgierz z rozklady.miasto.zgierz.pl =="
  python3 pipeline/zgierz-gtfs.py data/gtfs-zgierz
fi

# 3) MapLibre GL (vendored, no CDN at runtime)
if [ ! -f web/vendor/maplibre-gl.js ]; then
  echo "== MapLibre GL =="
  curl -fL --retry 3 -o web/vendor/maplibre-gl.js  https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js
  curl -fL --retry 3 -o web/vendor/maplibre-gl.css https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css
fi

echo "OK — data ready:"
du -sh data/gtfs data/gtfs-pabianice data/gtfs-zgierz data/osm/lodz.json data/osm/lodz-rail.json 2>/dev/null || true
