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

## Step 1 — Set up your terminal

**Windows — install WSL (Ubuntu terminal, one time):**
1. Click the Start menu, search for **PowerShell**, right-click it and select **Run as Administrator**
2. Run this command:
```
wsl --install
```
3. Restart your computer when prompted
4. After restart, open **Ubuntu** from the Start menu — it will finish setting up and ask you to create a username and password
5. That Ubuntu window is your terminal — use it for all the steps below
6. From now on, any time you want to run the script just open the Start menu, search **Ubuntu**, and click it

**Mac:** Open **Terminal** (search for it in Spotlight)

**Linux:** Open your terminal

---

## Step 2 — Install Python and Git

In your terminal run:
```
sudo apt update && sudo apt install python3 python3-pip git
```

---

## Step 3 — Download the script

```
git clone https://github.com/kosmickroma/redfin.git
cd redfin
```

---

## Step 4 — Install dependencies

```
pip3 install -r requirements.txt
```

This installs three small libraries. Takes under a minute.

---

## Step 5 — Download Dallas County property data (one time)

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

## Step 6 — Download the parcel map data (one time)

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

## Step 7 — Run it

In your terminal (Ubuntu on Windows, Terminal on Mac/Linux):
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
8. **Save the URL to a file called `redfin_url.txt`** in the redfin folder
   - Windows: Right-click in the folder, New > Text Document, paste the URL, save as `redfin_url.txt`
   - Mac/Linux: Use any text editor, paste URL, save as `redfin_url.txt` in the redfin folder
9. Switch back to the script, press **Enter** when prompted
10. Give your run a label (e.g. `highland_park_block1`) — this becomes the filename

The script reads the URL from the file and extracts the coordinates automatically. This avoids Windows terminal issues with special characters in URLs.

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
