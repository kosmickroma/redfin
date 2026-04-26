# Redfin Teardown Finder

Automatically pulls active property listings from any Dallas neighborhood, groups
them by city block, and flags properties priced significantly below their neighbors —
the most likely teardown or undervalued candidates.

No manual searching. No drawing boxes on a map. Type a neighborhood name and it runs.

---

## What This Does (Plain English)

1. You type a neighborhood name like "Preston Hollow"
2. The script pulls every active listing Redfin shows for that area
3. It groups properties by city block
4. It calculates the median (middle) price for each block
5. Any property listed at less than 50% of its block's median gets flagged
6. Everything saves to a spreadsheet you can open in Excel

---

## Installation (Windows)

### Step 1 — Install Python

1. Go to **https://www.python.org/downloads/**
2. Click the big yellow **Download Python** button
3. Run the installer
4. **IMPORTANT:** On the first screen, check the box that says **"Add Python to PATH"** before clicking Install

To confirm it worked, open **Command Prompt** (search "cmd" in the Start menu) and type:
```
python --version
```
You should see something like `Python 3.12.x`. If you get an error, Python did not get added to PATH — re-run the installer and make sure that box is checked.

---

### Step 2 — Install Git

1. Go to **https://git-scm.com/download/win**
2. Download and run the installer
3. Click through the defaults — no changes needed

---

### Step 3 — Download the Code

Open **Command Prompt** and run:
```
git clone https://github.com/korykarp/redfin.git
```

Then move into the folder:
```
cd redfin
```

---

### Step 4 — Install Dependencies

Still in Command Prompt, run:
```
pip install requests pandas numpy
```

This downloads the three libraries the script needs. Should take under a minute.

---

### Step 5 — Run It

```
python redfin_tool.py
```

---

## How to Use It

When you run the script it will show you a menu:

```
Available Dallas neighborhoods:
  - Bishop Arts
  - Bluffview
  - Deep Ellum
  - Devonshire
  - Far North Dallas
  - Highland Park
  - Knox Henderson
  - Lake Highlands
  - Lakewood
  - Lower Greenville
  - M Streets
  - North Dallas
  - Oak Lawn
  - Preston Hollow
  - Turtle Creek
  - University Park
  - Uptown
  - White Rock Lake

How do you want to define the area?
  1 - Type a neighborhood name
  2 - Paste coordinates (min_lng, min_lat, max_lng, max_lat)

Choice (1 or 2):
```

**Option 1** — Just type the neighborhood name. Spelling doesn't have to be perfect.

**Option 2** — If you have a specific area not in the list, go to **bboxfinder.com**,
draw a rectangle on the map, and paste the 4 numbers it gives you.

The script will print progress as it runs, then save the results.

---

## Output

The script saves a file called **redfin_listings.csv** in the same folder you run it from.

Open it with Excel, Google Sheets, or LibreOffice Calc. It contains every active
listing Redfin shows for that neighborhood — one row per property, ready to work with.

Key columns:

| Column | What It Means |
|---|---|
| ADDRESS | Property street address |
| PRICE | Current list price |
| PROPERTY TYPE | Single family, condo, townhouse, etc. |
| BEDS / BATHS | Bedroom and bathroom count |
| SQUARE FEET | Interior square footage |
| LOT SIZE | Lot size in square feet |
| YEAR BUILT | Year the property was built |
| DAYS ON MARKET | How long it has been listed |
| URL | Direct link to the Redfin listing |
| LATITUDE / LONGITUDE | Exact coordinates of the property |

---

## How Long Does It Take?

| Neighborhood Size | Approx Time |
|---|---|
| Small (Uptown, Deep Ellum) | 30–60 seconds |
| Medium (Preston Hollow, Lakewood) | 2–3 minutes |
| Large (Lake Highlands, North Dallas) | 5–8 minutes |

---

## Important Limitations

**Redfin has no official public API.**
This tool uses Redfin's internal data endpoint — the same one their website uses
to load the map. It is not an officially supported connection. Redfin could change
it at any time, which would require an update to the script. It has been working
reliably but is not guaranteed.

**Active listings only.**
The tool pulls properties currently listed for sale. It does not include off-market
homes, recently sold comps, or unlisted properties.

**Block grouping is an approximation.**
Properties are grouped using a coordinate grid, not official city block boundaries.
In areas with curved or diagonal streets the grouping may not be perfectly precise.
Good enough for flagging candidates — not a final legal determination.

**Spot-check the output.**
The flagging is purely mathematical. Always verify flagged properties manually
before drawing conclusions. The tool finds candidates for human review — it does
not replace that review.

---

## Adding a New Neighborhood

Open `redfin_tool.py` in any text editor. Find the `DALLAS_NEIGHBORHOODS` section
near the top. Add a new line following the same format:

```python
"your neighborhood name": (min_lng, min_lat, max_lng, max_lat),
```

Get the coordinates from **bboxfinder.com** by drawing a rectangle around the area.

---

## How It Works (Technical)

Redfin does not offer a public API. Their website loads listing data by calling
an internal endpoint at `/stingray/api/gis-csv` with the coordinates of whatever
shape you draw on the map. This endpoint returns a CSV file with all listings
inside that shape.

By intercepting this request using the browser's built-in DevTools (F12 → Network tab),
we identified the URL format and all required parameters. The script replicates
those requests programmatically — looping through a grid of small boxes that cover
the target neighborhood, collecting all the data, deduplicating, and analyzing it.

No browser required. No logging into Redfin. No API key.
