# Build per-tile landmark files for the app from the Geofabrik "free" shapefiles (OpenStreetMap, ODbL).
import shapefile, json, math, os, sys, collections
SRC, OUT = sys.argv[1], sys.argv[2]
TILE = 0.05
T1 = {'park':'公園','playground':'遊び場','garden':'庭園','memorial':'記念碑','monument':'モニュメント','wayside_shrine':'祠（ほこら）',
      'wayside_cross':'史跡','artwork':'アート作品','viewpoint':'眺めのよい場所','attraction':'見どころ','museum':'博物館・美術館',
      'library':'図書館','fountain':'噴水','archaeological':'遺跡','castle':'城','ruins':'史跡','zoo':'動物園','picnic_site':'ピクニック広場'}
T2 = {'cafe':'カフェ','restaurant':'飲食店','post_office':'郵便局','community_centre':'地域の施設','bakery':'パン屋',
      'railway_station':'駅','railway_halt':'駅','tram_stop':'停留場','bus_station':'バスターミナル'}
T3 = {'bus_stop':'バス停'}
def pofw_kind(f):
    if f.startswith('buddhist'): return 'お寺'
    if f.startswith('christian'): return '教会'
    if f == 'shinto': return '神社'
    return '礼拝所'
def centroid(shape):
    pts = shape.points[:shape.parts[1]] if len(shape.parts) > 1 else shape.points
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        c = x0 * y1 - x1 * y0; a += c; cx += (x0 + x1) * c; cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        bx = shape.bbox; return (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2, 0.0
    a /= 2; cx /= 6 * a; cy /= 6 * a
    lat = cy; m2 = abs(a) * (111320 ** 2) * math.cos(math.radians(lat))   # rough area in m²
    return cx, cy, m2
tiles = collections.defaultdict(list); stats = collections.Counter()
def add(lon, lat, tier, kind, name, r, oid):
    k = f"{math.floor(lat / TILE)}_{math.floor(lon / TILE)}"
    tiles[k].append([round(lat, 5), round(lon, 5), tier, kind, name, r, oid]); stats[(tier, kind)] += 1
def layer(name, area, pick):
    rd = shapefile.Reader(os.path.join(SRC, name), encoding='utf-8')
    for sr in rd.iterShapeRecords():
        rec = sr.record; f = rec['fclass']; nm = (rec['name'] or '').strip()
        if area and not sr.shape.points: continue
        res = pick(f, nm)
        if not res: continue
        tier, kind = res
        if area:
            lon, lat, m2 = centroid(sr.shape)
            r = int(min(150, max(30, math.sqrt(m2) * 0.4))) if m2 else 30   # bigger areas → bigger arrival circle
        else:
            lon, lat = sr.shape.points[0]; r = 15
        add(lon, lat, tier, kind, nm, r, f"{'w' if area else 'n'}{rec['osm_id']}")
def pick_poi(f, nm):
    if f in T1: return 1, T1[f]
    if f in T2 and nm: return 2, T2[f]
    return None
def pick_pofw(f, nm): return 1, pofw_kind(f)
def pick_tr(f, nm):
    if f in T2 and nm: return 2, T2[f]
    if f in T3 and nm: return 3, T3[f]
    return None
layer('gis_osm_pois_free_1', False, pick_poi); layer('gis_osm_pois_a_free_1', True, pick_poi)
layer('gis_osm_pofw_free_1', False, pick_pofw); layer('gis_osm_pofw_a_free_1', True, pick_pofw)
layer('gis_osm_transport_free_1', False, pick_tr)
os.makedirs(OUT, exist_ok=True)
total = 0
for k, v in tiles.items():
    with open(os.path.join(OUT, k + '.json'), 'w', encoding='utf-8') as fh:
        json.dump(v, fh, ensure_ascii=False, separators=(',', ':')); total += len(v)
lats = [float(k.split('_')[0]) * TILE for k in tiles]; lons = [float(k.split('_')[1]) * TILE for k in tiles]
meta = {'source': 'OpenStreetMap (Geofabrik kanto-free.shp)', 'license': 'ODbL 1.0, © OpenStreetMap contributors',
        'date': sys.argv[3], 'tile': TILE, 'bbox': [min(lats), min(lons), max(lats) + TILE, max(lons) + TILE], 'tiles': sorted(tiles)}
with open(os.path.join(OUT, 'meta.json'), 'w', encoding='utf-8') as fh: json.dump(meta, fh, ensure_ascii=False, separators=(',', ':'))
print('tiles', len(tiles), 'places', total)
for (t, k), n in sorted(stats.items()): print(t, k, n)
