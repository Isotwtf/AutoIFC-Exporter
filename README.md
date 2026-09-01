# AutoIFC

A pyRevit extension for isolating Revit categories into their own 3D
views and batch-exporting them to individual IFC files — built for
Digital Twin / Omniverse pipelines where each category needs to arrive
as a separate, clean IFC.

Two tools, both on the **Export** tab in Revit's ribbon:

- **Create Views by Category** (Views panel)
- **Export IFC by Category** (IFC panel)

---

## What it does

### Create Views by Category

Generates one isolated 3D view per selected Revit category (Ducts,
Duct Fittings, Electrical Equipment, etc.). Each view shows only that
category's elements — everything else, including linked models, is
hidden. Views are named `Omniverse_<Category>` so the export tool can
find them automatically.

The category picker only lists categories that actually have elements
placed in the current model (not Revit's full ~300 built-in category
list), and filters out administrative/non-physical categories (Sheets,
Project Information, Materials, RVT Links, Rooms, Areas, etc.) that
don't belong in an isolated 3D view.

### Export IFC by Category

Batch-exports every generated `Omniverse_*` view to its own IFC file —
one file per category, named after the category (e.g. `Ducts.ifc`).
Re-running the export overwrites the same file rather than creating
duplicates, so it's safe to re-run as the model changes.

The export setup itself is configured through **Revit's own native
"Modify Setup" editor** (Category Mapping, Property Mapping, Level of
Detail, Geographic Reference — the exact same dialog behind File >
Export > IFC), so you get full control without a separate settings
system to learn. Failures on individual categories don't stop the
batch, and a summary report (on-screen table + CSV saved next to the
exported files, in `_ExportReports/`) shows category, file name,
success/failure, and duration for every export.

---

## Requirements

- **Autodesk Revit** — developed and tested against Revit 2027.2, but
  built to degrade gracefully on other recent versions (some IFC
  Export Setup detection is version-dependent; see notes below).
- **pyRevit** — the extension is a set of pyRevit pushbuttons, so
  pyRevit must be installed first. Get it from:
  - https://pyrevitlabs.io (installer)
  - or https://github.com/pyrevitlabs/pyRevit (source / releases)

  Install pyRevit, open Revit once so it loads, and confirm you see a
  **pyRevit** tab in the ribbon before continuing.
- To read your project's own named IFC Export Setups (not just the
  generic built-in list), Revit's native IFC exporter component needs
  to be loaded into memory at least once per session — see
  [Troubleshooting](#troubleshooting) below.

---

## Installation

1. **Install pyRevit** (see Requirements above) if you haven't already.

2. **Clone this repository** somewhere permanent on your machine (not
   a temp folder):

   ```
   git clone https://github.com/Isotwtf/AutoIFC-Exporter.git
   ```

3. **Add it to pyRevit**:
   - Open Revit, go to the **pyRevit** tab → **Settings**.
   - Under **Custom Extension Directories**, click **Add folder**.
   - Select the **parent folder** that *contains* the cloned
     `AutoIFC-Exporter` folder — not the folder itself. pyRevit scans
     a directory for subfolders ending in `.extension`; pointing it at
     the extension folder directly means it finds nothing.
   - Click **Save Settings and Reload**.

4. You should now see an **Export** tab in Revit's ribbon with **Views**
   and **IFC** panels.

### Getting updates later

```
cd AutoIFC-Exporter
git pull
```
Then reload pyRevit (pyRevit tab → Reload, or just restart Revit).

---

## Usage

1. Run **Create Views by Category**, pick the categories you want
   (search box + checklist, all populated categories pre-checked),
   click **Create Views**.
2. Run **Export IFC by Category**. Pick which generated categories to
   export, click **Configure Settings...** to review/tune the IFC
   export setup in Revit's native editor, choose an output folder,
   then **Export Selected**.
3. Check the summary table and the CSV report in `_ExportReports/`
   inside your output folder.

---

## Troubleshooting

**"Only generic IFC versions are shown, not my project's real
setups."** Revit only loads the component that stores named IFC
Export Setups into memory the first time its own **File > Export >
IFC** dialog runs in a session. Open that dialog once (you can Cancel
out, no need to actually export), then reopen this tool.

**A custom setup I made in another project doesn't show up here.**
IFC Export Setups are saved per Revit file, the same as Revit's own
dialog. To move one between projects: in the source file's Modify
Setup editor, select the setup and click the **Export** icon (bottom
of the setup list) to save it as a file, then in the target file click
**Import** and pick that file.

**An element I expect to see is missing from the exported IFC.**
Check which IFC version the setup uses. IFC4/IFC4.3 apply much
stricter geometry validation than IFC2x3, and Revit's exporter will
silently skip an element whose geometry doesn't pass validation
(curved/swept solids, like duct elbows, are the most common case) —
this is a Revit exporter limitation, not specific to this tool. Try a
less strict schema, or check the "Advanced" tab in Modify Setup for
tessellation/geometry options. Built-in setups (anything named
`<...>`) are read-only in the editor — use the **Duplicate** icon to
make an editable copy first if you need to change one.

---

## Project structure

```
AutoIFC-Exporter/
├── Export.tab/
│   ├── Views.panel/
│   │   └── Create Views by Category.pushbutton/
│   └── IFC.panel/
│       └── Export IFC by Category.pushbutton/
└── lib/dt_common/          # shared library (Revit API, IFC export, UI)
    └── ui/                 # custom WPF windows for both tools
```

---

Built by Jayson Allosada.
