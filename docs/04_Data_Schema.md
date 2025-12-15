# 💾 Data Schema & Types

> **Status:** Active | **Updated:** 2025-12-15

## 🗄️ The Script DataFrame
The core data structure is a **Pandas DataFrame**. Every row represents one "Intervention" (a line of dialogue or scene header).

### Column Definitions
Defined in `guion_editor/constants_logic.py`.

| Internal Name | Excel Header | Type | Description |
| :--- | :--- | :--- | :--- |
| `ID` | `ID` | `int` | Unique identifier (mostly internal, hidden in UI). |
| `SCENE` | `SCENE` | `str` | Scene number (e.g., "1", "2A"). Propagates down. |
| `IN` | `IN` | `str/fmt` | Start Timecode `HH:MM:SS:FF`. |
| `OUT` | `OUT` | `str/fmt` | End Timecode `HH:MM:SS:FF`. |
| `PERSONAJE` | `PERSONAJE` | `str` | Character Name (Uppercase convention). |
| `DIÁLOGO` | `DIÁLOGO` | `str` | The script text. |
| `EUSKERA` | `EUSKERA` | `str` | Translation column (optional). |
| `OHARRAK` | `OHARRAK` | `str` | Notes/Comments. |
| `BOOKMARK` | `BOOKMARK` | `bool` | Visual flag for the user. |

### Serialized Formats

#### 1. JSON (Project Save)
Used for saving the entire state.
```json
{
  "header": {
    "reference_number": "12345",
    "chapter_number": "1"
  },
  "data": [
    {
      "ID": 1,
      "SCENE": "1",
      "IN": "00:00:01:00",
      "OUT": "00:00:05:00",
      "PERSONAJE": "HERO",
      "DIÁLOGO": "Hello world.",
      "EUSKERA": "",
      "BOOKMARK": false
    }
  ]
}
```

#### 2. Excel (Export/Import)
- **Sheet "Guion":** Contains the DataFrame columns exactly as above.
- **Sheet "Header":** (Optional) Key-Value pairs for project metadata.
- **Styling:** `OHARRAK` column presence may trigger row highlighting (Yellow) in the export.

## 🔢 Logic Constants
- **FPS:** `25.0` (Hardcoded in `constants_logic.py`. Critical for Timecode calculations).
- **Timecode Format:** `HH:MM:SS:FF` (Frames are 0-24).

## ⚠️ Data Integrity Rules
- **Scene Propagation:** Empty scene cells are filled forward (`ffill`) during processing in `GuionManager`.
- **String Sanitization:** `NaN`, `None`, and whitespace are normally converted to empty strings for display.
