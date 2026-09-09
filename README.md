# Łódź Public Transport — interactive map

Interactive, poster-grade map of the public transport of **Łódź and its
agglomeration**: the ZDiT buses (city lines, the night N family and the county
services), the MPK tram network including the two regional lines, and the two
neighbouring town networks that meet them — **MZK Pabianice** and **MUK
Zgierz**. **147 lines / 4 174 km** drawn along the real street and track
geometry, weighted mean matching error 1.9 m.

## Live

**https://miqell24.github.io/lodz-bus-map/** — GitHub Pages from `main:/docs`. Local build on port 8157 (`npm run serve`).

Three operators, two modes:

| mode | feed · route_type | lines | graph |
|---|---|---|---|
| buses | ZDiT Łódź (otwarte.miasto.lodz.pl) · 3 | 101 | OSM roadways |
| trams | ZDiT Łódź · 0 | 23 | `railway=tram` tracks |
| buses | **MZK Pabianice** (gtfs.mzkpabianice.pl) · 3 | 14 — the town's 1–7, the county 260–265, the T to Rzgów and the A41 | OSM roadways |
| buses | **MUK Zgierz** (built from the city's timetable site) · 3 | 9 — 1, 3, 4, 5, 6, 8, 9, 10, 61 | OSM roadways |

The sheet reaches as far as the timetables do: Ozorków, Zgierz and Stryków in
the north, Pabianice, Rzgów and Guzew in the south, Aleksandrów, Konstantynów
and Lutomiersk in the west, Brzeziny and Andrespol in the east.

**Zgierz has no GTFS.** Not on odt.org.pl, not on files.girlc.at, not on
cdn.zbiorkom.live; MUK's own site sends riders to jakdojade. What the city does
publish is its timetable pages — per line, the ordered stop list; per stop, the
departures by day type and the running time to every stop down the route — and
that is a timetable in everything but format, so `pipeline/zgierz-gtfs.py`
turns it into one. The pages carry no coordinates, so the poles are geocoded
against OSM's own stop nodes and the ZDiT feed (same city, same naming): 279 of
294 are found, and the fifteen that are not are single poles in Ozorków and the
Łódź centre, which the matcher bridges.

**Numbers repeat across the three operators** — Pabianice runs 1–7, Zgierz runs
1, 3, 4, 5, 6, 8, 9, 10 and a 61 of its own, and ZDiT's trams are numbered 1–16
— so a number used by more than one of them carries its operator's code in the
KEY (`mzk:1`, `muk:61`) and prints bare on the street. ZDiT is the home network
here and keeps its numbers as they are. The panel groups its chips by operator,
the way the Berlin and Randstad maps do.

Build quirks worth knowing:

* **Not every route in the feed is a passenger line.** `skipRoute` drops the
  R family (tram R8, buses R9…R26) — the "linie zjazdowe", depot pull-ins
  carrying the number of the line they belong to; R8's whole timetable is two
  trips between the same pole at the Telefoniczna depot — and P1/P2, P4/P7 and
  oP6, MPK's own staff shuttles, whose every trip is headed "PRZEWÓZ
  PRACOWNIKÓW". 138 ZDiT routes in, 124 lines drawn. The **Z lines stay**: unlike
  Warsaw's Z-buses or Budapest's *pótló* they are permanent fixtures here
  (Z11 alone runs 2 877 trips a week, more than any other bus in the city).
* **Line keys are the operator's own designations, verbatim** — including the
  bus `6.`, trailing dot and all, which is how MPK's timetables write the
  Łódź Kaliska – Zgierz zone line (mpk.lodz.pl, line id 1127). It sits beside
  tram `6` in the panel; the frontend tells the two apart by mode.
* **The feed's shapes are sparse** — 32 148 jumps longer than 200 m across the
  variants in use, some of them 3.8 km. Anything over 300 m is treated as a
  data gap and bridged by routing on the OSM graph instead of interpolated, so
  the drawn line follows streets rather than cutting corners. Mean matching
  error came out at 1–3 m per line-direction, and no line is drawn more than
  2 % short of its GTFS length.
* `railway=construction` counts as the kind of track it is being built as
  (the rule Sofia's tram 6 forced), so a rebuilt stretch OSM has not retagged
  yet still carries its line.
* The representative variant of every line+direction is the LONGEST pattern
  still worked by ≥15 % of the busiest pattern's trips — the busiest shape is
  very often a peak-hour short-turn.
* **Neither guest feed ships shapes.** Pabianice does; Zgierz does not, and
  neither does the timetable site it is built from, so there the stop sequence
  IS the matching observation (the Olsztyn/GPA arrangement).
* **A41 stays.** The family drops rail-replacement buses (Warsaw's Z-, the
  Budapest *pótló*), but the A41 is not a stopgap for works: it is what
  Pabianice runs where the tram to Łódź used to, in its own timetable, under
  its own number.

Known residue: one pole, *Żwirki-Piotrkowska*, is dropped as 419 m from every
line calling there.

## Two views

The panel's **Corridors / Lines** switch redraws the same data two ways.
*Corridors* is one stroke per roadway, the whole network in its mode colours
(navy buses, red trams). *Lines* draws every line on its own — up to four
coloured strands side by side, anything busier as one grey trunk with its
numbers beside it (`npm run lines`, checked by `npm run audit`). 73.5 % of the
2 732 roadway runs carry four lines or fewer and are drawn strand by strand;
the widest trunk gathers 21 lines. No network diagram for this city yet.

## Pipeline

`npm run download` fetches the three feeds (and builds the Zgierz one), cuts
the OSM roadways and rails and vendors MapLibre GL. **The OSM comes from
Geofabrik, not Overpass**: on 9.09.2026 every public mirror answered the
40 × 47 km road query with 504 for an hour, so `pipeline/pbf-cut.py` (needs
`pip3 install --user osmium`) cuts the same two boxes — 51.60–51.96 N /
19.15–19.83 E — out of `lodzkie-latest.osm.pbf`, and `pipeline/pbf-stops.py`
cuts the stop nodes that geocode Zgierz's poles. `npm run build` map-matches
every line (HMM/Viterbi on the OSM graphs) and writes GeoJSON to `data/out/`;
`npm run lines` adds the line-by-line view on top of it, `npm run audit`
checks that view. `npm run serve` hosts the map at http://localhost:8157.

Data: GTFS ZDiT Łódź from the city's open-data portal (otwarte.miasto.lodz.pl,
"Transport i komunikacja") · GTFS MZK Pabianice (gtfs.mzkpabianice.pl, listed
on odt.org.pl) · MUK Zgierz timetables from rozklady.miasto.zgierz.pl · base
map © OpenFreeMap / OpenMapTiles / OpenStreetMap contributors.
