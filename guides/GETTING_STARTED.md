# Getting Started

This tool pulls every property in any Dallas neighborhood and tells you who owns it,
what it's worth, and whether it's listed for sale — including all the ones that aren't.
The output is a spreadsheet and an interactive map.

---

## What You Need Before You Start

1. A computer running Windows, Mac, or Linux
2. An internet connection
3. The Dallas County property data files (free download — instructions below)

---

## Step 1 — Install Python

Python is the program that runs the script. You only do this once.

**Windows:**
1. Go to [python.org/downloads](https://python.org/downloads)
2. Click the big yellow Download button
3. Run the installer — **on the very first screen, check the box that says "Add Python to PATH"** before you click anything else. This is easy to miss.
4. Click Install Now and let it finish
5. To verify: open the Start menu, search for **Command Prompt**, open it, and type `python --version` — you should see a version number

**Mac:**
1. Go to [python.org/downloads](https://python.org/downloads)
2. Download and run the installer
3. To verify: open **Terminal** (search for it in Spotlight) and type `python3 --version`

**Linux:**
```
sudo apt install python3 python3-pip
```

---

## Step 2 — Download the script

**Windows:**
1. Go to [git-scm.com/download/win](https://git-scm.com/download/win), download and run the installer, click through all the defaults
2. Open Command Prompt and run:
```
git clone https://github.com/kosmickroma/redfin.git
cd redfin
```

**Mac:**
1. Open Terminal and run `git --version` — Mac will prompt you to install Git automatically if you don't have it
2. Then run:
```
git clone https://github.com/kosmickroma/redfin.git
cd redfin
```

**Linux:**
```
sudo apt install git
git clone https://github.com/kosmickroma/redfin.git
cd redfin
```

---

## Step 3 — Install dependencies

Inside the redfin folder, run this one command:

**Windows:**
```
pip install -r requirements.txt
```

**Mac / Linux:**
```
pip3 install -r requirements.txt
```

This installs three small libraries the script needs. Takes under a minute.

---

## Step 4 — Download Dallas County property data (one time)

This is the official county records database. It's free and public. You download it
once and it lives on your machine — the script reads it locally, no internet needed.

1. Go to [dallascad.org/dataproducts.aspx](https://dallascad.org/dataproducts.aspx)
2. Download **2026 Data Files with Proposed Values (Res and Com)**
3. Extract the ZIP file
4. Create a folder called `dcad_data` inside the `redfin` folder
5. Move these four files into `dcad_data`:
   - `ACCOUNT_INFO.CSV`
   - `ACCOUNT_APPRL_YEAR.CSV`
   - `RES_DETAIL.CSV`
   - `LAND.CSV`

---

## Step 5 — Download the parcel map data (one time)

This gives every property its exact location on the map so pins land on the actual lot.

1. Go to [dallascad.org/dataproducts.aspx](https://dallascad.org/dataproducts.aspx)
2. Click **GIS Data Products** in the left navigation
3. Download **Current 2026 Parcels** (`PARCEL_GEOM.zip`)
4. Inside `dcad_data`, create a folder called `PARCEL_GEOM`
5. Extract the ZIP into that folder — you should have `PARCEL_GEOM.shp` inside it

---

## Your folder should look like this

```
redfin/
  analyze_block.py
  redfin_tool.py
  requirements.txt
  README.md
  guides/
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
  output/
```

---

## Step 6 — Run it

Open Command Prompt (Windows) or Terminal (Mac/Linux), navigate to the redfin folder, and run:

**Windows:**
```
python analyze_block.py
```

**Mac / Linux:**
```
python3 analyze_block.py
```

The script will ask you two questions:
1. Do you want to pick a neighborhood by name, or paste coordinates from Redfin?
2. What do you want to call this run? (This becomes the filename)

---

## Picking Your Area

**Option 1 — Type a neighborhood name**

Type `1` and enter the name. Built-in neighborhoods:

```
Bishop Arts       Bluffview         Deep Ellum
Devonshire        Far North Dallas  Highland Park
Knox Henderson    Lake Highlands    Lakewood
Lower Greenville  M Streets         North Dallas
Oak Lawn          Preston Hollow    Turtle Creek
University Park   Uptown            White Rock Lake
```

Spelling doesn't need to be exact — it will find the closest match.

**Option 2 — Draw a custom area on Redfin**

Use this to analyze any specific block or custom shape:

1. Go to **redfin.com** and navigate to the area you want to analyze
2. Press **F12** on your keyboard to open the browser developer tools
3. Click the **Network** tab along the top of the developer tools panel
4. In the filter box, type **`gis`** — this filters out everything except the map data requests
5. On the Redfin map, click the **draw tool** (looks like a pencil or polygon icon, usually in the top-right of the map)
6. Draw your shape by clicking around the area — click back to the start to close the shape
7. A request will appear in the Network tab — click on it
8. **Right-click the full URL** at the top of the panel and copy the entire thing
9. Back in the script, type `2`, paste the full URL when prompted, and give your run a label

The script pulls the coordinates out of the URL automatically — you just paste and go.

---

## What You Get

Two files are saved in the `output` folder:

**Spreadsheet** (`block_analysis_[name].csv`)
Open in Excel or Google Sheets. One row per property with:
- Who owns it and where they get their mail
- What the county says it's worth (land vs. structure)
- Year built, square footage, zoning, school district
- Whether it's listed on Redfin right now

**Map** (`map_[name].html`)
Double-click to open in any browser. Each property is outlined on the map.
- Red = listed on Redfin
- Blue = off market

Click any property outline for owner info and values.

---

## Sharing the Map

The map file opens in any browser. To share it with someone else:

1. Go to [netlify.com/drop](https://netlify.com/drop)
2. Drag your `map_[name].html` file onto the page
3. You get a link instantly — share it with anyone

A free Netlify account keeps the link permanent.

---

## Finding Teardown Candidates

In the spreadsheet, sort by **Land % of Total** from highest to lowest.

A property where land is 80–90%+ of the total value means the land itself is worth
far more than the building sitting on it. Pair that with an old **Year Built** and
you have a strong teardown candidate — an owner who may not know anyone is looking.

Filter **Listed on Redfin** to `NO` to see only off-market properties.
Every one of those rows has the owner name and mailing address.
