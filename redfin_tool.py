import requests
import pandas as pd
import numpy as np
import io
import time
import difflib

# min_lng, min_lat, max_lng, max_lat
DALLAS_NEIGHBORHOODS = {
    "preston hollow":    (-96.836, 32.879, -96.753, 32.894),
    "highland park":     (-96.819, 32.817, -96.779, 32.844),
    "university park":   (-96.803, 32.843, -96.779, 32.863),
    "uptown":            (-96.814, 32.788, -96.790, 32.815),
    "oak lawn":          (-96.822, 32.793, -96.798, 32.820),
    "bluffview":         (-96.845, 32.852, -96.815, 32.878),
    "lakewood":          (-96.765, 32.793, -96.724, 32.830),
    "m streets":         (-96.782, 32.818, -96.758, 32.842),
    "lake highlands":    (-96.740, 32.860, -96.690, 32.920),
    "turtle creek":      (-96.822, 32.812, -96.800, 32.835),
    "knox henderson":    (-96.800, 32.815, -96.780, 32.835),
    "lower greenville":  (-96.778, 32.800, -96.760, 32.820),
    "devonshire":        (-96.832, 32.862, -96.808, 32.878),
    "north dallas":      (-96.820, 32.900, -96.750, 32.950),
    "far north dallas":  (-96.830, 32.940, -96.750, 33.000),
    "white rock lake":   (-96.733, 32.820, -96.704, 32.848),
    "deep ellum":        (-96.789, 32.782, -96.773, 32.793),
    "bishop arts":       (-96.838, 32.738, -96.820, 32.755),
}

def find_neighborhood(name):
    """Fuzzy match a neighborhood name against the built-in Dallas list."""
    key = name.lower().strip()
    if key in DALLAS_NEIGHBORHOODS:
        return key, DALLAS_NEIGHBORHOODS[key]
    matches = difflib.get_close_matches(key, DALLAS_NEIGHBORHOODS.keys(), n=1, cutoff=0.5)
    if matches:
        return matches[0], DALLAS_NEIGHBORHOODS[matches[0]]
    return None, None

def make_session():
    """Start a session and grab cookies from Redfin so requests don't get blocked."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.redfin.com/city/30794/TX/Dallas',
    })
    session.get('https://www.redfin.com/city/30794/TX/Dallas', timeout=15)
    return session

def fetch_cell(session, min_lng, min_lat, max_lng, max_lat):
    """Pull one grid cell from Redfin. Returns a DataFrame or None."""
    poly = (
        f"{min_lng} {min_lat},"
        f"{max_lng} {min_lat},"
        f"{max_lng} {max_lat},"
        f"{min_lng} {max_lat},"
        f"{min_lng} {min_lat}"
    )
    params = {
        'al': '1', 'market': 'dallas', 'mpt': '99',
        'num_homes': '350', 'sf': '1,2,3,5,6,7',
        'start': '0', 'status': '1',
        'uipt': '1,2,3,4,5,6,7', 'v': '8',
        'poly': poly,
    }
    r = session.get('https://www.redfin.com/stingray/api/gis-csv', params=params, timeout=15)
    if r.status_code == 200 and len(r.text) > 200:
        return pd.read_csv(io.StringIO(r.text))
    return None

def pull_grid(min_lng, min_lat, max_lng, max_lat, cell_size=0.003):
    """
    Pull all properties in a neighborhood by looping a grid of small boxes.
    cell_size ~0.003 degrees ≈ 2-3 city blocks. Tune smaller for denser areas.
    """
    session = make_session()
    lngs = np.arange(min_lng, max_lng, cell_size)
    lats = np.arange(min_lat, max_lat, cell_size)
    total = len(lngs) * len(lats)
    print(f"Pulling {total} grid cells over {round((max_lng-min_lng)*(max_lat-min_lat)*10000,1)} sq blocks...")

    all_dfs = []
    count = 0
    for i, lng in enumerate(lngs):
        for j, lat in enumerate(lats):
            count += 1
            c_max_lng = min(lng + cell_size, max_lng)
            c_max_lat = min(lat + cell_size, max_lat)

            try:
                df = fetch_cell(session, lng, lat, c_max_lng, c_max_lat)
                if df is not None and not df.empty:
                    df['block_id'] = f"B{i}_{j}"
                    all_dfs.append(df)
                    print(f"  [{count}/{total}] cell {i},{j} → {len(df)} props")
                else:
                    print(f"  [{count}/{total}] cell {i},{j} → empty")
            except Exception as e:
                print(f"  [{count}/{total}] cell {i},{j} → error: {e}")

            time.sleep(0.5)

    if not all_dfs:
        print("No data returned.")
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    if 'ADDRESS' in combined.columns:
        combined = combined.drop_duplicates(subset=['ADDRESS'])
    elif 'Address' in combined.columns:
        combined = combined.drop_duplicates(subset=['Address'])

    print(f"\nTotal unique properties: {len(combined)}")
    return combined

if __name__ == '__main__':
    print("Available Dallas neighborhoods:")
    for n in sorted(DALLAS_NEIGHBORHOODS.keys()):
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
            print("Couldn't parse those — make sure it's 4 numbers separated by commas.")
            exit()
    else:
        name = input("\nNeighborhood name: ").strip()
        matched, coords = find_neighborhood(name)
        if not coords:
            print(f"Couldn't find '{name}' in the list. Use option 2 to paste coordinates manually.")
            exit()
        if matched != name.lower().strip():
            print(f"Matched to: '{matched.title()}'")
        MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT = coords
    print()

    df = pull_grid(MIN_LNG, MIN_LAT, MAX_LNG, MAX_LAT)
    if df.empty:
        exit()

    # drop the internal block_id column — not needed in the output
    df = df.drop(columns=['block_id'], errors='ignore')

    output = 'redfin_listings.csv'
    df.to_csv(output, index=False)
    print(f"\nDone. {len(df)} properties saved to {output}")
