# Build per-tile landmark files for the app from an OpenStreetMap .osm.pbf extract (ODbL).
# usage: python3 make_tiles_pbf.py <in.osm.pbf> <out_dir> <data_date>
import osmium, json, math, os, sys, collections
SRC, OUT, DATE = sys.argv[1], sys.argv[2], sys.argv[3]
TILE = 0.05

def kind_of(t):
    g = t.get
    if g('leisure') == 'park': return '公園'
    if g('leisure') == 'playground': return '遊び場'
    if g('leisure') == 'garden': return '庭園'
    if g('tourism') == 'artwork': return '像' if g('artwork_type') == 'statue' else '彫刻' if g('artwork_type') == 'sculpture' else 'アート作品'
    if g('tourism') == 'viewpoint': return '眺めのよい場所'
    if g('tourism') == 'attraction': return '見どころ'
    if g('tourism') == 'museum': return '博物館・美術館'
    if g('tourism') == 'zoo': return '動物園'
    if g('tourism') == 'picnic_site': return 'ピクニック広場'
    if g('amenity') == 'place_of_worship':
        r = g('religion'); return '神社' if r == 'shinto' else 'お寺' if r == 'buddhist' else '教会' if r == 'christian' else '礼拝所'
    if g('historic') == 'memorial': return '像' if g('memorial') == 'statue' else '記念碑'
    if g('historic') == 'monument': return 'モニュメント'
    if g('historic') == 'wayside_shrine': return '祠（ほこら）'
    if g('historic') in ('castle',): return '城'
    if g('historic') in ('archaeological_site',): return '遺跡'
    if g('historic'): return '史跡'
    if g('amenity') == 'fountain': return '噴水'
    if g('amenity') == 'library': return '図書館'
    if g('amenity') == 'cafe': return 'カフェ'
    if g('amenity') == 'restaurant': return '飲食店'
    if g('shop') == 'bakery': return 'パン屋'
    if g('amenity') == 'post_office': return '郵便局'
    if g('amenity') == 'community_centre': return '地域の施設'
    if g('amenity') == 'bus_station': return 'バスターミナル'
    if g('railway') == 'station': return '駅'
    if g('highway') == 'bus_stop': return 'バス停'
    return None

def tier_of(t):
    g = t.get
    if g('highway') == 'bus_stop': return 3
    if g('amenity') in ('cafe', 'restaurant', 'post_office', 'community_centre', 'bus_station') or g('shop') == 'bakery' or g('railway') == 'station': return 2
    return 1

def accept(t):
    """Return (tier, kind) or None."""
    if t.get('access') in ('private', 'no') or t.get('disused') == 'yes': return None
    k = kind_of(t)
    if not k: return None
    tier = tier_of(t)
    name = t.get('name:ja') or t.get('name')
    if tier > 1 and not name: return None              # everyday places only with a name
    if k == '庭園' and not name: return None              # unnamed gardens are often private yards
    if t.get('historic') and k == '史跡' and not name: return None
    return tier, k

tiles = collections.defaultdict(list); stats = collections.Counter(); seen = set()
def add(lat, lon, tier, kind, name, r, oid):
    tiles[f"{math.floor(lat / TILE)}_{math.floor(lon / TILE)}"].append([round(lat, 5), round(lon, 5), tier, kind, name, r, oid])
    stats[(tier, kind)] += 1

keys = ('leisure', 'tourism', 'historic', 'amenity', 'shop', 'railway', 'highway')
fp = osmium.FileProcessor(SRC).with_locations().with_areas(osmium.filter.KeyFilter(*keys)).with_filter(osmium.filter.KeyFilter(*keys))
for o in fp:
    if o.is_node():
        res = accept(o.tags)
        if not res: continue
        name = o.tags.get('name:ja') or o.tags.get('name') or ''
        add(o.location.lat, o.location.lon, res[0], res[1], name, 15, f"n{o.id}")
    elif o.is_area():
        res = accept(o.tags)
        if not res: continue
        # centroid of the largest outer ring (shoelace), area in m² for the arrival radius
        best = None
        for ring in o.outer_rings():
            pts = [(n.lon, n.lat) for n in ring if n.location.valid()]
            if len(pts) < 3: continue
            a = cx = cy = 0.0
            for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
                c = x0 * y1 - x1 * y0; a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
            if abs(a) < 1e-14: continue
            if not best or abs(a) > abs(best[0]): best = (a, cx / (3 * a), cy / (3 * a))
        if not best: continue
        a2, lon, lat = best
        m2 = abs(a2) / 2 * (111320 ** 2) * math.cos(math.radians(lat))
        r = int(min(150, max(30, math.sqrt(m2) * 0.4)))
        oid = f"{'w' if o.from_way() else 'r'}{o.orig_id()}"
        name = o.tags.get('name:ja') or o.tags.get('name') or ''
        add(lat, lon, res[0], res[1], name, r, oid)

os.makedirs(OUT, exist_ok=True)
total = 0
for k, v in tiles.items():
    with open(os.path.join(OUT, k + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(v, fh, ensure_ascii=False, separators=(',', ':')); total += len(v)
lats = [int(k.split('_')[0]) * TILE for k in tiles]; lons = [int(k.split('_')[1]) * TILE for k in tiles]
meta = {'source': 'OpenStreetMap (Geofabrik kanto-latest.osm.pbf)', 'license': 'ODbL 1.0, © OpenStreetMap contributors',
        'date': DATE, 'tile': TILE, 'bbox': [round(min(lats), 2), round(min(lons), 2), round(max(lats) + TILE, 2), round(max(lons) + TILE, 2)], 'tiles': sorted(tiles)}
with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fh: json.dump(meta, fh, ensure_ascii=False, separators=(',', ':'))
print('tiles', len(tiles), 'places', total)
for (t, k), n in sorted(stats.items()): print(t, k, n)
