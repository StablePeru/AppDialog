# guion_editor/constants.py

# Importamos todas las constantes de lógica pura
from .constants_logic import *

ROW_NUMBER_COL_IDENTIFIER = "__ROW_NUMBER__"
DURATION_COL_IDENTIFIER = "__DURATION__"

VIEW_COL_NUM_INTERV = 0
VIEW_COL_ID = 1
VIEW_COL_SCENE = 2
VIEW_COL_IN = 3
VIEW_COL_OUT = 4
VIEW_COL_DURATION = 5
VIEW_COL_CHARACTER = 6
VIEW_COL_DIALOGUE = 7
VIEW_COL_EUSKERA = 8
VIEW_COL_OHARRAK = 9
VIEW_COL_BOOKMARK = 10

VIEW_COLUMN_NAMES = ["Nº", "ID", "SCENE", "IN", "OUT", "DURACIÓN", "PERSONAJE", "DIÁLOGO", "EUSKERA", "OHARRAK", "BOOKMARK"]

# --- Claves de Configuración (QSettings) ---
SETTING_GEOMETRY = "geometry"
SETTING_SPLITTER_STATE = "splitter_state"
SETTING_COLUMN_STATE = "column_state"
SETTING_FONT_SIZE = "font_size"
SETTING_LINE_LENGTH = "line_length"
SETTING_TRIM_VALUE = "trim_value"
SETTING_CAST_WIN_GEOMETRY = "cast_window_geometry"
SETTING_CAST_HEADER_STATE = "cast_table_header_state"
SETTING_UI_LINK_OUT_IN = "link_out_in_enabled"
SETTING_UI_SYNC_VIDEO = "sync_video_enabled"

# --- Identificadores de Acciones (Action IDs) ---
# Usados para conectar menús, shortcuts y botones de la tabla
ACT_FILE_OPEN_VIDEO = "file_open_video"
ACT_FILE_LOAD_ME = "file_load_me"
ACT_FILE_OPEN_DOCX = "file_open_docx"
ACT_FILE_EXPORT_EXCEL = "file_export_excel"
ACT_FILE_IMPORT_EXCEL = "file_import_excel"
ACT_FILE_SAVE_JSON = "file_save_json"
ACT_FILE_SAVE_JSON_AS = "file_save_json_as"
ACT_FILE_LOAD_JSON = "file_load_json"
ACT_FILE_EXPORT_SRT = "file_export_srt"

ACT_EDIT_UNDO = "edit_undo"
ACT_EDIT_REDO = "edit_redo"
ACT_EDIT_ADD_ROW = "edit_add_row"
ACT_EDIT_DELETE_ROW = "edit_delete_row"
ACT_EDIT_TOGGLE_BOOKMARK = "edit_toggle_bookmark"
ACT_EDIT_MOVE_UP = "edit_move_up"
ACT_EDIT_MOVE_DOWN = "edit_move_down"
ACT_EDIT_ADJUST_DIALOGS = "edit_adjust_dialogs"
ACT_EDIT_SHIFT_TIMECODES = "edit_shift_timecodes"
ACT_EDIT_SPLIT_INTERVENTION = "edit_split_intervention"
ACT_EDIT_MERGE_INTERVENTIONS = "edit_merge_interventions"
ACT_EDIT_VIEW_CAST = "edit_view_cast"
ACT_EDIT_FIND_REPLACE = "edit_find_replace"
ACT_EDIT_COPY_IN_OUT = "edit_copy_in_out"
ACT_EDIT_INCREMENT_SCENE = "edit_increment_scene"

ACT_CONFIG_APP = "config_app_settings"
ACT_TOOLS_TAKEO = "tools_run_takeo"
ACT_TOOLS_CREATE_SUB = "tools_create_sub_version"
ACT_TOOLS_XLSX_CONVERTER = "tools_xlsx_converter"
ACT_TOOLS_RESET_SCENES = "tools_reset_scenes"
ACT_TOOLS_RESET_TIMECODES = "tools_reset_timecodes"
ACT_TOOLS_COPY_IN_OUT_PREV = "tools_copy_in_to_out"

ACT_SHORTCUTS_DIALOG = "config_shortcuts_dialog"
ACT_SHORTCUTS_DELETE = "config_delete_shortcut_profile"

ACT_VIDEO_TOGGLE_PLAY = "video_toggle_play"
ACT_VIDEO_REWIND = "video_rewind"
ACT_VIDEO_FORWARD = "video_forward"
ACT_VIDEO_MARK_IN = "video_mark_in"
ACT_VIDEO_MARK_OUT_HOLD = "video_mark_out_hold"