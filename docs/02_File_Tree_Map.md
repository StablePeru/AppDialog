# 📂 Project File Tree Map

This document provides an annotated view of the project structure as of the latest update.

## 📦 Root Directory: `TakeoAPP/`
| File / Directory | Description |
| :--- | :--- |
| `main.py` | **Entry Point**. Initializes QApplication, styles, and MainWindow. |
| `requirements.txt` | Dependencies list (PyQt6, pandas, openpyxl, etc.). |
| `setup.py` | Build configuration for PyInstaller/Distribution. |
| `pytest.ini` | Configuration for pytest. |
| `README.md` | Standard Github README (User-facing generic info). |
| `LICENSE.md` | License info. |
| `.gitignore` | Git ignore rules (includes `ZANTIGUO/`). |
| `ZANTIGUO/` | **Archive**. Contains legacy/unused files (`Takeo.py`, `install.txt`, etc.). |
| `docs/` | **Living Documentation System**. |
| `guion_editor/` | **Core Package**. Contains all application logic. |

---

## 🏗️ Core Package: `guion_editor/`

### 🔹 Logic & Constants
| File | Description |
| :--- | :--- |
| `constants.py` | **UI Constants**. Colors, dimensions, font sizes. |
| `constants_logic.py` | **Logic Constants**. Regex patterns, Column Names, Timecode defaults. |
| `shortcuts.json` | JSON mapping for keyboard shortcuts. |

### 🔹 Models (Data Layer)
| File | Description |
| :--- | :--- |
| `models/pandas_table_model.py` | **Core Data Model**. Wraps Pandas DataFrame for Qt TableView. Handles validation. |

### 🔹 Widgets (UI Layer)
| File | Description |
| :--- | :--- |
| `widgets/table_window.py` | **Main Editor**. The central spreadsheet-like view. Logic for row ops, regex cleaning. |
| `widgets/video_player_widget.py` | **Video Player**. Handles playback and timecode sync using `C.FPS`. |
| `widgets/takeo_dialog.py` | **Takeo Tool**. Dialog optimization utility (integrated from legacy `Takeo.py`). |
| `widgets/time_code_edit.py` | Custom widget for TimeCode entry. |
| `widgets/waveform_widget.py` | Audio visualization widget. |

### 🔹 Utilities
| File | Description |
| :--- | :--- |
| `utils/dialog_utils.py` | string manipulation, timecode math. |
| `commands/undo_commands.py` | **Undo/Redo Logic**. Implements `QUndoCommand` for all table operations. |

---

## 📜 Documentation: `docs/`
| File | Description |
| :--- | :--- |
| `00_Context_Bank_Index.md` | Master Index of this documentation. |
| `01_Project_Manifest.md` | High-level summary, tech stack, and business purpose. |
| `02_File_Tree_Map.md` | **(This File)**. Map of the codebase. |

> **Note:** Files inside `ZANTIGUO/` are not documented here as they are considered archived.
