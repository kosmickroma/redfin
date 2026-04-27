# Dallas Off-Market Property Finder

Pulls every active listing from Redfin for any area in Dallas and cross-references
it against Dallas County Appraisal District (DCAD) records — which cover **every
property that exists**, not just the ones for sale. The output tells you who owns
each property, what it's worth, and whether it's listed anywhere.

---

## Running It

First, open a terminal in the `redfin` folder:
- **Windows:** Open Command Prompt, then type `cd C:\path\to\redfin` (wherever you cloned it)
- **Mac / Linux:** Open Terminal, then type `cd ~/redfin` (or wherever you cloned it)

Then run:

**Windows (Ubuntu/WSL terminal) / Mac / Linux:**
```
python3 analyze_block.py
```

---

## How to Pick Your Area

The script gives you two options:

**Option 1 — Neighborhood name**

Type `1` and enter a neighborhood. Built-in neighborhoods include:

```
Bishop Arts       Bluffview         Deep Ellum
Devonshire        Far North Dallas  Highland Park
Knox Henderson    Lake Highlands    Lakewood
Lower Greenville  M Streets         North Dallas
Oak Lawn          Preston Hollow    Turtle Creek
University Park   Uptown            White Rock Lake
```

Spelling doesn't need to be exact — it will fuzzy-match.

**Option 2 — Custom area from Redfin**

Use this to analyze any specific block or custom shape:

1. Go to **redfin.com** and navigate to the area you want
2. Click the **draw tool** on the Redfin map and draw your shape
3. Once your shape is drawn, press **F12** to open DevTools
4. Click the **Network** tab and type `gis` in the filter box
5. Click the most recent request that appears in the list
6. **Right-click the full URL** at the top of the panel and copy it
7. **Save the URL to a text file called `redfin_url.txt`** in the same folder as the script
   - Windows: Right-click in the redfin folder, New > Text Document, paste URL, save as `redfin_url.txt`
   - Mac/Linux: Use any text editor, paste the URL, save as `redfin_url.txt`
8. Back in the script, type `2` and press Enter

The script reads the URL from the file automatically — this avoids Windows terminal issues with special characters.

---

## Output Files

Each run saves files in the `output/` folder:

| File | What It Is |
|---|---|
| `block_analysis_[label].csv` | Full spreadsheet — open in Excel or Google Sheets |
| `map_[label].html` | Interactive map — open in any browser |

---

## Reading the Output

**To find teardown candidates:** Sort by **Land % of Total** descending.
A property where land is 70–90%+ of the total value means the land is worth
far more than the structure sitting on it. Combined with an old Year Built,
that's the owner to call.

**On/Off market:** Filter **Listed on Redfin** to `NO` to see only off-market
properties — these are owners who aren't selling publicly and may not know
anyone is looking.

**Google Maps Link:** Click to open the property in Google Maps for a quick
visual check of the lot, neighborhood context, and street view.

**Sharing the map:** Drag the `map_[label].html` file to [netlify.com/drop](https://netlify.com/drop)
to get a shareable link anyone can open in their browser.

---

## What You Get

A spreadsheet with one row per property in your target area:

| Column | What It Is |
|---|---|
| Property Address | Street address |
| Listed on Redfin | YES = active listing / NO = off market |
| Owner Name | Who owns it |
| Owner Mailing Address | Where to send a letter |
| Owner City / State / Zip | Owner's mailing location |
| Land Value | County appraisal — land only |
| Improvement Value | County appraisal — structure only |
| Total Value | Combined county appraisal |
| Land % of Total | Key teardown signal — higher = more valuable as land than as structure |
| Year Built | Age of structure |
| Living Area (sq ft) | Interior square footage |
| Total Structure Area (sq ft) | Full structure footprint |
| State Code | Property type (e.g. Single Family Residences) |
| Zoning | How the parcel is zoned |
| Lot Size (sq ft) | Total lot area |
| Frontage (ft) | Street frontage |
| Depth (ft) | Lot depth |
| School District | ISD serving the property |
| Neighborhood Code | DCAD neighborhood classification |
| Subdivision | Subdivision name |
| Legal Description | Full legal description from county records |
| Google Maps Link | One click to view the property in Google Maps |

The interactive map shows every property outlined on the actual parcel.
Red = listed on Redfin. Blue = off market. Click any parcel for details.

---

## How Long Does It Take?

| Step | Time |
|---|---|
| Loading parcel shapefile | 10–20 seconds (first time each run) |
| Redfin pull (small area) | 30–60 seconds |
| Redfin pull (full neighborhood) | 2–4 minutes |
| DCAD join and output | A few seconds |

---

## Installation

### Step 1 — Install Python

**Windows:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click **Download Python**
3. Run the installer — on the first screen, check **"Add Python to PATH"** before clicking Install
4. Verify: open Command Prompt and run `python --version`

**Mac:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download and run the installer
3. Verify: open Terminal and run `python3 --version`

**Linux:**
```bash
sudo apt install python3 python3-pip
```

---

### Step 2 — Download the code

Open a terminal and run:

```
git clone https://github.com/kosmickroma/redfin.git
cd redfin
```

If you don't have Git installed:
- **Windows:** [git-scm.com/download/win](https://git-scm.com/download/win) — run installer, click through defaults
- **Mac:** Run `git --version` in Terminal — Mac will prompt you to install it automatically
- **Linux:** `sudo apt install git`

---

### Step 3 — Install dependencies

Inside the `redfin` folder, run:

**Windows:**
```
pip install -r requirements.txt
```

**Mac / Linux:**
```
pip3 install -r requirements.txt
```

This installs three libraries: `requests`, `pandas`, and `numpy`. Takes under a minute.

---

### Step 4 — Download DCAD data (one time)

This is the Dallas County property records database. You download it once and it
stays on your machine. DCAD updates it annually.

1. Go to [dallascad.org/dataproducts.aspx](https://dallascad.org/dataproducts.aspx)
2. Download **2026 Data Files with Proposed Values (Res and Com)**
3. Extract the ZIP — you need these files:
   - `ACCOUNT_INFO.CSV`
   - `ACCOUNT_APPRL_YEAR.CSV`
   - `RES_DETAIL.CSV`
   - `LAND.CSV`
4. Place them in a folder called `dcad_data` inside the `redfin` folder

---

### Step 5 — Download DCAD parcel shapefile (one time)

This gives every property its exact GPS location on the map.

1. Go to [dallascad.org/dataproducts.aspx](https://dallascad.org/dataproducts.aspx)
2. Click **GIS Data Products** in the left navigation
3. Download **Current 2026 Parcels** (the file is called `PARCEL_GEOM.zip`)
4. Extract into `dcad_data/PARCEL_GEOM/` — you should have `PARCEL_GEOM.shp` inside that folder

---

### Your folder should look like this

```
redfin/
  analyze_block.py
  redfin_tool.py
  requirements.txt
  README.md
  dcad_data/
    ACCOUNT_INFO.CSV
    ACCOUNT_APPRL_YEAR.CSV
    RES_DETAIL.CSV
    LAND.CSV
    PARCEL_GEOM/
      PARCEL_GEOM.shp
      PARCEL_GEOM.dbf
      PARCEL_GEOM.shx
      PARCEL_GEOM.prj
```

---

## Data Sources

| Source | What It Provides | How Current |
|---|---|---|
| Redfin | Active listings, list price, beds/baths/sqft | Live |
| DCAD | All properties, owner info, appraisal values | Updated annually |

---

## Notes

- Redfin has no public API. This tool uses their internal data endpoint — the same
  one their website uses. It has worked reliably but is not officially supported.
- DCAD data updates once per year. Download the new version each spring when DCAD
  releases it (typically April).
- Condos and units will show zero frontage and depth — DCAD does not track
  individual unit dimensions. This is expected.
