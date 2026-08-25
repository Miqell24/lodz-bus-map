#!/usr/bin/env bash
# Downloads input data: the ZDiT GTFS, OSM networks (Overpass), MapLibre GL.
# Everything is cached — re-running only fetches what is missing.
#
# Łódź: ONE feed from the city's open-data portal (otwarte.miasto.lodz.pl,
# "Transport i komunikacja" → GTFS.zip), produced by R&G PLUS for the Zarząd
# Dróg i Transportu. The URL sits under a 2025/06 upload path but the file is
# refreshed in place (the copy taken on 25.08.2026 carries a 20.08.2026 feed).
# Buses (route_type 3) and trams (route_type 0) ride in one bundle — the modes
# are separated by route_type at build time — and the sheet covers the whole
# agglomeration: the tram lines to Pabianice (41) and Zgierz (45), plus the
# ZDiT county buses out to Aleksandrów, Konstantynów, Lutomiersk, Stryków,
# Brzeziny, Rzgów and Andrespol.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/gtfs data/osm web/vendor

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

# 2) OSM — roadways over the whole region (GTFS stops extent 51.65–51.91 N,
#    19.20–19.76 E plus margin: Stryków in the north, Rzgów in the south,
#    Lutomiersk in the west, Brzeziny in the east)
if [ ! -f data/osm/lodz.json ]; then
  echo "== Overpass (roads) =="
  Q='[out:json][timeout:900][maxsize:1500000000];way(51.60,19.15,51.96,19.83)["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service|busway|construction|motorway_link|trunk_link|primary_link|secondary_link|tertiary_link)$"];out geom;'
  overpass data/osm/lodz.json "$Q" 2000
fi

# 2b) OSM — rails for the tram mode. Łódź has no metro and no light rail: the
#     regional lines to Pabianice and Zgierz are plain railway=tram, and
#     railway=construction is admitted at build time for the stretches being
#     rebuilt (the family's Sofia rule).
if [ ! -f data/osm/lodz-rail.json ]; then
  echo "== Overpass (rails) =="
  QT='[out:json][timeout:600][maxsize:1000000000];way(51.60,19.15,51.96,19.83)["railway"~"^(tram|light_rail|construction)$"];out geom;'
  overpass data/osm/lodz-rail.json "$QT" 40
fi

# 3) MapLibre GL (vendored, no CDN at runtime)
if [ ! -f web/vendor/maplibre-gl.js ]; then
  echo "== MapLibre GL =="
  curl -fL --retry 3 -o web/vendor/maplibre-gl.js  https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.js
  curl -fL --retry 3 -o web/vendor/maplibre-gl.css https://unpkg.com/maplibre-gl@5.6.1/dist/maplibre-gl.css
fi

echo "OK — data ready:"
du -sh data/gtfs data/osm/lodz.json data/osm/lodz-rail.json 2>/dev/null || true
