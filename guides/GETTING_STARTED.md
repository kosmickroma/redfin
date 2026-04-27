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
```

**Mac:**
1. Open Terminal and run `git --version` — Mac will prompt you to install Git automatically if you don't have it
2. Then run:
```
git clone https://github.com/kosmickroma/redfin.git
```

**Linux:**
```
sudo apt install git
git clone https://github.com/kosmickroma/redfin.git
```

---

## Step 3 — Install dependencies

**Windows:** Open Command Prompt, navigate to the redfin folder, and run:
```
cd redfin
pip install -r requirements.txt
```

**Mac / Linux:** Open Terminal, navigate to the redfin folder, and run:
```
cd redfin
pip3 install -r requirements.txt
```

This installs three small libraries the script needs. Takes under a minute.

---

## Step 4 — Download Dallas County property data (one time)

This is the official county records database. It's free and public. You download it
once and it lives on your machine.

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
  run.bat
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

**Windows:** Double-click `run.bat` in the redfin folder. A terminal window will open automatically.

**Mac / Linux:** Open Terminal, navigate to the redfin folder, and run:
```
python3 analyze_block.py
```

The script will ask you two things:
1. Do you want to pick a neighborhood by name, or draw a custom area on Redfin?
2. What do you want to call this run? (This becomes the output filename)

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

Use this to analyze any specific block or shape you want.

1. Go to **redfin.com** and navigate to the area you want
2. Click the **draw tool** on the Redfin map and draw your shape
   - The draw tool is usually in the top-right corner of the map
   - Click around the area to draw — click back to the starting point to close the shape
3. Once your shape is drawn, press **F12** to open the browser developer tools
4. Click the **Network** tab and type `gis` in the filter box
5. Go back to the map and pan or move it slightly — this fires new requests that will appear in the list
6. Click any of the new requests that pop up
7. Right-click the URL at the top of the panel and select **Copy link address**
8. Switch back to the script window and press **Enter** — it reads the URL from your clipboard automatically, no pasting needed
9. Give your run a label (e.g. `highland_park_block1`) — this becomes the filename

The script extracts the coordinates automatically — you just paste the URL and go.

---

## What You Get

Two files are saved in the `output` folder inside redfin:

**Spreadsheet** (`block_analysis_[name].csv`)
Open in Excel or Google Sheets. One row per property:
- Who owns it and where they get their mail
- Land value, total value, land % of total
- Year built, square footage, zoning, school district, lot size, frontage, depth
- Whether it's listed on Redfin right now

**Map** (`map_[name].html`)
Double-click to open in any browser. Each property is outlined on the actual parcel.
- Red = listed on Redfin
- Blue = off market
- Click any parcel for owner info and values

---

## Sharing the Map

1. Go to [netlify.com/drop](https://netlify.com/drop)
2. Drag your `map_[name].html` file onto the page
3. You get a shareable link instantly — anyone can open it in their browser

A free Netlify account keeps the link permanent.

---

## Finding Teardown Candidates

In the spreadsheet, sort by **Land % of Total** from highest to lowest.

A property where land is 80–90%+ of the total value means the land is worth
far more than the building on top of it. Pair that with an old **Year Built** and
you have a strong candidate — an owner who may not know anyone is looking.

Filter **Listed on Redfin** to `NO` to see only off-market properties.
Every one of those rows has the owner name and mailing address.
