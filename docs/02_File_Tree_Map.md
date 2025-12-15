# 🌳 File Tree Map

> **Snapshot Date:** 2025-12-15
> **Scope:** Critical Application Files

This map annotates the project structure to help agents navigate the codebase.

```text
TakeoAPP/
├── main.py                     # 🚀 Application Entry Point (MainWindow, App startup)
├── Takeo.py                    # 🛠️ Standalone/Legacy utility script (Check strict usage)
├── requirements.txt            # 📦 Python Dependencies (PyQt6, Pandas, OpenPyXL)
├── pubspec.yaml                # ⚠️ Trace of Flutter/Dart? (Likely irrelevant or misidentified in context, verify if active)
├── README.md                   # 📄 Setup instructions and feature list
│
├── docs/                       # 📂 Living Documentation (You are here)
│   ├── 00_Context_Bank_Index.md
│   ├── 01_Project_Manifest.md
│   └── 02_File_Tree_Map.md
│
└── guion_editor/               # 🧠 CORE PACKAGE: All application logic
    ├── constants.py            # 🔢 Global constants (Action names, columns, UI strings)
    ├── constants_logic.py      # 🔢 Logic-specific constants
    │
    ├── widgets/                # 🖼️ GUI Components (Views & Dialogs)
    │   ├── table_window.py     # ⭐ MAIN EDITOR: Grid view logic, data binding, shortcuts
    │   ├── video_player_widget.py # ⭐ VIDEO PLAYER: Media controls, sync logic
    │   ├── cast_window.py      # Character management UI
    │   ├── config_dialog.py    # Settings dialog (fonts, behavior)
    │   ├── takeo_dialog.py     # "Takeo" feature specific dialog
    │   ├── find_replace_dialog.py # Search/Replace functionality
    │   └── advanced_srt_export_dialog.py # Subtitle export logic
    │
    ├── models/                 # 💾 Logic / Data Layer
    │   └── [Likely PandasModel] # Qt AbstractItemModel wrapper for Pandas DataFrame
    │
    ├── delegates/              # 🎨 Custom Item Delegates
    │   └── [Renderers]         # Custom painting for Timecode cells, active rows, etc.
    │
    ├── utils/                  # 🔧 Helpers
    │   ├── guion_manager.py    # I/O Helper (Load/Save JSON/Excel)
    │   ├── shortcut_manager.py # Keyboard shortcut handling system
    │   └── paths.py            # Filesystem path resolvers (resource_path)
    │
    ├── styles/                 # 💅 Assets & Styling
    │   └── icons/              # SVG/PNG Icons used in the UI
    │
    └── commands/               # ⚡ Command Pattern
        └── [Undo/Redo]         # Likely QUndoCommand implementations for Script edits
```

## 🔍 Key Locations for Agents

- **Modifying the Grid/Editor:** `guion_editor/widgets/table_window.py` is the monolith controlling the main editing experience.
- **Modifying Video Behavior:** `guion_editor/widgets/video_player_widget.py`.
- **Data Structure Changes:** Check `guion_editor/models` first (to see how DataFrame is exposed) and `guion_editor/utils/guion_manager.py` (for serialization).
- **Adding Shortcuts:** `guion_editor/utils/shortcut_manager.py` + `main.py` entry.
