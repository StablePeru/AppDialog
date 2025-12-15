# 🏗️ Project Manifest

> **Project Name:** AppDialog
> **Internal Codename:** Takeo / TakeoAPP
> **Version:** 1.0 (Inferred)

## 🎯 Business Purpose
**AppDialog** is a specialized desktop application for **Audiovisual Script Editing**, specifically tailored for Dubbing and Subtitling workflows. It replaces generic spreadsheet editors with a synchronized Video + Text environment.

**Key Capabilities:**
- **Synchronized Editing:** Edit script lines while watching the video frame-accurate.
- **Timecode Management:** Calculate durations, enforce IN/OUT constraints, and detect overlaps.
- **Format Interop:** Import/Export word processors (`.docx`), spreadsheets (`.xlsx`), and subtitle formats (`.srt`).
- **Character Management:** Track line counts and character occurrences.

## 💻 Tech Stack & Dependencies

### Core Runtime
- **Language:** Python 3.x
- **GUI Framework:** `PyQt6` (incorporating `PyQt6-Qt6`, `PyQt6-sip`)

### Data & Logic
- **Data Handling:** `pandas` (Heavy use for tabular script data backbone)
- **Math/Array:** `numpy`
- **Excel I/O:** `openpyxl`, `et_xmlfile`
- **Word I/O:** `python-docx`
- **Image/Assets:** `pillow`

### Build & Distribution
- **Packaging:** `pyinstaller` (Hooks present: `pyinstaller-hooks-contrib`)
- **System Integ:** `pywin32-ctypes`, `pefile`

## 🧩 Core Application Logic (Inferred)

1.  **Entry Point:** `main.py` initializes the `QApplication` and the main `MainWindow`.
2.  **Data Flow:**
    - The Script is loaded into a **Pandas DataFrame**.
    - This DataFrame is wrapped in a Custom Qt Model (`PandasModel` likely located in `guion_editor/models`).
    - The `TableWindow` widget displays this model.
    - Autosave logic serializes this DataFrame to JSON/Excel.
3.  **Video Integration:**
    - `VideoPlayerWidget` handles media playback.
    - Sync signals (`positionChanged`) trigger updates in the TableView to highlight active lines (karaoke style or scroll-sync).

## ⚠️ Critical Context
- **"Takeo" Feature:** "Takeo" refers to specific dialog optimization features. The legacy `Takeo.py` standalone script has been archived in `ZANTIGUO/` as its functionality is integrated into `main.py` and `guion_editor/`.
- **Legacy Isolation:** A `ZANTIGUO/` directory exists to hold deprecated files (`install.txt`, old docs) to keep the root clean without deleting history.
- **Code Organization:**
    - `guion_editor/constants.py`: UI-related constants (Colors, Geometries).
    - `guion_editor/constants_logic.py`: core logic constants (Regex, Timecode defaults, Table Column names).
    - **Filesystem:** The app interacts heavily with the local filesystem (`W:\Z_JSON\...`), implying it is part of a specific studio pipeline or workflow.
