# TakeoAPP File Tree Map
> Generated: 2025-12-15
> Status: Stability Update Complete

## Project Root `TakeoAPP/`

*   `main.py`: Entry point. Initializes MainWindow, Logging, and Global Styles.
*   `guion_editor.log`: Runtime logs.
*   `recent_files.json`: Persistence for recent file history.
*   `requirements.txt`: Python dependencies.
*   `README.md`: General info.
*   `LICENSE.md`: License info.

### `docs/` (Living Documentation)
*   `00_Context_Bank_Index.md`: Master Index.
*   `01_Project_Manifest.md`: High-level summary & tech stack.
*   `02_File_Tree_Map.md`: This file.
*   `03_Architecture_Patterns.md`: Design patterns & rules.
*   `04_Data_Schema.md`: DataFrame columns & serialization.
*   `05_Roadmap_History.md`: Past milestones.
*   `06_Stability_Log.md`: Tracking for "The Stability Update".

### `tests/`
*   `test_guion_manager_robustness.py`: [NEW] Unit tests for GuionManager schema & edge cases.

### `guion_editor/` (Main Package)
*   `__init__.py`
*   `constants.py`: UI Constants (Colors, Dimensions).
*   `constants_logic.py`: Logic Constants (Columns, FPS, Timecodes).

#### `guion_editor/models/`
*   `pandas_table_model.py`: [MODIFIED] Core QAbstractTableModel. Now uses `ValidationWorker`.
*   `script_model.py`: (Legacy/Alternative model).

#### `guion_editor/widgets/`
*   `table_window.py`: [MODIFIED] Main spreadsheet UI.
*   `video_player_widget.py`: Video playback & sync.
*   `toast_widget.py`: [NEW] Non-blocking notification overlay.
*   `custom_table_view.py`: Extized QTableView.
*   `custom_text_edit.py`: Editor for cells.
*   `time_code_edit.py`: Widget for TC inputs.
*   `waveform_widget.py`: Audio visualization.
*   `cast_window.py`: Character management.
*   `config_dialog.py`: Settings.
*   `search_dialog.py` / `find_replace_dialog.py`
*   (Various other dialogs: `takeo_dialog`, `theme_dialog`, etc.)

#### `guion_editor/workers/`
*   `validation_worker.py`: [NEW] Background thread for heavy validation logic.
*   `audio_conversion_worker.py`: M+E processing.

#### `guion_editor/utils/`
*   `guion_manager.py`: [MODIFIED] Data processing logic (Type Hinted).
*   `file_io_handler.py`: File open/save operations.
*   `dialog_utils.py`: Text processing helpers.
*   `shortcut_manager.py`: QShortcut handling.
*   `paths.py`: Resource path helpers.

#### `guion_editor/commands/`
*   `undo_commands.py`: QUndoCommand implementations.

#### `guion_editor/delegates/`
*   `guion_delegate.py`: Cell rendering/editing delegate.
*   `custom_delegates.py`: Specialized delegates.

#### `guion_editor/styles/`
*   `main.css`: Global stylesheet.
*   `table_styles.css`: Specific table styling.
*   `icons/`: SVG resources.

### `ZANTIGUO/`
*   (Legacy/Archive folder)
