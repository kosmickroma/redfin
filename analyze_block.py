"""
Run this when Mike says "show me this block."
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

sys.path.insert(0, os.path.dirname(__file__))
import redfin_tool as rt

DCAD_DIR = os.path.join(os.path.dirname(__file__), 'dcad_data')

# ── Step 1: get area ──────────────────────────────────────────────────────────

print("Available Dallas neighborhoods:")
for n in sorted(rt.DALLAS_NEIGHBORHOODS.keys()):
    print(f"  - {n.title()}")

print("\nHow do you want to define the area?")
print("  1 - Type a neighborhood name")
print("  2 - Paste coordinates (min_lng, min_lat, max_lng, max_lat)")
choice = input("\nChoice (1 or 2): ").strip()

if choice == '2':
    raw = input("Coordinates: ").strip()
    try:
        MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT = [float(x.strip()) for x in raw.split(',')]
    except ValueError:
        print("Couldn't parse those — 4 numbers separated by commas.")
        sys.exit()
    label = f"{MIN_LNG},{MIN_LAT},{MAX_LNG},{MAX_LAT}"
else:
    name = input("\nNeighborhood name: ").strip()
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
df_redfin.to_csv(f'redfin_{redfin_out}.csv', index=False)

# ── Step 3: check DCAD is available ──────────────────────────────────────────

required = ['ACCOUNT_INFO.CSV', 'ACCOUNT_APPRL_YEAR.CSV', 'RES_DETAIL.CSV']
missing  = [f for f in required if not os.path.exists(os.path.join(DCAD_DIR, f))]
if missing:
    print("DCAD data not found. Download from dallascad.org/dataproducts.aspx")
    print("Extract into a folder called dcad_data/ in this project folder.")
    print(f"Missing: {missing}")
    print(f"\nRedfin data saved to redfin_{redfin_out}.csv")
    sys.exit()

# ── Step 4: filter DCAD ───────────────────────────────────────────────────────

print("Loading DCAD data...")
acct   = pd.read_csv(os.path.join(DCAD_DIR, 'ACCOUNT_INFO.CSV'), dtype=str)
apprl  = pd.read_csv(os.path.join(DCAD_DIR, 'ACCOUNT_APPRL_YEAR.CSV'), dtype=str)
res    = pd.read_csv(os.path.join(DCAD_DIR, 'RES_DETAIL.CSV'), dtype=str)

# Get zip codes from Redfin pull
redfin_zips = set(df_redfin['ZIP OR POSTAL CODE'].dropna().astype(str).str[:5].unique()) if 'ZIP OR POSTAL CODE' in df_redfin.columns else {'75229','75230'}

dcad = acct[
    (acct['DIVISION_CD'] == 'RES') &
    (acct['PROPERTY_ZIPCODE'].str[:5].isin(redfin_zips)) &
    (acct['FULL_STREET_NAME'].isin(streets_clean))
].copy()

dcad['STREET_NUM_INT'] = pd.to_numeric(dcad['STREET_NUM'], errors='coerce')
# Get street number range from Redfin addresses
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

print(f"DCAD candidates: {len(dcad)} — geocoding...")

# ── Step 5: geocode ───────────────────────────────────────────────────────────

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
geo[['LNG','LAT']] = geo['coords'].str.split(',', expand=True).astype(float)
geo['id'] = geo['id'].astype(str)
dcad.index = dcad.index.astype(str)
dcad = dcad.join(geo[['id','LAT','LNG']].set_index('id'), how='left')

dcad_box = dcad[
    (dcad['LAT'] >= MIN_LAT) & (dcad['LAT'] <= MAX_LAT) &
    (dcad['LNG'] >= MIN_LNG) & (dcad['LNG'] <= MAX_LNG)
].copy()
print(f"In bounding box after geocoding: {len(dcad_box)}")

# ── Step 6: join values, flag on/off market ───────────────────────────────────

dcad_box = dcad_box.merge(apprl[['ACCOUNT_NUM','LAND_VAL','IMPR_VAL','TOT_VAL']], on='ACCOUNT_NUM', how='left')
dcad_box = dcad_box.merge(res[['ACCOUNT_NUM','YR_BUILT','TOT_LIVING_AREA_SF']], on='ACCOUNT_NUM', how='left')
for col in ['LAND_VAL','IMPR_VAL','TOT_VAL','YR_BUILT','TOT_LIVING_AREA_SF','LAT','LNG']:
    dcad_box[col] = pd.to_numeric(dcad_box[col], errors='coerce')

dcad_box['PROPERTY_ADDRESS'] = (dcad_box['STREET_NUM'] + ' ' + dcad_box['FULL_STREET_NAME']).str.strip().str.upper()
dcad_box['LAND_PCT']  = (dcad_box['LAND_VAL'] / dcad_box['TOT_VAL'] * 100).round(1)
dcad_box['ON_REDFIN'] = dcad_box['PROPERTY_ADDRESS'].isin(redfin_addresses)

# ── Step 7: save CSV ──────────────────────────────────────────────────────────

out = dcad_box[['PROPERTY_ADDRESS','ON_REDFIN','OWNER_NAME1','OWNER_ADDRESS_LINE1',
                'OWNER_CITY','OWNER_STATE','OWNER_ZIPCODE',
                'LAND_VAL','IMPR_VAL','TOT_VAL','LAND_PCT','YR_BUILT','TOT_LIVING_AREA_SF','LAT','LNG']].copy()
out.columns = ['Property Address','Listed on Redfin','Owner Name','Owner Mailing Address',
               'Owner City','Owner State','Owner Zip',
               'Land Value','Improvement Value','Total Value','Land % of Total',
               'Year Built','Sq Ft','LAT','LNG']
out['Listed on Redfin'] = out['Listed on Redfin'].map({True:'YES', False:'NO'})
out = out.sort_values('Property Address')

csv_file = f'block_analysis_{redfin_out}.csv'
out.to_csv(csv_file, index=False)

on  = (out['Listed on Redfin']=='YES').sum()
off = (out['Listed on Redfin']=='NO').sum()
print(f"\nResults for {label}:")
print(f"  Listed on Redfin:  {on}")
print(f"  Off market:        {off}")
print(f"  Total:             {len(out)}")
print(f"\nSaved: {csv_file}")

# ── Step 8: build map ─────────────────────────────────────────────────────────

points = []
for _, row in out.dropna(subset=['LAT','LNG']).iterrows():
    points.append({
        'lat': row['LAT'], 'lng': row['LNG'],
        'on_redfin': row['Listed on Redfin'] == 'YES',
        'addr':  str(row['Property Address']),
        'owner': str(row['Owner Name']),
        'land_val': f"${row['Land Value']:,.0f}" if pd.notna(row['Land Value']) else 'N/A',
        'impr_val': f"${row['Improvement Value']:,.0f}" if pd.notna(row['Improvement Value']) else 'N/A',
        'tot_val':  f"${row['Total Value']:,.0f}"  if pd.notna(row['Total Value'])  else 'N/A',
        'land_pct': f"{row['Land % of Total']:.1f}%" if pd.notna(row['Land % of Total']) else 'N/A',
        'yr_built': str(int(row['Year Built'])) if pd.notna(row['Year Built']) and row['Year Built'] > 0 else 'N/A',
        'sqft':     f"{int(row['Sq Ft']):,}" if pd.notna(row['Sq Ft']) and row['Sq Ft'] > 0 else 'N/A',
    })

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
  .dot {{ display:inline-block; width:12px; height:12px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
</style>
</head><body><div id="map"></div>
<script>
const points = {json.dumps(points)};
const map = L.map('map').setView([{center_lat}, {center_lng}], 15);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution: '© OpenStreetMap contributors © CARTO'
}}).addTo(map);
points.forEach(p => {{
  const color = p.on_redfin ? '#e74c3c' : '#2980b9';
  const label = p.on_redfin ? 'LISTED ON REDFIN' : 'OFF MARKET';
  L.circleMarker([p.lat, p.lng], {{
    radius: p.on_redfin ? 9 : 6,
    fillColor: color, color: '#fff',
    weight: 2, opacity: 1, fillOpacity: 0.85
  }}).bindPopup(`<b>${{p.addr}}</b><br>
    <span style="color:${{color}};font-weight:bold">${{label}}</span><br><br>
    <b>Owner:</b> ${{p.owner}}<br>
    <b>Land Value:</b> ${{p.land_val}}<br>
    <b>Improvement Value:</b> ${{p.impr_val}}<br>
    <b>Total Value:</b> ${{p.tot_val}}<br>
    <b>Land % of Total:</b> ${{p.land_pct}}<br>
    <b>Year Built:</b> ${{p.yr_built}}<br>
    <b>Sq Ft:</b> ${{p.sqft}}`
  ).addTo(map);
}});
const legend = L.control({{position:'bottomright'}});
legend.onAdd = () => {{
  const d = L.DomUtil.create('div','legend');
  d.innerHTML = `<b>{label}</b><br><br>
    <span class="dot" style="background:#e74c3c"></span>Listed on Redfin ({on})<br>
    <span class="dot" style="background:#2980b9"></span>Off Market ({off})<br><br>
    Click any pin for details.`;
  return d;
}};
legend.addTo(map);
</script></body></html>"""

map_file = f'map_{redfin_out}.html'
with open(map_file, 'w') as f:
    f.write(html)
print(f"Map:   {map_file}")
print("\nDone.")
