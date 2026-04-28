"""
Pulls Redfin data, cross-references DCAD, outputs CSV + map.

Usage:
    python analyze_block.py
"""

import requests
import pandas as pd
import numpy as np
import io
import time
import sys
import json
import difflib
import os
import struct

sys.path.insert(0, os.path.dirname(__file__))
import redfin_tool as rt

DCAD_DIR   = os.path.join(os.path.dirname(__file__), 'dcad_data')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _lcc_batch(xs, ys):
    """NAD83 State Plane Texas North Central (US Survey Feet) → WGS84 lat/lng arrays."""
    a    = 6378137.0
    e2   = 2/298.257222101 - (1/298.257222101)**2
    e    = np.sqrt(e2)
    ft2m = 0.3048006096012192
    phi1 = np.radians(32 + 8/60);  phi2 = np.radians(33 + 58/60)
    phi0 = np.radians(31 + 40/60); lam0 = np.radians(-98.5)
    FE   = 1968500.0 * ft2m;       FN   = 6561666.6666667 * ft2m
    xm   = np.asarray(xs, dtype=float) * ft2m
    ym   = np.asarray(ys, dtype=float) * ft2m
    def _m(p): return np.cos(p) / np.sqrt(1 - e2*np.sin(p)**2)
    def _t(p): s=np.sin(p); return np.tan(np.pi/4-p/2)*((1+e*s)/(1-e*s))**(e/2)
    m1,m2 = _m(phi1),_m(phi2); t0,t1,t2 = _t(phi0),_t(phi1),_t(phi2)
    n  = (np.log(m1)-np.log(m2))/(np.log(t1)-np.log(t2))
    F  = m1/(n*t1**n); r0 = a*F*t0**n
    dx = xm-FE; dy = r0-(ym-FN)
    r  = np.sign(n)*np.sqrt(dx**2+dy**2)
    ti = (r/(a*F))**(1/n)
    lam = np.arctan2(dx,dy)/n+lam0
    phi = np.pi/2-2*np.arctan(ti)
    for _ in range(10):
        phi = np.pi/2-2*np.arctan(ti*((1-e*np.sin(phi))/(1+e*np.sin(phi)))**(e/2))
    return np.degrees(phi), np.degrees(lam)


def _read_parcel_dbf(dbf_path):
    """Return list of Acct strings from PARCEL_GEOM.dbf."""
    with open(dbf_path, 'rb') as f:
        hdr = f.read(32)
        num_records = struct.unpack('<I', hdr[4:8])[0]
        header_size = struct.unpack('<H', hdr[8:10])[0]
        record_size = struct.unpack('<H', hdr[10:12])[0]
        fields, off = [], 1
        while True:
            fd = f.read(32)
            if fd[0] == 0x0D or len(fd) < 32:
                break
            name = fd[:11].replace(b'\x00', b'').decode('ascii', errors='ignore')
            fields.append({'name': name, 'len': fd[16], 'off': off})
            off += fd[16]
        acct_fd = next((fd for fd in fields if fd['name'].upper() == 'ACCT'), None)
        if not acct_fd:
            return None, num_records, header_size, record_size
        f.seek(header_size)
        accts = []
        for _ in range(num_records):
            rec = f.read(record_size)
            accts.append(rec[acct_fd['off']:acct_fd['off']+acct_fd['len']]
                         .decode('ascii', errors='ignore').strip())
    return accts, num_records, header_size, record_size


def _load_parcel_coords(dcad_dir):
    """Return {acct: (lat, lng)} centroid lookup from PARCEL_GEOM shapefile, or None."""
    shp_path = os.path.join(dcad_dir, 'PARCEL_GEOM', 'PARCEL_GEOM.shp')
    dbf_path = os.path.join(dcad_dir, 'PARCEL_GEOM', 'PARCEL_GEOM.dbf')
    if not os.path.exists(shp_path):
        return None
    accts, num_records, _, _ = _read_parcel_dbf(dbf_path)
    if accts is None:
        return None
    xs = np.full(num_records, np.nan)
    ys = np.full(num_records, np.nan)
    with open(shp_path, 'rb') as f:
        f.seek(100)
        for i in range(num_records):
            rec_hdr = f.read(8)
            if len(rec_hdr) < 8:
                break
            content_len = struct.unpack('>I', rec_hdr[4:8])[0] * 2
            content = f.read(content_len)
            if len(content) >= 36 and struct.unpack('<i', content[:4])[0] in (5, 15, 25):
                xmin, ymin, xmax, ymax = struct.unpack('<4d', content[4:36])
                xs[i] = (xmin + xmax) / 2
                ys[i] = (ymin + ymax) / 2
    valid = ~np.isnan(xs)
    lats = np.full(num_records, np.nan)
    lngs = np.full(num_records, np.nan)
    lats[valid], lngs[valid] = _lcc_batch(xs[valid], ys[valid])
    return {acct: (lats[i], lngs[i])
            for i, acct in enumerate(accts) if not np.isnan(lats[i])}


def _load_parcel_polygons(dcad_dir, account_nums):
    """Return {acct: rings} where rings = [[[lat, lng], ...]] for each parcel polygon."""
    shp_path = os.path.join(dcad_dir, 'PARCEL_GEOM', 'PARCEL_GEOM.shp')
    dbf_path = os.path.join(dcad_dir, 'PARCEL_GEOM', 'PARCEL_GEOM.dbf')
    if not os.path.exists(shp_path):
        return {}
    accts, num_records, _, _ = _read_parcel_dbf(dbf_path)
    if accts is None:
        return {}
    target = set(str(a).strip() for a in account_nums if pd.notna(a))
    idx_to_acct = {i: acct for i, acct in enumerate(accts) if acct in target}
    raw = {}
    with open(shp_path, 'rb') as f:
        f.seek(100)
        for i in range(num_records):
            rec_hdr = f.read(8)
            if len(rec_hdr) < 8:
                break
            content_len = struct.unpack('>I', rec_hdr[4:8])[0] * 2
            if i not in idx_to_acct:
                f.seek(content_len, 1)
                continue
            content = f.read(content_len)
            if len(content) < 44 or struct.unpack('<i', content[:4])[0] not in (5, 15, 25):
                continue
            num_parts  = struct.unpack('<i', content[36:40])[0]
            num_points = struct.unpack('<i', content[40:44])[0]
            parts = list(struct.unpack(f'<{num_parts}i', content[44:44+num_parts*4]))
            parts.append(num_points)
            po = 44 + num_parts * 4
            pts = struct.unpack(f'<{num_points*2}d', content[po:po+num_points*16])
            rings = []
            for p in range(num_parts):
                s, e = parts[p], parts[p+1]
                rings.append([(pts[j*2], pts[j*2+1]) for j in range(s, e)])
            raw[idx_to_acct[i]] = rings
    if not raw:
        return {}
    all_x, all_y, meta, cur = [], [], {}, 0
    for acct, rings in raw.items():
        rl = [len(r) for r in rings]
        for ring in rings:
            all_x.extend(x for x, y in ring)
            all_y.extend(y for x, y in ring)
        meta[acct] = (cur, rl)
        cur += sum(rl)
    lats, lngs = _lcc_batch(np.array(all_x), np.array(all_y))
    result = {}
    for acct, (start, rl) in meta.items():
        rings_out, idx = [], start
        for length in rl:
            rings_out.append([[float(lats[idx+j]), float(lngs[idx+j])] for j in range(length)])
            idx += length
        result[acct] = rings_out
    return result

# ── Step 1: get area ──────────────────────────────────────────────────────────

sorted_neighborhoods = sorted(rt.DALLAS_NEIGHBORHOODS.keys())

print("Available Dallas neighborhoods:")
for i, n in enumerate(sorted_neighborhoods, 1):
    print(f"  {i:2}. {n.title()}")

print("\nHow do you want to define the area?")
print("  1 - Pick a neighborhood from the list above")
print("  2 - Load URL from saved .txt file")
choice = input("\nChoice (1 or 2): ").strip()

if choice == '2':
    print("\nHow to get the URL:")
    print("  1. Go to redfin.com and find the area you want")
    print("  2. Use the draw tool on the Redfin map to draw your shape")
    print("  3. Press F12 to open DevTools, click the Network tab, type 'gis' in the filter box")
    print("  4. Go back to the map and pan or move it slightly — new requests will appear in the list")
    print("  5. Click any of the new requests that pop up")
    print("  6. Right-click the URL at the top of the panel and copy it")
    print("  7. Open Notepad, paste the URL, and save it as any name (e.g. highland_park.txt)")
    print("     in the redfin folder — then come back here\n")
    # Read URL from a .txt file to avoid terminal special character issues with &.
    # Users save the URL to any named .txt file in the redfin folder, then pick it from a list.
    script_dir = os.path.dirname(__file__)
    txt_files = [f for f in os.listdir(script_dir) if f.endswith('.txt')]

    if not txt_files:
        print("\n  No .txt files found in the redfin folder.")
        print("  Save the URL to a text file first:")
        print("  - Open Notepad, paste the URL, save it in the redfin folder as anything.txt")
        print("  - Then run the script again.\n")
        sys.exit()

    print("\n  Saved URL files found:")
    for i, fname in enumerate(txt_files, 1):
        print(f"    {i} - {fname}")
    pick = input("\n  Pick a file (number): ").strip()
    try:
        url_file = os.path.join(script_dir, txt_files[int(pick) - 1])
    except (ValueError, IndexError):
        print("Invalid choice.")
        sys.exit()

    with open(url_file, 'r', encoding='utf-8') as f:
        raw = f.read().strip()

    if not raw or 'redfin' not in raw.lower():
        print(f"\nERROR: {url_file} doesn't look like a Redfin URL.")
        sys.exit()
    print(f"URL loaded from {os.path.basename(url_file)}")
    try:
        from urllib.parse import unquote_plus
        if 'user_poly=' in raw:
            poly_str = raw.split('user_poly=')[1].split('&')[0]
        elif 'poly=' in raw:
            poly_str = raw.split('poly=')[1].split('&')[0]
        else:
            poly_str = raw
        poly_str = unquote_plus(poly_str)
        pairs = [pt.strip().split() for pt in poly_str.split(',') if pt.strip()]
        lngs = [float(p[0]) for p in pairs]
        lats = [float(p[1]) for p in pairs]
        MIN_LNG, MAX_LNG = min(lngs), max(lngs)
        MIN_LAT, MAX_LAT = min(lats), max(lats)
    except (ValueError, IndexError) as e:
        print(f"\nERROR: Couldn't parse coordinates from the URL.")
        print(f"Make sure the URL contains 'user_poly=' or is just the coordinate string.")
        print(f"Debug info: {e}")
        sys.exit()
    label = input("Label for output files (e.g. 'oak_cliff_block1'): ").strip()
    if not label:
        label = f"{MIN_LNG},{MIN_LAT},{MAX_LNG},{MAX_LAT}"
else:
    pick = input("\nEnter number or name: ").strip()
    try:
        name = sorted_neighborhoods[int(pick) - 1]
    except (ValueError, IndexError):
        name = pick
    matched, coords = rt.find_neighborhood(name)
    if not coords:
        print(f"Couldn't find '{name}'. Use option 2 to paste coordinates.")
        sys.exit()
    if matched != name.lower().strip():
        print(f"Matched to: '{matched.title()}'")
    MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT = coords
    label = matched.title()

print()

# ── Step 2: pull Redfin ───────────────────────────────────────────────────────

print(f"Pulling Redfin listings for {label}...")
df_redfin = rt.pull_grid(MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT)
df_redfin = df_redfin.drop(columns=['block_id'], errors='ignore')
print(f"Redfin: {len(df_redfin)} active listings\n")

redfin_addresses = set(
    df_redfin['ADDRESS'].dropna().str.upper().str.strip().str.split('#').str[0].str.strip()
)
streets_clean = set()
for addr in redfin_addresses:
    parts = addr.split(' ', 1)
    if len(parts) == 2:
        streets_clean.add(parts[1].split(' UNIT ')[0].strip())

# Save Redfin output
redfin_out = label.lower().replace(' ', '_')
df_redfin.to_csv(os.path.join(OUTPUT_DIR, f'redfin_{redfin_out}.csv'), index=False)

# ── Step 3: check DCAD is available ──────────────────────────────────────────

required = ['ACCOUNT_INFO.CSV', 'ACCOUNT_APPRL_YEAR.CSV', 'RES_DETAIL.CSV']
missing  = [f for f in required if not os.path.exists(os.path.join(DCAD_DIR, f))]
if missing:
    print("DCAD data not found. Download from dallascad.org/dataproducts.aspx")
    print("Extract into a folder called dcad_data/ in this project folder.")
    print(f"Missing: {missing}")
    print(f"\nRedfin data saved to redfin_{redfin_out}.csv")
    sys.exit()

# ── Steps 4-5: load parcel coords then filter DCAD by bounding box ────────────

print("Loading parcel coordinates from DCAD shapefile...")
coord_map = _load_parcel_coords(DCAD_DIR)

print("Loading DCAD data...")
acct  = pd.read_csv(os.path.join(DCAD_DIR, 'ACCOUNT_INFO.CSV'), dtype=str)
apprl = pd.read_csv(os.path.join(DCAD_DIR, 'ACCOUNT_APPRL_YEAR.CSV'), dtype=str)
res   = pd.read_csv(os.path.join(DCAD_DIR, 'RES_DETAIL.CSV'), dtype=str)
land  = pd.read_csv(os.path.join(DCAD_DIR, 'LAND.CSV'), dtype=str)
exempt_val = pd.read_csv(os.path.join(DCAD_DIR, 'ACCT_EXEMPT_VALUE.CSV'), dtype=str)
total_exempt_accts = set(
    exempt_val[exempt_val['EXEMPTION_CD'].str.strip() == '14']['ACCOUNT_NUM'].astype(str).str.strip()
)

if coord_map is not None:
    # Filter parcel coords to bounding box — get every account number in the area
    in_box   = {a: (lat, lng) for a, (lat, lng) in coord_map.items()
                if MIN_LAT <= lat <= MAX_LAT and MIN_LNG <= lng <= MAX_LNG}
    acct_set = set(in_box.keys())
    dcad     = acct[acct['DIVISION_CD'].isin(['RES', 'COM'])].copy()
    acct_keys = dcad['ACCOUNT_NUM'].astype(str).str.strip()
    dcad      = dcad[acct_keys.isin(acct_set)].copy()
    acct_keys = dcad['ACCOUNT_NUM'].astype(str).str.strip()
    dcad['LAT'] = acct_keys.map(lambda a: in_box.get(a, (np.nan, np.nan))[0])
    dcad['LNG'] = acct_keys.map(lambda a: in_box.get(a, (np.nan, np.nan))[1])
    print(f"DCAD candidates: {len(dcad)}")
    dcad_box = dcad.dropna(subset=['LAT', 'LNG']).copy()
    print(f"In bounding box: {len(dcad_box)}")
else:
    # Fallback: street-name filter + Census geocoder
    print("Shapefile not found — falling back to street-name filter + Census geocoder...")
    redfin_zips = set(df_redfin['ZIP OR POSTAL CODE'].dropna().astype(str).str[:5].unique()) if 'ZIP OR POSTAL CODE' in df_redfin.columns else {'75229', '75230'}
    dcad = acct[
        (acct['DIVISION_CD'].isin(['RES', 'COM'])) &
        (acct['PROPERTY_ZIPCODE'].str[:5].isin(redfin_zips)) &
        (acct['FULL_STREET_NAME'].isin(streets_clean))
    ].copy()
    dcad['STREET_NUM_INT'] = pd.to_numeric(dcad['STREET_NUM'], errors='coerce')
    nums = []
    for addr in redfin_addresses:
        try:
            nums.append(int(addr.split()[0]))
        except:
            pass
    if nums:
        num_min = max(0, min(nums) - 200)
        num_max = max(nums) + 200
        dcad = dcad[(dcad['STREET_NUM_INT'] >= num_min) & (dcad['STREET_NUM_INT'] <= num_max)].copy()
    print(f"DCAD candidates: {len(dcad)}")
    rows = [
        f'{idx},"{row["STREET_NUM"]} {row["FULL_STREET_NAME"]}","Dallas","TX","{str(row["PROPERTY_ZIPCODE"])[:5]}"'
        for idx, row in dcad.iterrows()
    ]
    r = requests.post(
        'https://geocoding.geo.census.gov/geocoder/locations/addressbatch',
        files={'addressFile': ('addr.csv', '\n'.join(rows), 'text/csv')},
        data={'benchmark': 'Public_AR_Current'},
        timeout=180
    )
    geo = pd.read_csv(io.StringIO(r.text), header=None,
                      names=['id','input_addr','match','match_type','matched_addr','coords','tiger_id','side'], dtype=str)
    geo = geo[geo['match'] == 'Match'].copy()
    coords_split = geo['coords'].str.split(',', expand=True)
    geo['LNG'] = pd.to_numeric(coords_split[0], errors='coerce')
    geo['LAT'] = pd.to_numeric(coords_split[1], errors='coerce')
    geo['id'] = geo['id'].astype(str)
    dcad.index = dcad.index.astype(str)
    dcad = dcad.join(geo[['id', 'LAT', 'LNG']].set_index('id'), how='left')
    dcad_box = dcad[
        (dcad['LAT'] >= MIN_LAT) & (dcad['LAT'] <= MAX_LAT) &
        (dcad['LNG'] >= MIN_LNG) & (dcad['LNG'] <= MAX_LNG)
    ].copy()
    print(f"In bounding box: {len(dcad_box)}")

# ── Step 6: join values, flag on/off market ───────────────────────────────────

land_cols = land.groupby('ACCOUNT_NUM').first()[['ZONING','FRONT_DIM','DEPTH_DIM','AREA_SIZE','AREA_UOM_DESC']].reset_index()
dcad_box = dcad_box.merge(apprl[['ACCOUNT_NUM','LAND_VAL','IMPR_VAL','TOT_VAL','ISD_JURIS_DESC','SPTD_CODE']], on='ACCOUNT_NUM', how='left')
dcad_box = dcad_box.merge(res[['ACCOUNT_NUM','YR_BUILT','TOT_LIVING_AREA_SF','TOT_MAIN_SF']], on='ACCOUNT_NUM', how='left')
dcad_box = dcad_box.merge(land_cols, on='ACCOUNT_NUM', how='left')
for col in ['LAND_VAL','IMPR_VAL','TOT_VAL','YR_BUILT','TOT_LIVING_AREA_SF','TOT_MAIN_SF','LAT','LNG','FRONT_DIM','DEPTH_DIM','AREA_SIZE']:
    dcad_box[col] = pd.to_numeric(dcad_box[col], errors='coerce')
# Normalize AREA_SIZE to square feet regardless of source unit
acre_mask = dcad_box['AREA_UOM_DESC'].str.upper().str.strip() == 'ACRE'
dcad_box.loc[acre_mask, 'AREA_SIZE'] = dcad_box.loc[acre_mask, 'AREA_SIZE'] * 43560

SPTD_LABELS = {
    'A11': 'Single Family Residences',      'A12': 'Single Family Residences',
    'A13': 'Mobile Homes',                  'A14': 'Quadruplex/Triplex',
    'B11': 'Multifamily Residences',        'B12': 'Multifamily Residences',
    'C11': 'Vacant Lots and Land Tracts',   'C12': 'Vacant Lots and Land Tracts',
    'D11': 'Qualified Open-Space Land',     'E11': 'Farm and Ranch Improvements',
    'F11': 'Commercial Real Property',      'F10': 'Commercial Real Property',
    'L10': 'Business Personal Property',    'M31': 'Other Personal Property',
    'O11': 'Residential Inventory',         'X11': 'Totally Exempt Property',
}

dcad_box['PROPERTY_ADDRESS'] = (dcad_box['STREET_NUM'] + ' ' + dcad_box['FULL_STREET_NAME']).str.strip().str.upper()
dcad_box['LAND_PCT']    = (dcad_box['LAND_VAL'] / dcad_box['TOT_VAL'] * 100).round(1)
dcad_box['ON_REDFIN']   = dcad_box['PROPERTY_ADDRESS'].isin(redfin_addresses)
dcad_box['SUBDIVISION'] = dcad_box['LEGAL1'].fillna('').str.strip()
dcad_box['LEGAL_DESC']  = dcad_box[['LEGAL1','LEGAL2','LEGAL3','LEGAL4','LEGAL5']].fillna('').agg(' '.join, axis=1).str.strip()
dcad_box['STATE_CODE']  = dcad_box['SPTD_CODE'].map(SPTD_LABELS).fillna(dcad_box['SPTD_CODE'])

# Google Maps link for spot checking — clickable in Excel/Sheets
dcad_box['GOOGLE_MAPS'] = dcad_box.apply(
    lambda r: f"https://maps.google.com/?q={str(r['STREET_NUM']).strip()}+{str(r['FULL_STREET_NAME']).strip().replace(' ', '+')},+Dallas+TX+{str(r['PROPERTY_ZIPCODE'])[:5]}",
    axis=1
)

# ── Step 7: save CSV ──────────────────────────────────────────────────────────

out = dcad_box[['PROPERTY_ADDRESS','ON_REDFIN','OWNER_NAME1','OWNER_ADDRESS_LINE1',
                'OWNER_CITY','OWNER_STATE','OWNER_ZIPCODE',
                'LAND_VAL','IMPR_VAL','TOT_VAL','LAND_PCT','YR_BUILT',
                'TOT_LIVING_AREA_SF','TOT_MAIN_SF',
                'STATE_CODE','ZONING','AREA_SIZE','FRONT_DIM','DEPTH_DIM',
                'ISD_JURIS_DESC','NBHD_CD','SUBDIVISION','LEGAL_DESC','LAT','LNG','GOOGLE_MAPS']].copy()
out.columns = ['Property Address','Status','Owner Name','Owner Mailing Address',
               'Owner City','Owner State','Owner Zip',
               'Land Value','Improvement Value','Total Value','Land % of Total',
               'Year Built','Living Area (sq ft)','Total Structure Area (sq ft)',
               'State Code','Zoning','Lot Size (sq ft)','Frontage (ft)','Depth (ft)',
               'School District','Neighborhood Code','Subdivision','Legal Description','Latitude','Longitude','Google Maps Link']
out['Status'] = out['Status'].map({True: 'Active', False: 'Off Market'})
out = out.sort_values('Property Address')

csv_file = os.path.join(OUTPUT_DIR, f'block_analysis_{redfin_out}.csv')
out.to_csv(csv_file, index=False)

sptd_col     = dcad_box['SPTD_CODE'].fillna('') if 'SPTD_CODE' in dcad_box.columns else pd.Series([''] * len(dcad_box), index=dcad_box.index)
on_count     = int(dcad_box['ON_REDFIN'].sum())
GOVT_KEYWORDS = ['CITY OF DALLAS', 'DALLAS COUNTY', 'STATE OF TEXAS', 'UNITED STATES',
                 'TXDOT', 'TX DEPT', ' ISD', 'DISD', 'DART ', 'NTTA']
owner_upper  = dcad_box['OWNER_NAME1'].fillna('').str.upper()
govt_mask    = owner_upper.apply(lambda o: any(k in o for k in GOVT_KEYWORDS))
exempt_mask  = dcad_box['ACCOUNT_NUM'].astype(str).str.strip().isin(total_exempt_accts) | sptd_col.isin(['X11']) | govt_mask
off_mask     = ~dcad_box['ON_REDFIN']
multi_count  = int((off_mask & ~exempt_mask & sptd_col.isin(['B11','B12','A14'])).sum())
vacant_count = int((off_mask & ~exempt_mask & sptd_col.isin(['C11','C12'])).sum())
comm_count   = int((off_mask & ~exempt_mask & sptd_col.isin(['F10','F11'])).sum())
exempt_count = int((off_mask & exempt_mask).sum())
off_sf_count = int(off_mask.sum()) - multi_count - vacant_count - comm_count - exempt_count
print(f"\nResults for {label}:")
print(f"  Active listings:   {on_count}")
print(f"  Off market:        {off_sf_count}")
print(f"  Multifamily:       {multi_count}")
print(f"  Vacant lots:       {vacant_count}")
print(f"  Commercial:        {comm_count}")
print(f"  Exempt:            {exempt_count}")
print(f"  Total:             {len(out)}")
print(f"\nSaved: {csv_file}")

# ── Step 8: build map ─────────────────────────────────────────────────────────

print("Loading parcel outlines for map...")
poly_map = _load_parcel_polygons(DCAD_DIR, dcad_box['ACCOUNT_NUM'].astype(str).str.strip())
print(f"Polygon outlines: {len(poly_map)} parcels")

features = []
for _, row in dcad_box.dropna(subset=['LAT','LNG']).iterrows():
    acct = str(row['ACCOUNT_NUM']).strip()
    sptd = str(row['SPTD_CODE']).strip() if 'SPTD_CODE' in dcad_box.columns and pd.notna(row.get('SPTD_CODE')) else ''
    owner_up = str(row['OWNER_NAME1']).upper() if pd.notna(row.get('OWNER_NAME1')) else ''
    is_govt  = any(k in owner_up for k in ['CITY OF DALLAS', 'DALLAS COUNTY', 'STATE OF TEXAS',
                                            'UNITED STATES', 'TXDOT', 'TX DEPT', ' ISD', 'DISD', 'DART ', 'NTTA'])
    if str(row['ACCOUNT_NUM']).strip() in total_exempt_accts or sptd == 'X11' or is_govt:
        prop_type = 'exempt'
    elif sptd in ('B11', 'B12', 'A14'):
        prop_type = 'multifamily'
    elif sptd in ('C11', 'C12'):
        prop_type = 'vacant'
    elif sptd in ('F10', 'F11'):
        prop_type = 'commercial'
    else:
        prop_type = 'single_family'
    props = {
        'on_redfin':  bool(row['ON_REDFIN']),
        'prop_type':  prop_type,
        'addr':      str(row['PROPERTY_ADDRESS']),
        'owner':     str(row['OWNER_NAME1'] or ''),
        'land_val':   f"${row['LAND_VAL']:,.0f}"            if pd.notna(row['LAND_VAL'])              else 'N/A',
        'tot_val':    f"${row['TOT_VAL']:,.0f}"             if pd.notna(row['TOT_VAL'])               else 'N/A',
        'land_pct':   f"{row['LAND_PCT']:.1f}%"             if pd.notna(row['LAND_PCT'])              else 'N/A',
        'lot_acres':  f"{row['AREA_SIZE']/43560:.2f} ac"    if pd.notna(row['AREA_SIZE']) and row['AREA_SIZE'] > 0 else 'N/A',
        'frontage':   f"{int(row['FRONT_DIM'])} ft"         if pd.notna(row['FRONT_DIM']) and row['FRONT_DIM'] > 0 else 'N/A',
        'depth':      f"{int(row['DEPTH_DIM'])} ft"         if pd.notna(row['DEPTH_DIM']) and row['DEPTH_DIM'] > 0 else 'N/A',
        'state_code': str(row['STATE_CODE']).strip()        if pd.notna(row['STATE_CODE'])            else 'N/A',
        'zoning':     str(row['ZONING']).strip()            if pd.notna(row['ZONING'])                else 'N/A',
        'school':     str(row['ISD_JURIS_DESC']).strip()    if pd.notna(row['ISD_JURIS_DESC'])        else 'N/A',
        'yr_built':   str(int(row['YR_BUILT']))              if pd.notna(row['YR_BUILT']) and row['YR_BUILT'] > 0 else 'N/A',
        'sqft':       f"{int(row['TOT_LIVING_AREA_SF']):,}"  if pd.notna(row['TOT_LIVING_AREA_SF']) and row['TOT_LIVING_AREA_SF'] > 0 else 'N/A',
        'lat':        float(row['LAT']),
        'lng':        float(row['LNG']),
    }
    if acct in poly_map:
        rings = [[[pt[1], pt[0]] for pt in ring] for ring in poly_map[acct]]
        features.append({'type': 'Feature',
                         'geometry': {'type': 'Polygon', 'coordinates': rings},
                         'properties': props})
    else:
        features.append({'type': 'Feature',
                         'geometry': {'type': 'Point', 'coordinates': [float(row['LNG']), float(row['LAT'])]},
                         'properties': props})

geojson_data = json.dumps({'type': 'FeatureCollection', 'features': features})
center_lat = (MIN_LAT + MAX_LAT) / 2
center_lng = (MIN_LNG + MAX_LNG) / 2

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{label} — On Market vs Off Market</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin:0; font-family:Arial,sans-serif; }}
  #map {{ height:100vh; width:100%; }}
  .legend {{ background:white; padding:12px 16px; border-radius:6px; box-shadow:0 2px 8px rgba(0,0,0,.3); font-size:13px; line-height:1.8; }}
  .swatch {{ display:inline-block; width:14px; height:14px; border-radius:3px; margin-right:6px; vertical-align:middle; opacity:0.85; }}
</style>
</head><body><div id="map"></div>
<script>
const geojson = {geojson_data};
const map = L.map('map').setView([{center_lat}, {center_lng}], 16);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO'
}}).addTo(map);

function getColor(p) {{
  if (p.on_redfin)                    return '#e74c3c';
  if (p.prop_type === 'multifamily')  return '#8e44ad';
  if (p.prop_type === 'vacant')       return '#27ae60';
  if (p.prop_type === 'commercial')   return '#e67e22';
  if (p.prop_type === 'exempt')       return '#95a5a6';
  return '#2980b9';
}}
function getBorder(p) {{
  if (p.on_redfin)                    return '#c0392b';
  if (p.prop_type === 'multifamily')  return '#6c3483';
  if (p.prop_type === 'vacant')       return '#1e8449';
  if (p.prop_type === 'commercial')   return '#d35400';
  if (p.prop_type === 'exempt')       return '#7f8c8d';
  return '#1a6a9a';
}}
function getStatus(p) {{
  if (p.on_redfin)                    return 'ACTIVE LISTING';
  if (p.prop_type === 'multifamily')  return 'MULTIFAMILY';
  if (p.prop_type === 'vacant')       return 'VACANT LOT';
  if (p.prop_type === 'commercial')   return 'COMMERCIAL';
  if (p.prop_type === 'exempt')       return 'EXEMPT (church/school/nonprofit)';
  return 'OFF MARKET';
}}

function makePopup(p) {{
  const color = getColor(p);
  const status = getStatus(p);
  return '<b>' + p.addr + '</b><br>' +
    '<span style="color:' + color + ';font-weight:bold">' + status + '</span><br><br>' +
    '<b>Owner:</b> ' + p.owner + '<br>' +
    '<b>Land Value:</b> ' + p.land_val + '<br>' +
    '<b>Total Value:</b> ' + p.tot_val + '<br>' +
    '<b>Land % of Total:</b> ' + p.land_pct + '<br>' +
    '<b>Lot Size:</b> ' + p.lot_acres + '<br>' +
    '<b>Frontage:</b> ' + p.frontage + '<br>' +
    '<b>Depth:</b> ' + p.depth + '<br>' +
    '<b>State Code:</b> ' + p.state_code + '<br>' +
    '<b>Zoning:</b> ' + p.zoning + '<br>' +
    '<b>School District:</b> ' + p.school + '<br>' +
    '<b>Year Built:</b> ' + p.yr_built + '<br>' +
    '<b>Sq Ft:</b> ' + p.sqft;
}}

L.geoJSON(geojson, {{
  style: function(f) {{
    if (f.geometry.type !== 'Polygon') return {{}};
    const c = getColor(f.properties); const b = getBorder(f.properties);
    return {{color: b, weight: 1.5, fillColor: c, fillOpacity: 0.12, opacity: 0.85}};
  }},
  pointToLayer: function(f, latlng) {{
    const c = getColor(f.properties); const b = getBorder(f.properties);
    return L.circleMarker(latlng, {{
      radius: f.properties.on_redfin ? 7 : 5,
      fillColor: c, color: b, weight: 1.5, opacity: 1, fillOpacity: 0.9
    }});
  }},
  onEachFeature: function(f, layer) {{
    layer.bindPopup(makePopup(f.properties));
    if (f.geometry.type === 'Polygon') {{
      const c = getColor(f.properties); const b = getBorder(f.properties);
      L.circleMarker([f.properties.lat, f.properties.lng], {{
        radius: f.properties.on_redfin ? 5 : 3,
        fillColor: c, color: b, weight: 1, opacity: 1, fillOpacity: 0.95
      }}).bindPopup(makePopup(f.properties)).addTo(map);
    }}
  }}
}}).addTo(map);

const legend = L.control({{position: 'bottomright'}});
legend.onAdd = () => {{
  const d = L.DomUtil.create('div', 'legend');
  d.innerHTML = '<b>{label}</b><br><br>' +
    '<span class="swatch" style="background:#e74c3c;border:1px solid #c0392b"></span>Active Listing ({on_count})<br>' +
    '<span class="swatch" style="background:#2980b9;border:1px solid #1a6a9a"></span>Off Market ({off_sf_count})<br>' +
    '<span class="swatch" style="background:#8e44ad;border:1px solid #6c3483"></span>Multifamily ({multi_count})<br>' +
    '<span class="swatch" style="background:#27ae60;border:1px solid #1e8449"></span>Vacant Lot ({vacant_count})<br>' +
    '<span class="swatch" style="background:#e67e22;border:1px solid #d35400"></span>Commercial ({comm_count})<br>' +
    '<span class="swatch" style="background:#95a5a6;border:1px solid #7f8c8d"></span>Exempt / Church / School ({exempt_count})<br><br>' +
    'Click any parcel for details.';
  return d;
}};
legend.addTo(map);
</script></body></html>"""

map_file = os.path.join(OUTPUT_DIR, f'map_{redfin_out}.html')
with open(map_file, 'w', encoding='utf-8') as f:
    f.write(html)
print(f"Map:   {map_file}")
print("\nDone.")
