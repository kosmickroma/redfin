# Redfin Teardown Finder — POC Briefing

## The Short Version

This tool automatically pulls active property listings from a Dallas neighborhood,
groups them by city block, and flags any property priced way below its neighbors —
the likely teardown candidates. No manual searching, no drawing boxes on a map.

---

## Does Redfin Have an Official API?

**No.** Redfin has never published a public API or developer portal. They aggregate
data from thousands of MLS (Multiple Listing Service) systems across the country,
and the licensing agreements on that data prevent them from redistributing it
programmatically to outside developers.

Every third-party "Redfin API" you'll find online is either a paid scraping service
(like Oxylabs or ScrapingBee) that works around this, or an unofficial wrapper
someone built by reverse-engineering how Redfin's own website works internally.

---

## The Technique We Used

Every map-based website works the same way under the hood:

1. Your browser loads the page
2. The page makes an HTTP request to a backend server asking for data
3. The server sends back the data (usually JSON or CSV)
4. The browser draws it on the map

Redfin's map uses an internal endpoint called `/stingray/api/gis` to load listings.
When you draw a shape on their map, it sends the coordinates of that shape to this
endpoint and gets back all the properties inside it.

There is a variant of this endpoint — `/stingray/api/gis-csv` — that returns the
exact same data as a downloadable CSV file instead of JSON. By intercepting this
request in the browser's DevTools Network tab, we were able to reverse-engineer
the URL format, including all the required parameters.

From there, we built a script that hits this endpoint programmatically — no browser,
no drawing, no manual steps.

---

## How the Tool Works

```
1. You type a neighborhood name (e.g. "Preston Hollow")
2. The script looks up the geographic bounding box for that neighborhood
3. It divides that box into a grid of small cells (~2-3 blocks each)
4. For each cell, it hits the Redfin endpoint and collects all listed properties
5. Properties are tagged with which grid cell (block area) they landed in
6. It calculates the median price for each block group
7. Any property below 50% of its block median is flagged as a teardown candidate
8. Everything is saved to teardown_candidates.csv
```

---

## Limitations (Be Upfront About These)

**1. This endpoint is not official.**
Redfin could change it at any time without notice. If the script suddenly stops
working, that's likely why. Not hard to fix, but it would require re-intercepting
the endpoint to see what changed.

**2. The 350 property cap per cell.**
Each request to Redfin returns a maximum of 350 listings. In very dense areas,
some properties may be missed. Shrinking the grid cell size fixes this but means
more requests and slower runs.

**3. Block grouping is approximate.**
We're using a coordinate grid, not actual city block boundaries. Properties near
the edge of a cell might be compared to neighbors one block over. For a POC this
is fine — a full implementation could use Census Bureau TIGER/Line block shapefiles
for exact boundaries.

**4. Active listings only.**
The endpoint returns currently listed properties. It does not include off-market
homes, recently sold comps, or unlisted properties. A more complete picture would
require cross-referencing with sold data.

**5. Spot-check the output.**
The flagging logic is purely mathematical (price vs. block median). It will
occasionally flag a legitimate lower-priced home in a transitional area. The output
should be treated as a shortlist for human review, not a final answer.

---

## Setup Instructions (HP Laptop / Windows)

### Step 1 — Install Python
Go to python.org and download Python 3.12 or newer. During install, check the box
that says "Add Python to PATH".

### Step 2 — Get the code
```
git clone https://github.com/YOUR_USERNAME/redfin-teardown-finder.git
cd redfin-teardown-finder
```

### Step 3 — Install dependencies
Open a terminal (Command Prompt or PowerShell) and run:
```
pip install requests pandas numpy
```

### Step 4 — Run it
```
python redfin_tool.py
```

Then follow the prompts — type a neighborhood name or paste coordinates.

---

## Available Dallas Neighborhoods (Built In)

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

---

## Output File

`teardown_candidates.csv` — saved in the same folder you run the script from.

Key columns:
- **ADDRESS** — property address
- **PRICE** — listed price
- **block_median** — median price of surrounding properties in the same block group
- **price_ratio** — listed price divided by block median (lower = more of an outlier)
- **teardown_flag** — TRUE if price_ratio is below 0.5 (below 50% of block median)

File is sorted by price_ratio ascending, so the biggest outliers are at the top.
