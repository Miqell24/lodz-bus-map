#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MUK Zgierz -> GTFS.

Miejskie Uslugi Komunikacyjne w Zgierzu publish no GTFS anywhere - not on
odt.org.pl, not on files.girlc.at, not on cdn.zbiorkom.live - and the
operator's own site sends riders to jakdojade. What the city does publish is
its timetable site, https://rozklady.miasto.zgierz.pl, and that site is
complete:

  ?line_id=<id>                          every route of a line: its title
                                         ("A - B") and the ORDERED stop list,
                                         each stop a route_stop id
  /3320/harmonogram.html?route_stop=<id> that stop's departures by day type
                                         (weekday / Saturday / Sunday), plus
                                         the whole sequence again with the
                                         running time to every stop ("+7 min")

So: the stop list is the route, the running times turn it into stop_times, and
the departures at the FIRST stop are the trips. What the site does not carry is
coordinates - the poles are named ("Parzeczewska/Staffa (116)"), never located
- so they are geocoded against OSM's own stop nodes, the way Ruse's poles were
(data/osm/zgierz-stops.json, cut by pipeline/pbf-stops.py).

No shapes: the stop sequence is the matching observation, like Olsztyn or GPA.

Every GET is cached on disk (<outdir>/.zg-cache) so a rerun costs nothing.

usage: zgierz-gtfs.py <outdir>
"""
import csv, difflib, hashlib, html, json, os, re, subprocess, sys, unicodedata

BASE = 'https://rozklady.miasto.zgierz.pl'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0 Safari/537.36')
AGENCY = ('muk', 'Miejskie Uslugi Komunikacyjne w Zgierzu', 'https://muk.zgierz.pl/')

ROOT = os.path.join(os.path.dirname(__file__), '..')
out_dir = sys.argv[1] if len(sys.argv) > 1 else 'data/gtfs-zgierz'
out_dir = out_dir if os.path.isabs(out_dir) else os.path.join(ROOT, out_dir)
os.makedirs(out_dir, exist_ok=True)
cache_dir = os.path.join(out_dir, '.zg-cache')
os.makedirs(cache_dir, exist_ok=True)


def get(url, tries=4):
    """curl, not urllib: this python build has no CA bundle for urllib."""
    cp = os.path.join(cache_dir, hashlib.md5(url.encode()).hexdigest() + '.html')
    if os.path.exists(cp):
        with open(cp, encoding='utf-8') as fh:
            return fh.read()
    for _ in range(tries):
        p = subprocess.run(['curl', '-sL', '-A', UA, '--max-time', '60', url],
                           capture_output=True)
        if p.returncode == 0 and len(p.stdout) > 2000:
            d = p.stdout.decode('utf-8', 'replace')
            with open(cp, 'w', encoding='utf-8') as fh:
                fh.write(d)
            return d
    sys.exit('nie udalo sie pobrac ' + url)


def txt(s):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))).strip()


# -- 1) the lines -----------------------------------------------------------
home = get(BASE + '/3317/wybierz-linie.html')
lines = [(m.group(1), txt(m.group(2))) for m in
         re.finditer(r'class="btn btn-primary btn-line-routes"\s+data-id="(\d+)"\s*>\s*(.*?)</button>',
                     home, re.S)]
if not lines:
    sys.exit('nie znalazlem przyciskow linii - strona zmienila uklad')
print('linie: %d - %s' % (len(lines), ', '.join(n for _, n in lines)), flush=True)

ROUTE_RE = re.compile(r'<div class="transport-route">(.*?)</div>\s*</div>', re.S)
TITLE_RE = re.compile(r'class="transport-route__title">(.*?)</h2>', re.S)
STOP_RE = re.compile(r'route_stop=(\d+)"[^>]*class="route-list__link"[^>]*>(.*?)</a>', re.S)

routes = []          # (line, title, [(route_stop_id, stop_name)])
for lid, name in lines:
    page = get(BASE + '/?line_id=' + lid)
    for block in ROUTE_RE.findall(page):
        t = TITLE_RE.search(block)
        stops = [(sid, txt(s)) for sid, s in STOP_RE.findall(block)]
        if len(stops) >= 2:
            routes.append((name, txt(t.group(1)) if t else '', stops))
print('kierunki: %d' % len(routes), flush=True)

# -- 2) running times and departures, from the first stop of each route ------
SEQ_RE = re.compile(
    r'data-routeStopId="(\d+)"\s*>\s*(.*?)<span class="route-stops__departure-times"'
    r'\s+data-sequence="(\d+)"[^>]*>(.*?)</span>', re.S)
DIFF_RE = re.compile(r'departure-times-diff">\+?(\d+) min')
ROW_RE = re.compile(r'<tr>\s*<th>(\d{1,2})</th>(.*?)</tr>', re.S)
CELL_RE = re.compile(r'<td>(.*?)</td>', re.S)
ITEM_RE = re.compile(r'class="item">\s*(\d{1,2})')

DAYS = [('pn-pt', '1,1,1,1,1,0,0'), ('sob', '0,0,0,0,0,1,0'), ('nd', '0,0,0,0,0,0,1')]

patterns = []        # (line, title, [(name, offset)], {day: [minutes]})
for line, title, stops in routes:
    page = get(BASE + '/3320/harmonogram.html?route_stop=' + stops[0][0])
    seq = []
    for sid, nm, s, tail in SEQ_RE.findall(page):
        d = DIFF_RE.search(tail)
        seq.append((int(s), txt(nm), int(d.group(1)) if d else 0))
    seq.sort()
    if len(seq) < 2:
        print('  %s "%s" - brak sekwencji, pomijam' % (line, title), flush=True)
        continue
    # the selected stop is sequence 1; a loop route repeats it at the end with
    # the full running time, which is exactly what stop_times wants
    order = [(nm, off) for _, nm, off in seq]
    if order[0][1] and order[0][1] > order[1][1]:
        order[0] = (order[0][0], 0)
    dep = dict((d, []) for d, _ in DAYS)
    for hh, row in ROW_RE.findall(page):
        cells = CELL_RE.findall(row)
        for (d, _), cell in zip(DAYS, cells):
            for mm in ITEM_RE.findall(cell):
                dep[d].append(int(hh) * 60 + int(mm))
    if not any(dep.values()):
        print('  %s "%s" - brak odjazdow, pomijam' % (line, title), flush=True)
        continue
    patterns.append((line, title, order, dep))
    print('  %s "%s": %d przystankow, %d kursow'
          % (line, title, len(order), sum(len(v) for v in dep.values())), flush=True)

# -- 3) the poles, geocoded against OSM --------------------------------------
osm_file = os.path.join(ROOT, 'data/osm/zgierz-stops.json')
if not os.path.exists(osm_file):
    sys.exit('brak ' + osm_file + ' - uruchom pipeline/pbf-stops.py')
nodes = json.load(open(osm_file, encoding='utf-8'))['elements']


def norm(s):
    s = s.lower().replace('ł', 'l')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    # the parentheses hold the POLE NUMBER on the Zgierz side ("(116)", "(S1)")
    # and part of the NAME on the OSM side ("Lakowa (TBS)", "Slowik (szkola)"),
    # so only a short code is dropped
    s = re.sub(r'\((?:[\d\s#]{1,6}|[a-z]\d{1,3})\)', ' ', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    # "NZ" (na zadanie) and the "#" marker are timetable notation, not name
    return ' '.join(t for t in s.split() if t not in ('nz', 'n'))


# a town prefix on the OSM side is not part of what the timetable calls a stop
TOWN = {'zgierz', 'ozorkow', 'lodz', 'al', 'pl', 'os', 'ul'}


osm = {}
for n in nodes:
    k = norm(n['tags'].get('name', ''))
    if k:
        osm.setdefault(k, []).append((n['lat'], n['lon']))
# the ZDiT feed is the better authority for the poles inside Lodz, which lines
# 6, 61 and 8 reach: same city, same naming, coordinates straight from the
# operator. OSM stays the fallback (Zgierz and Ozorkow are not in that feed).
zdit = os.path.join(ROOT, 'data/gtfs/stops.txt')
if os.path.exists(zdit):
    with open(zdit, encoding='utf-8-sig') as fh:
        for r in csv.DictReader(fh):
            k = norm(r.get('stop_name', ''))
            if k and r.get('stop_lat'):
                osm.setdefault(k, []).append((float(r['stop_lat']), float(r['stop_lon'])))

names = sorted(set(nm for _, _, order, _ in patterns for nm, _ in order))
coord, miss, fuzzy = {}, [], []
for nm in names:
    k = norm(nm)
    hit = osm.get(k)
    if not hit:      # "Dluga/al. Armii Krajowej" vs "Dluga - Armii Krajowej",
        # "Proboszczewice I" vs OSM's "Zgierz - Proboszczewice I"
        want = set(k.split()) - TOWN
        hit = next((v for kk, v in osm.items()
                    if set(kk.split()) - TOWN == want), None)
    if not hit:      # the last resort: near-identical spelling (Cegielniania)
        near = difflib.get_close_matches(k, list(osm), n=1, cutoff=0.88)
        if near:
            hit = osm[near[0]]
            fuzzy.append((nm, near[0]))
    if hit:
        coord[nm] = (sum(a for a, _ in hit) / len(hit), sum(b for _, b in hit) / len(hit))
    else:
        miss.append(nm)
print('slupki: %d/%d zgeokodowane w OSM' % (len(coord), len(names)), flush=True)
for nm, k in fuzzy:
    print('  ~ %s -> %s' % (nm, k), flush=True)
if miss:
    print('  bez wspolrzednych: ' + ', '.join(miss), flush=True)

# -- 4) GTFS ----------------------------------------------------------------
def w(fn, header, rows):
    with open(os.path.join(out_dir, fn), 'w', newline='', encoding='utf-8') as fh:
        c = csv.writer(fh)
        c.writerow(header)
        c.writerows(rows)


w('agency.txt', ['agency_id', 'agency_name', 'agency_url', 'agency_timezone', 'agency_lang'],
  [[AGENCY[0], AGENCY[1], AGENCY[2], 'Europe/Warsaw', 'pl']])
sid = dict((nm, 's%d' % i) for i, nm in enumerate(sorted(coord)))
w('stops.txt', ['stop_id', 'stop_name', 'stop_lat', 'stop_lon'],
  [[sid[nm], nm, '%.6f' % coord[nm][0], '%.6f' % coord[nm][1]] for nm in sorted(coord)])
w('calendar.txt', ['service_id', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday',
                   'saturday', 'sunday', 'start_date', 'end_date'],
  [[d] + f.split(',') + ['20260901', '20261231'] for d, f in DAYS])

rt, tr, st = [], [], []
seen, ndir = set(), {}
for line, title, order, dep in patterns:
    if line not in seen:
        seen.add(line)
        rt.append([line, AGENCY[0], line, '', '3'])
    d_id = ndir.setdefault((line, title), len(ndir) % 2)
    for day, times in dep.items():
        for t0 in times:
            tid = ('%s_%d_%s_%d' % (line, d_id, day, t0))
            tr.append([line, day, tid, order[-1][0], d_id])
            for i, (nm, off) in enumerate(order):
                if nm not in sid:
                    continue
                m = t0 + off
                hhmm = '%02d:%02d:00' % (m // 60, m % 60)
                st.append([tid, hhmm, hhmm, sid[nm], i + 1])
w('routes.txt', ['route_id', 'agency_id', 'route_short_name', 'route_long_name', 'route_type'], rt)
w('trips.txt', ['route_id', 'service_id', 'trip_id', 'trip_headsign', 'direction_id'], tr)
w('stop_times.txt', ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'], st)
w('feed_info.txt', ['feed_publisher_name', 'feed_publisher_url', 'feed_lang'],
  [['zgierz-gtfs.py z rozklady.miasto.zgierz.pl', BASE, 'pl']])
print('GTFS: %d linii, %d kursow, %d zatrzyman -> %s'
      % (len(rt), len(tr), len(st), out_dir), flush=True)
