# Guion Editor con Video - Documentation

## 1. Overview

The "Guion Editor con Video" is a PyQt6-based desktop application designed for editing video scripts (guiones) while synchronizing them with a video player. It allows users to load video files, manage script entries in a table format (including character, dialogue, IN/OUT timecodes, and Euskera translations), and export/import scripts in various formats (DOCX, Excel, JSON). The application features an undo/redo system, configurable shortcuts, a detachable video player, and a custom dark theme.

## 2. Features

*   **Video Playback:**
    *   Integrated video player with standard controls (play/pause, rewind, forward).
    *   Volume adjustment.
    *   Support for separate M+E (Music & Effects) audio tracks.
    *   Detachable video player that can be moved to a separate window.
*   **Script Table Management:**
    *   Displays script lines with columns: Intervention Number, ID (hidden), Scene, IN Timecode, OUT Timecode, Character, Dialogue, and Euskera Translation.
    *   Column visibility can be toggled via a context menu on the header.
    *   Add, delete, and move script lines.
    *   Direct in-table editing of script content.
    *   Automatic dialogue line wrapping and row height adjustment.
    *   Adjust all dialogue text to fit line length constraints (max 60 chars per line).
    *   Split a single script intervention into two.
    *   Merge two consecutive script interventions from the same character.
*   **Timecode Synchronization:**
    *   Mark IN and OUT points directly from the video player, updating the table.
    *   Hold-and-drag functionality for marking OUT points (using F6 or OUT button).
    *   Click IN/OUT times in the table (Ctrl+Click for IN, Alt+Click for OUT) to jump the video to that position.
    *   Option to automatically link a row's OUT time to the subsequent row's IN time.
    *   Manual timecode entry and navigation in the video player.
    *   Visual indication of timecode errors (e.g., OUT time before IN time).
*   **File Management:**
    *   Load video files (MP4, AVI, MKV, MOV).
    *   Load M+E audio files (WAV, MP3).
    *   Import scripts from DOCX, Excel, and JSON formats.
    *   Export scripts to Excel and JSON formats.
    *   Automatic generation of default filenames based on script metadata.
    *   Management of a list of recently opened files.
*   **Character Management:**
    *   View a "Cast Window" listing all unique characters and their number of interventions.
    *   Rename characters globally from the Cast Window.
    *   Character name auto-completion when editing in the table.
*   **Search and Replace:**
    *   Find and replace text within Character and Dialogue columns.
*   **Configuration:**
    *   Application settings:
        *   Trim value (in milliseconds) to adjust player position when setting from table.
        *   Font size for the script table and dialogues.
    *   Customizable keyboard shortcuts:
        *   Ability to save and load different shortcut profiles.
        *   Default shortcut profile provided.
*   **Undo/Redo System:**
    *   Comprehensive undo/redo stack for most editing operations (text changes, row additions/deletions/moves, splits/merges, scene changes, character renaming).
*   **User Interface & Styling:**
    *   Custom dark theme applied via CSS.
    *   Collapsible header section in the table window for script metadata (Reference, Product, Chapter, Type).
    *   Icons for most actions and buttons.
*   **Error Handling:**
    *   Global exception handler to catch unexpected errors and display user-friendly messages.

## 3. Project Structure

guion-editor-project/
├── main.py # Main application entry point, MainWindow class
├── guion_editor/
│ ├── init.py
│ ├── widgets/ # Custom Qt widgets
│ │ ├── init.py
│ │ ├── video_player_widget.py # Core video player
│ │ ├── table_window.py # Manages the script table and its operations
│ │ ├── cast_window.py # Displays character list for renaming
│ │ ├── config_dialog.py # Dialog for app settings (trim, font)
│ │ ├── shortcut_config_dialog.py # Dialog for configuring shortcuts
│ │ ├── find_replace_dialog.py # Dialog for find/replace
│ │ ├── custom_table_view.py # QTableView subclass with custom click signals
│ │ ├── custom_table_widget.py # (Appears unused, CustomTableView is preferred)
│ │ ├── custom_text_edit.py # QTextEdit subclass for dialogue editing, tracks cursor
│ │ ├── time_code_edit.py # QLineEdit subclass for HH:MM:SS:FF timecode input
│ │ └── video_window.py # Window for the detached video player
│ ├── models/ # Data models for QTableView
│ │ ├── init.py
│ │ └── pandas_table_model.py # QAbstractTableModel implementation using Pandas
│ ├── delegates/ # Custom item delegates for QTableView
│ │ ├── init.py
│ │ ├── custom_delegates.py # TimeCodeDelegate, CharacterDelegate
│ │ └── guion_delegate.py # DialogDelegate (uses CustomTextEdit)
│ ├── utils/ # Utility classes and functions
│ │ ├── init.py
│ │ ├── shortcut_manager.py # Manages loading, saving, applying shortcuts
│ │ ├── guion_manager.py # Handles script import/export logic
│ │ └── dialog_utils.py # Utilities for DOCX parsing and dialogue formatting
│ └── styles/ # CSS files and icons
│ ├── icons/
│ │ ├── *.svg # Icon files used throughout the application
│ │ └── ...
│ ├── main.css # Global application styles (dark theme)
│ └── table_styles.css # Specific styles for the QTableView
├── shortcuts.json # Saved shortcut configurations (generated at runtime)
└── recent_files.json # List of recently opened files (generated at runtime)


## 4. Core Components

### 4.1. `main.py` - `MainWindow`

*   **Role:** The main application window, responsible for initializing and coordinating all major UI components and managers.
*   **Initialization (`__init__`):**
    *   Sets up the main window's title and geometry.
    *   Initializes `GuionManager` for script data operations and `ShortcutManager` for handling keyboard shortcuts.
    *   Creates the central widget using a `QSplitter` to arrange `VideoPlayerWidget` and `TableWindow`.
    *   Loads recently opened files from `recent_files.json`.
    *   Calls `create_all_actions()` to instantiate `QAction` objects for all menu items, toolbar buttons (if any), and their associated shortcuts.
    *   Connects signals from child widgets (e.g., `videoPlayerWidget.detach_requested`, `tableWindow.in_out_signal`) to appropriate slots in `MainWindow`.
    *   Builds the menu bar (`create_menu_bar()`) and a dedicated menu for shortcut configurations (`create_shortcuts_menu()`).
*   **Key Methods:**
    *   `create_all_actions()` & `add_managed_action()`: Centralized creation of `QAction` instances. Actions are stored in `self.actions` dictionary, keyed by an object name. This allows `ShortcutManager` to easily find and modify them.
    *   Menu Creation (`create_file_menu`, `create_edit_menu`, etc.): Populates the menu bar with actions. The "Recent Files" submenu is dynamically updated.
    *   File Operations:
        *   `open_video_file()`: Opens a dialog to select a video, loads it into `VideoPlayerWidget`, and adds to recent files.
        *   `load_me_audio_file()`: Loads an M+E audio track into `VideoPlayerWidget`.
        *   The other file operations (Open DOCX, Export Excel, etc.) are QActions directly connected to methods in `TableWindow`.
    *   Video Player Interaction:
        *   `detach_video()`: Moves the `VideoPlayerWidget` instance from the main window's splitter to a new `VideoWindow`.
        *   `attach_video()`: Moves the `VideoPlayerWidget` back from `VideoWindow` to the main window.
    *   Dialogs:
        *   `open_cast_window()`: Opens the `CastWindow`.
        *   `open_find_replace_dialog()`: Opens the `FindReplaceDialog`.
        *   `open_config_dialog()`: Opens `ConfigDialog` for application settings (trim, font). Updates `self.trim_value`, `self.font_size`.
        *   `open_shortcut_config_dialog()`: Opens `ShortcutConfigDialog` for managing keyboard shortcuts.
        *   `delete_shortcut_configuration()`: Handles deleting a shortcut profile via `ShortcutManager`.
    *   `handle_set_position(action_type_str, position_ms)`: Slot connected to `TableWindow.in_out_signal`. Adjusts `position_ms` by `self.trim_value` and calls `videoPlayerWidget.set_position_public()`.
    *   `change_scene()`: Calls `tableWindow.change_scene()`.
    *   `closeEvent()`: Prompts to save unsaved changes in `TableWindow` before exiting.
*   **Icon Management (`get_icon` function):**
    *   Global helper function to load `QIcon` objects from `guion_editor/styles/icons/`.
    *   Uses `ICON_CACHE` dictionary to cache loaded icons for efficiency.
*   **Global Exception Handling (`handle_exception` function, `main` function):**
    *   `sys.excepthook` is set to `handle_exception`, which catches unhandled Python exceptions.
    *   It prints the full traceback to the console and displays a user-friendly `QMessageBox` with a summary of the error.

### 4.2. `guion_editor.widgets.video_player_widget.VideoPlayerWidget`

*   **Role:** Encapsulates all video playback functionality and user controls for the video.
*   **UI Elements:**
    *   `QVideoWidget` (`self.video_widget`): The widget that displays the video frames.
    *   `QMediaPlayer` (`self.media_player`): Handles main video playback and audio.
    *   `QMediaPlayer` (`self.me_player`): Handles playback for the separate M+E audio track.
    *   Controls: Play/Pause button (toggles icon), Rewind button, Forward button, Detach button, IN button, OUT button (press-and-hold).
    *   `QSlider` (`self.slider`): Horizontal slider for video progress display and seeking.
    *   Timecode Display:
        *   `QLabel` (`self.time_code_label`): Shows current video timecode in HH:MM:SS:FF.
        *   `TimeCodeEdit` (`self.time_code_editor`): A custom QLineEdit for manual timecode input, appears on double-click of `time_code_label`.
    *   `QCheckBox` (`self.me_toggle_checkbox`): Allows the user to switch between the main video's audio (V.O.) and the loaded M+E track.
    *   Volume Controls: Volume toggle button and a vertical `QSlider` (`self.volume_slider_vertical`).
*   **Core Functionality:**
    *   Video Loading:
        *   `load_video(video_path)`: Sets the source for `self.media_player`. Clears any existing M+E track.
        *   `load_me_file(audio_path)`: Sets the source for `self.me_player`. Enables the M+E toggle checkbox.
    *   Playback Control:
        *   `toggle_play()`: Plays or pauses both `media_player` and `me_player` (if M+E is active and loaded), ensuring synchronization.
        *   `change_position(change_ms)`: Seeks the video forward or backward by a specified number of milliseconds.
        *   `set_position_from_slider_move()`: Sets player position when the user drags the progress slider.
        *   `set_position_public(milliseconds)`: Public method called by `MainWindow` to set player position.
    *   Timecode Marking:
        *   `mark_in()`: Emits `in_out_signal` with "IN" and current player position (ms).
        *   `mark_out_continuous()`: Called by `self.out_timer` when OUT button/F6 is held. Emits `in_out_signal` with "OUT" and current position.
        *   `handle_out_button_pressed()` / `handle_out_button_released()`: Manages the `QTimer` for continuous OUT marking and emits `out_released` signal.
    *   Audio Management:
        *   `toggle_me_audio_source(state)`: Slot for `me_toggle_checkbox`. Updates `self.use_me_audio`.
        *   `_update_audio_outputs()`: Mutes/unmutes `media_player` or `me_player` audio output based on `self.use_me_audio` and applies `self.user_volume_float`.
        *   `set_volume_from_slider_value()`: Sets `self.user_volume_float` and updates audio outputs.
    *   Timecode Display & Editing:
        *   `update_time_code_display()`: Periodically updates `time_code_label`.
        *   `edit_time_code_label()` / `finish_edit_time_code()`: Switches between `time_code_label` and `time_code_editor` for manual input. Validates and applies the new timecode.
    *   Font Updates: `update_fonts(font_size)` adjusts font sizes of controls.
*   **Signals:**
    *   `in_out_signal(str, int)`: Emitted for "IN" or "OUT" marking (action_type, position_ms).
    *   `out_released()`: Emitted when the OUT button/F6 key (for hold-marking) is released.
    *   `detach_requested(QWidget)`: Emitted when the "Detach" button is clicked, passing self.
*   **Key Event Handling:**
    *   `keyPressEvent` / `keyReleaseEvent`: Specifically listen for the F6 key (defined by `MainWindow.mark_out_hold_key_sequence`) to trigger `handle_out_button_pressed` and `handle_out_button_released` for the "Mark OUT (Hold)" functionality.

### 4.3. `guion_editor.widgets.table_window.TableWindow`

*   **Role:** The primary interface for viewing and editing the script (guion). It manages the table, its data model, delegates, and related actions.
*   **UI Elements:**
    *   `CustomTableView` (`self.table_view`): Displays the script.
    *   Header Details Section (`self.header_details_widget`): Contains `QLineEdit`s (Reference, Product, Chapter) and a `QComboBox` (Type) for script metadata. This section is collapsible using `self.toggle_header_button`.
    *   Action Buttons: A row of `QPushButton`s for common table operations (Add Line, Delete Row, Move Up/Down, Adjust Dialogs, Split, Juntar, Copy IN/OUT). These buttons are linked to the same actions as menu items.
    *   `QLabel` (`self.time_error_indicator_label`): Displays "⚠️ TIEMPOS" if any row has an OUT timecode earlier than its IN timecode.
    *   `QCheckBox` (`self.link_out_in_checkbox`): If checked, setting an OUT time for a row automatically sets the IN time for the next row.
*   **Core Functionality:**
    *   Data Model: Uses `PandasTableModel` (`self.pandas_model`) to manage the script data as a Pandas DataFrame.
    *   Undo/Redo: Manages a `QUndoStack` (`self.undo_stack`) to record all modifications as `QUndoCommand` objects, allowing for undo and redo of script changes.
        *   Custom command classes: `EditCommand`, `AddRowCommand`, `RemoveRowsCommand`, `MoveRowCommand`, `SplitInterventionCommand`, `MergeInterventionsCommand`, `ChangeSceneCommand`.
    *   File Operations:
        *   Provides methods like `open_docx_dialog()`, `load_from_excel_path()`, `export_to_excel_dialog()`, etc., which use `GuionManager` to perform the actual file I/O.
        *   `_post_load_script_actions()`: Common UI updates after loading a script.
        *   `_generate_default_filename()`: Creates a suggested filename for saving.
    *   Table Interaction & Editing:
        *   `add_new_row()`: Adds a new row, inferring Scene and Character from the previous/selected row.
        *   `remove_row()`: Removes selected row(s).
        *   `move_row_up()` / `move_row_down()`: Moves the selected row.
        *   `adjust_dialogs()`: Applies `dialog_utils.ajustar_dialogo` to all dialogue lines.
        *   `split_intervention()`: Splits the dialogue of the selected row at the last known cursor position (obtained from `CustomTextEdit` via `handle_dialog_editor_state_on_focus_out`). Creates a new row for the second part.
        *   `merge_interventions()`: Merges the dialogue of the selected row with the next row, provided they are by the same character. The second row is removed.
        *   `copy_in_out_to_next()`: Copies IN and OUT timecodes from the selected row to the next row.
        *   `change_scene()`: Increments the scene number for all rows from the selected row downwards.
    *   Timecode Interaction with Video Player:
        *   `update_in_out_from_player(action_type, position_ms)`: Slot connected to `VideoPlayerWidget.in_out_signal`. Updates the IN or OUT timecode of the selected row in the table.
        *   `handle_ctrl_click_on_cell(view_row_idx)` / `handle_alt_click_on_cell(view_row_idx)`: Connected to `CustomTableView.cellCtrlClicked` / `cellAltClicked`. Emits `self.in_out_signal` to `MainWindow` to set the video player's position to the IN (Ctrl+Click) or OUT (Alt+Click) time of the clicked row.
        *   `select_next_row_after_out_release()`: Slot connected to `VideoPlayerWidget.out_released`. Selects the next row in the table. If `link_out_in_checkbox` is checked, it also copies the OUT time of the current row to the IN time of the newly selected next row.
    *   Delegates & Editors:
        *   Sets up `TimeCodeDelegate`, `CharacterDelegate`, and `DialogDelegate` for appropriate columns to provide custom editing and rendering.
        *   `handle_dialog_editor_state_on_focus_out()`: Receives the final text and cursor position from `CustomTextEdit` when it loses focus. This state is used by `split_intervention()`.
    *   Character Management:
        *   `get_character_names_from_model()`: Retrieves a unique, sorted list of character names from the model for use by `CharacterDelegate`'s completer and `CastWindow`.
        *   `update_character_name(old_name, new_name)`: Called by `CastWindow` to rename a character throughout the script. This is an undoable action. Emits `character_name_changed`.
    *   Find/Replace: `find_and_replace()` method, called by `FindReplaceDialog`, performs text replacement in character/dialogue columns (undoable).
    *   UI Updates:
        *   `update_action_buttons_state()`: Enables/disables action buttons based on row selection.
        *   `update_time_error_indicator()`: Checks `PandasTableModel._time_validation_status` and updates the UI label.
        *   `request_resize_rows_to_contents_deferred()`: Triggers `_perform_resize_rows_to_contents` via a QTimer to adjust row heights after data changes or column resizes.
        *   `apply_font_size_to_dialogs()`: Updates font size for the table and its delegates.
        *   `show_header_context_menu()` / `toggle_column_visibility()`: Allows users to show/hide table columns.
*   **Signals:**
    *   `in_out_signal(str, int)`: Emitted to `MainWindow` when Ctrl+Click or Alt+Click occurs on IN/OUT cells (action_type, position_ms).
    *   `character_name_changed()`: Emitted when character names are updated, notifying `CastWindow` to refresh.
*   **Key Event Handling:**
    *   `keyPressEvent` / `keyReleaseEvent`: Listens for F6 key (from `MainWindow.mark_out_hold_key_sequence`) and relays the press/release to `VideoPlayerWidget`'s `handle_out_button_pressed/released` methods. This ensures F6 works for OUT marking even when `TableWindow` has focus.

### 4.4. `guion_editor.models.pandas_table_model.PandasTableModel`

*   **Role:** An implementation of `QAbstractTableModel` that uses a Pandas DataFrame as its underlying data store. This model serves the `CustomTableView` in `TableWindow`.
*   **Core Functionality:**
    *   DataFrame Management:
        *   Stores script data in `self._dataframe`.
        *   `_ensure_df_structure()`: Guarantees that the DataFrame has all necessary columns (`ID`, `SCENE`, `IN`, `OUT`, `PERSONAJE`, `DIÁLOGO`, `EUSKERA`) with appropriate default values and data types. Reorders columns if necessary.
        *   `set_dataframe(dataframe)`: Replaces the internal DataFrame, resets the model, and re-validates all timecodes.
    *   QAbstractTableModel Implementation:
        *   `rowCount()`, `columnCount()`: Return dimensions based on the DataFrame.
        *   `data(index, role)`: Provides data for various roles:
            *   `DisplayRole`/`EditRole`: Returns cell value as a string.
            *   `BackgroundRole`: For 'IN'/'OUT' columns, returns a `QBrush` (red for invalid time, transparent for valid) based on `self._time_validation_status`.
            *   Handles a special `ROW_NUMBER_COL_IDENTIFIER` to display row numbers.
        *   `setData(index, value, role)`: Updates the DataFrame when a cell is edited.
            *   Validates 'IN'/'OUT' timecode format.
            *   For 'IN'/'OUT' changes, calls `_validate_in_out_for_row()` and emits `dataChanged` for `BackgroundRole` if validation status changes.
        *   `headerData()`: Provides column headers.
        *   `flags()`: Defines item properties (editable, selectable, enabled). 'ID' column is not editable.
    *   Row Operations:
        *   `insert_row_data(df_row_idx, row_data_dict)`: Inserts a new row into the DataFrame at the specified index. Handles ID generation and default values. Updates `_time_validation_status`.
        *   `remove_row_by_df_index(df_row_idx)`: Removes a row. Updates `_time_validation_status`.
        *   `move_df_row(source_df_idx, target_df_idx)`: Moves a row within the DataFrame. Rebuilds `_time_validation_status`.
    *   Timecode Validation:
        *   `_convert_tc_to_ms(time_code_str)`: Converts "HH:MM:SS:FF" string to milliseconds (assumes 25 FPS).
        *   `_validate_in_out_for_row(df_row_idx)`: Checks if `OUT_ms >= IN_ms` for the given row and updates `self._time_validation_status[df_row_idx]`.
        *   `force_time_validation_update_for_row(df_row_idx)`: Re-runs validation for a row and emits `dataChanged` for background if status changed.
    *   Helper Methods:
        *   `get_next_id()`: Finds the maximum existing 'ID' and returns max+1.
        *   `find_df_index_by_id(id_value)`: Returns the DataFrame index for a given 'ID'.
        *   `get_view_column_index(df_col_name)` / `get_df_column_name(view_col_idx)`: Map between view column indices and DataFrame column names.

### 4.5. Delegates (Located in `guion_editor.delegates/`)

*   **`custom_delegates.TimeCodeDelegate`:**
    *   **Editor:** Uses `guion_editor.widgets.time_code_edit.TimeCodeEdit` for editing 'IN' and 'OUT' column cells.
    *   **Painting:** Custom `paint` method to correctly render the background color (e.g., red for invalid timecodes) as provided by `PandasTableModel`'s `BackgroundRole`, while respecting selection state.
*   **`custom_delegates.CharacterDelegate`:**
    *   **Editor:** Uses a `QLineEdit` for the 'PERSONAJE' column.
    *   **Auto-completion:** Configures a `QCompleter` for the `QLineEdit`, populated with existing character names obtained via a callback (`TableWindow.get_character_names_from_model`).
*   **`guion_delegate.DialogDelegate`:**
    *   **Editor:** Uses `guion_editor.widgets.custom_text_edit.CustomTextEdit` for 'DIÁLOGO' and 'EUSKERA' columns, allowing multi-line text editing.
    *   **Sizing:** `sizeHint()` calculates the necessary row height based on the dialogue text content, font size, and column width, enabling text wrapping.
    *   **Painting:** `paint()` method correctly draws multi-line, word-wrapped text within the cell.
    *   **Font Management:** `setFontSize()` allows the delegate to adapt to font size changes from application settings.
    *   **Integration with `TableWindow`:** Connects `CustomTextEdit.focusLostWithState` signal to `TableWindow.handle_dialog_editor_state_on_focus_out`.

### 4.6. `guion_editor.widgets.custom_text_edit.CustomTextEdit`

*   **Role:** A subclass of `QTextEdit` designed for use as an editor in `DialogDelegate`. Its key feature is to report its state (text and cursor position) when it loses focus.
*   **Core Functionality:**
    *   Signal `focusLostWithState(str, int, QModelIndex)`: Emitted in `focusOutEvent`. It passes the current text, the last known cursor position, and the model index that was being edited. This is crucial for features like "Split Intervention" in `TableWindow`.
    *   Cursor Position Tracking: `_last_known_cursor_pos` is meticulously updated via `cursorPositionChanged` signal, `setPlainText()`, and `_ensure_cursor_pos_on_show()` (called on `showEvent` via `QTimer.singleShot`) to ensure the reported cursor position is accurate.
    *   `setEditingIndex()`: Stores the `QModelIndex` it is currently editing.

### 4.7. Other Key Widgets

*   **`guion_editor.widgets.cast_window.CastWindow`:**
    *   Displays a table of unique characters from the script and the count of their interventions.
    *   Data is sourced from `TableWindow.pandas_model`.
    *   Allows editing character names in its table. Changes are propagated back to `TableWindow.update_character_name()` to update the main script model globally (this is an undoable action).
    *   Connects to `TableWindow.pandas_model.dataChanged` and `layoutChanged` to refresh its display when the script data changes.
    *   Sortable columns (Character, Interventions).
*   **`guion_editor.widgets.config_dialog.ConfigDialog`:**
    *   A simple dialog with `QSpinBox` controls for setting the "Trim" value (ms) and "Font Size".
    *   Returns the selected values to `MainWindow` when accepted.
*   **`guion_editor.widgets.shortcut_config_dialog.ShortcutConfigDialog`:**
    *   Allows users to view and modify keyboard shortcuts for actions defined in `MainWindow.actions`.
    *   Displays actions and their current shortcuts in a `QTableWidget`.
    *   Uses `QKeySequenceEdit` for users to input new shortcuts.
    *   Checks for shortcut conflicts.
    *   Interacts with `ShortcutManager` to:
        *   Populate the table based on the `ShortcutManager.current_config`.
        *   Update shortcuts in the `ShortcutManager`'s current configuration.
        *   Save the current set of modified shortcuts as a new named profile (`save_configuration_profile()`).
*   **`guion_editor.widgets.find_replace_dialog.FindReplaceDialog`:**
    *   Provides `QLineEdit`s for "Find" and "Replace with" text.
    *   `QCheckBox`es to specify search scope (Character column, Dialogue column).
    *   Buttons for "Find Previous", "Find Next", and "Replace All".
    *   "Find Next"/"Previous" highlights matching rows in the `TableWindow`.
    *   "Replace All" calls `TableWindow.find_and_replace()` to perform replacements (this is an undoable action).
*   **`guion_editor.widgets.time_code_edit.TimeCodeEdit`:**
    *   A `QLineEdit` subclass specifically for inputting timecodes in "HH:MM:SS:FF" format.
    *   Handles direct digit input by shifting existing digits or filling from right to left if input is partial.
    *   Manages backspace/delete.
    *   Handles pasting text, extracting only digits.
    *   `set_time_code()` and `get_time_code()` for programmatic access.
*   **`guion_editor.widgets.video_window.VideoWindow`:**
    *   A `QMainWindow` that acts as a container for the `VideoPlayerWidget` when it is detached from the `MainWindow`.
    *   Includes an "Attach Back" button that closes the window, signaling `MainWindow` to re-attach the player.
    *   Its `closeEvent` emits `close_detached` signal.
    *   Like `VideoPlayerWidget` and `TableWindow`, it handles F6 key events to ensure "Mark OUT (Hold)" functionality works when this window has focus.

### 4.8. Manager Classes (Located in `guion_editor.utils/`)

*   **`guion_manager.GuionManager`:**
    *   Centralizes logic for loading and saving script data to/from different file formats.
    *   `load_from_excel()`, `save_to_excel()`: Handles `.xlsx` files. Metadata (reference, product, etc.) can be stored on a separate "Header" sheet.
    *   `load_from_json()`, `save_to_json()`: Handles `.json` files. JSON structure includes a "header" object for metadata and a "data" array for script lines.
    *   `load_from_docx()`: Uses `dialog_utils.leer_guion` to parse `.docx` script files. Assumes a simple format of CHARACTER_NAME followed by dialogue lines.
    *   `_verify_and_prepare_df()`: A crucial internal method called after loading data from any source. It ensures the DataFrame has all required columns (ID, SCENE, IN, OUT, PERSONAJE, DIÁLOGO, EUSKERA), adds them with default values if missing, and determines if the script uses distinct scene numbers or defaults to "1".
*   **`shortcut_manager.ShortcutManager`:**
    *   Manages keyboard shortcut configurations for the application.
    *   `load_shortcuts()`: Loads configurations from `shortcuts.json`. If the file is missing or corrupt, it calls `create_default_config()` and saves it.
    *   `save_shortcuts()`: Saves all configurations and the name of the currently active configuration to `shortcuts.json`.
    *   `create_default_config()`: Defines a "default" set of shortcuts for all actions.
    *   `apply_shortcuts(config_name)`: Iterates through `MainWindow.actions` and sets their `shortcut` property based on the selected `config_name`. Special handling for "video_mark_out_hold" (F6): instead of setting the shortcut on its `QAction` (which could interfere with global key events), it updates `MainWindow.mark_out_hold_key_sequence`. The QAction for F6 still exists to be listed in the config dialog.
    *   `add_configuration()`, `delete_configuration()`, `update_configuration()`: Allow creating, deleting, and modifying shortcut profiles.
    *   `refresh_shortcuts_menu()`: Calls `MainWindow.create_shortcuts_menu()` to rebuild the shortcuts menu, reflecting any changes in available profiles.

### 4.9. Utility Modules

*   **`guion_editor.utils.dialog_utils.py`:**
    *   `ajustar_dialogo(dialogo_str)`: Reformats a given dialogue string so that each line has a maximum of 60 characters. Text within parentheses `()` is not counted towards the character limit and is preserved on its original line if possible or moved with the word it's attached to.
    *   `contar_caracteres(dialogo_str)`: Counts characters in a dialogue string, excluding any text within parentheses.
    *   `es_nombre_personaje(texto_str)`: A heuristic function to determine if a given text line from a DOCX file is likely a character name (typically all uppercase, short).
    *   `leer_guion(docx_file_path)`: Parses a DOCX file. It iterates through paragraphs, using `es_nombre_personaje` to identify character lines and then accumulates subsequent lines as their dialogue. Calls `ajustar_dialogo` on the accumulated dialogue. Returns a list of dictionaries, each representing a script line.

### 4.10. Styling (Located in `guion_editor.styles/`)

*   **`main.css`:** Provides global CSS rules for the application, establishing a dark theme. It styles `QMainWindow`, `QDialog`, `QPushButton`, `QLineEdit`, `QComboBox`, `QSlider`, `QMenuBar`, `QMenu`, `QMessageBox`, and `QToolTip`. Specific button styles are often defined by `objectName`.
*   **`table_styles.css`:** Contains CSS rules specifically for `QTableView` and its components, such as items, alternate rows, selected items, header sections, and embedded `QTextEdit` (used by `DialogDelegate`). This ensures the table also fits the dark theme.
*   **`icons/` directory:** Stores all `.svg` icon files used by the application. The `get_icon()` function in `main.py` loads these.

## 5. Key Workflows and Interactions

*(This section would typically describe common user stories and how different components interact to achieve them. Examples include: "Loading a Video and Script," "Marking IN/OUT points and Auto-linking," "Splitting an Intervention," "Changing Shortcuts.")*

## 6. Setup and Running

1.  **Prerequisites:**
    *   Python 3.x
    *   PyQt6
    *   Pandas
    *   openpyxl (for Excel file support)
    *   python-docx (for DOCX file support)
2.  **Installation of Dependencies:**
    ```bash
    pip install PyQt6 pandas openpyxl python-docx
    ```
3.  **Running the Application:**
    Navigate to the root directory of the project (where `main.py` is located) and run:
    ```bash
    python main.py
    ```
    The application should start, displaying the main window maximized. `shortcuts.json` and `recent_files.json` will be created in the root directory if they don't exist.

## 7. Notes and Potential Improvements

*   **Unused Code:** The widget `guion_editor/widgets/custom_table_widget.py` (class `CustomTableWidget`) appears to be an older or alternative implementation and is not currently used by the main application, which uses `CustomTableView`. It could potentially be removed.
*   **Error Handling:** While there's a global exception handler, file parsing errors within `GuionManager` or `dialog_utils` could be made more specific to provide users with clearer feedback on what went wrong with a particular file.
*   **Hardcoded FPS:** The application assumes 25 FPS for timecode conversions in several places (e.g., `PandasTableModel._convert_tc_to_ms`, `VideoPlayerWidget._convert_ms_to_tc_parts`). This could be made configurable or detected from the video if possible.
*   **Configuration Persistence:** Currently, trim value and font size are reset each time the application starts. These could be saved to a configuration file (perhaps extending `shortcuts.json` or a new settings file).
*   **Testing:** No automated tests are present. Adding unit and integration tests would greatly improve the robustness and maintainability of the application.
*   **Internationalization (i18n):** All UI strings are currently in Spanish. For broader usability, a translation system could be implemented.