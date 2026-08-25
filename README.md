# Łódź Public Transport — interactive map

Interactive, poster-grade map of the public transport of **Łódź and its
agglomeration**: the ZDiT buses (city lines, the night N family and the county
services) and the MPK tram network including the two regional lines — 126 lines
/ 3 712 km drawn along the real street and track geometry.

## Live

**https://miqell24.github.io/lodz-bus-map/** — GitHub Pages from `main:/docs`. Local build on port 8157 (`npm run serve`).

One feed, two modes:

| mode | feed · route_type | lines | graph |
|---|---|---|---|
| buses | ZDiT Łódź (otwarte.miasto.lodz.pl) · 3 | 104 | OSM roadways |
| trams | ZDiT Łódź · 0 | 22 | `railway=tram` tracks |

The sheet reaches as far as the timetable does: Zgierz and Stryków in the
north, Pabianice and Rzgów in the south, Aleksandrów, Konstantynów and
Lutomiersk in the west, Brzeziny and Andrespol in the east — 40 × 30 km, of
which 894 km of roadway and track carry a line.

Build quirks worth knowing:

* **Not every route in the feed is a passenger line.** `skipRoute` drops the
  R family (tram R8, buses R9…R26) — the "linie zjazdowe", depot pull-ins
  carrying the number of the line they belong to; R8's whole timetable is two
  trips between the same pole at the Telefoniczna depot — and P1/P2, P4/P7 and
  oP6, MPK's own staff shuttles, whose every trip is headed "PRZEWÓZ
  PRACOWNIKÓW". 138 routes in, 126 lines drawn. The **Z lines stay**: unlike
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

`npm run download` fetches the feed, OSM roadways and rails (Overpass, bbox
51.60–51.96 N / 19.15–19.83 E) and MapLibre GL. `npm run build` map-matches
every line (HMM/Viterbi on the OSM graphs) and writes GeoJSON to `data/out/`;
`npm run lines` adds the line-by-line view on top of it, `npm run audit`
checks that view. `npm run serve` hosts the map at http://localhost:8157.

Data: GTFS ZDiT Łódź from the city's open-data portal
(otwarte.miasto.lodz.pl, "Transport i komunikacja") · base map
© OpenFreeMap / OpenMapTiles / OpenStreetMap contributors.
