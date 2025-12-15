# 🏗️ Architecture Patterns

> **Status:** Draft | **Updated:** 2025-12-15
> **Scope:** Core Application Logic

## 📐 High-Level Architecture
AppDialog follows a **Model-View-Delegate (Qt Standard)** architecture, heavily adapted for Data Science-like table manipulation using Pandas.

### 1. The Core Loop
The application essentially wraps a **Pandas DataFrame** in a GUI.
- **State:** The Single Source of Truth is the `DataFrame` residing in `PandasModel`.
- **Mutations:** Direct edits in the UI update the DataFrame cell by cell.
- **Persistence:** The DataFrame is serialized to JSON/Excel via `GuionManager`.

### 2. Key components
- **`MainWindow` (Controller-ish):** Orchestrates the layout, menus, and communication between the Video Player and the Table.
- **`TableWindow` (View/Logic Hybrid):** Handles the specific business logic of *editing* the script (adding rows, splitting dialogue, merging). It contains the `PandasModel`.
- **`VideoPlayerWidget` (Independent Component):** Handles media playback. It emits signals (`positionChanged`) that the `TableWindow` listens to for synchronization.

### 3. Data Flow
1.  **User Input:** User types in a cell or presses a shortcut (e.g., F5 for Mark IN).
2.  **Action Trigger:** The action calls a method in `TableWindow` or `VideoPlayerWidget`.
3.  **Model Update:**
    - If it's a script edit: `TableWindow` updates `PandasModel`, which updates the underlying `DataFrame`.
    - If it's a timecode: `VideoPlayerWidget` sends the timestamp to `TableWindow`, which writes it to the `COL_IN` column of the active row.
4.  **View Refresh:** `PandasModel` emits `dataChanged`, triggering the View to redraw.

## 🧩 Specific Patterns

### Custom Pandas Model (`Qt AbstractItemModel`)
Instead of using standard Qt items, the app bridges Qt's `QAbstractTableModel` to Pandas.
- **Reads:** `data()` checks the DataFrame.
- **Writes:** `setData()` updates the DataFrame.
- **Implements:** Sorting, Filtering, and Header management directly from Pandas metadata.

### Command Pattern (Undo/Redo)
The app likely implements the Qt Undo Framework (`QUndoStack`).
- Edits are encapsulated in Commands (`hooks` or specific classes in `guion_editor/commands`).
- This allows for robust Undo/Redo of complex batch operations (like "Split Intervention").

### Manager Pattern
- **`GuionManager`:** Encapsulates all I/O complexity. The rest of the app doesn't know how to read a `.docx` or write an `.xlsx`; it just asks the Manager.
- **`ShortcutManager`:** Decouples keybindings from the widgets, allowing user-customizable profiles.
