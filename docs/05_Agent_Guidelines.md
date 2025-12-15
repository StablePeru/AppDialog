# 🤖 Agent Guidelines

> **Target Audience:** Autonomous Agents & Developers
> **Purpose:** Ensure consistent, clean, and maintainable code.

## 🛑 Strict Rules

1.  **Framework Consistency:**
    *   **GUI:** Use `PyQt6` exclusively. Do NOT import `PySide6`, `tkinter`, or `wxPython`.
    *   **Data:** Use `pandas` for all script data. Do NOT introduce SQLite or local databases unless explicitly requested for a new subsystem.
    *   **Async:** Avoid `asyncio` for UI logic. Use `QTimer` or `QThread` if absolutely necessary (but prefer synchronous `pandas` operations as they are generally fast enough for this data size).

2.  **File I/O:**
    *   **Always** use `guion_editor.utils.guion_manager.GuionManager` for reading/writing Scripts (JSON/Excel).
    *   **Always** use `guion_editor.utils.paths.resource_path` for loading static assets (icons/styles) to ensure compatibility with PyInstaller builds.

3.  **Naming Conventions:**
    *   **Classes:** PascalCase (e.g., `VideoPlayerWidget`, `PandasTableModel`).
    *   **Methods/Functions:** snake_case (e.g., `process_dataframe`, `update_action_buttons_state`).
    *   **Variables:** snake_case.
    *   **Constants:** UPPER_CASE (e.g., `COL_SCENE`, `ACT_EDIT_UNDO`).
    *   **Private Members:** Prefix with `_` (e.g., `_dataframe`, `_init_internal_state`).

4.  **Error Handling:**
    *   Catch specific exceptions (e.g., `OSError`, `json.JSONDecodeError`) rather than bare `except:`.
    *   Use `QMessageBox` to inform the user of errors in the UI, but **always** log the error using `logging.error(..., exc_info=True)` first.

## 🛠️ Workflow: How to add a new feature

### 1. Define the Action
Add a new constant in `guion_editor/constants.py` for the action ID.
```python
ACT_MY_NEW_FEATURE = "my_new_feature_id"
```

### 2. Implement the Logic
- If it modifies data: Add a method in `guion_editor/widgets/table_window.py`.
- If it affects video: Add to `guion_editor/widgets/video_player_widget.py`.
- **Crucial:** If the action is undoable, creating a `QUndoCommand` in `guion_editor/commands/undo_commands.py` is mandatory.

### 3. Register the Action
In `main.py`, inside `create_all_actions`:
```python
self.add_managed_action("My Feature Name", self.tableWindow.my_new_method, "Ctrl+Alt+X", "my_icon.svg", C.ACT_MY_NEW_FEATURE)
```

### 4. Add to Menu
In `main.py`, inside `create_edit_menu` (or appropriate menu):
```python
editMenu.addAction(self.actions[C.ACT_MY_NEW_FEATURE])
```

### 5. Add to Shortcuts
Update `guion_editor/utils/shortcut_manager.py` inside `_get_default_config_template` to ensure it has a default binding (or empty string if none).

## 🧪 Testing Guidelines
- Tests are located in `tests/`.
- Run tests using `pytest` from the root directory.
- Mocks: When testing UI logic without a running event loop, verify logic by inspecting the `PandasTableModel` directly.
