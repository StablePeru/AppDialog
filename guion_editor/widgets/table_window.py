# guion_editor/widgets/table_window.py
import json
import os
import re
from typing import Any, List, Dict, Optional, Tuple
import pandas as pd
import bisect

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QModelIndex, QTimer, QPoint
from PyQt6.QtGui import QFont, QIntValidator, QIcon, QKeyEvent, QKeySequence, QAction
from PyQt6.QtWidgets import (
    QWidget, QAbstractItemView, QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLineEdit, QLabel, QFormLayout, QInputDialog, QCheckBox, QMenu,
    QSizePolicy, QDialog, QToolTip, QProgressDialog, QApplication
)
from PyQt6.QtGui import QUndoStack

from guion_editor import constants as C
from guion_editor.widgets.custom_table_view import CustomTableView
from guion_editor.models.pandas_table_model import PandasTableModel
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.delegates.guion_delegate import DialogDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.utils.file_io_handler import FileIOHandler
from guion_editor.utils.guion_manager import GuionManager
from guion_editor.widgets.custom_text_edit import CustomTextEdit 
from guion_editor.widgets.shift_timecode_dialog import ShiftTimecodeDialog
from guion_editor.commands.undo_commands import (
    EditCommand, AddRowCommand, RemoveRowsCommand, MoveRowCommand,
    SplitInterventionCommand, MergeInterventionsCommand, ChangeSceneCommand, HeaderEditCommand,
    ToggleBookmarkCommand, UpdateMultipleCharactersCommand, SplitCharacterCommand,
    TrimAllCharactersCommand, ShiftTimecodesCommand, ResetTimecodesCommand, ResetScenesCommand,
    CopyInToPreviousOutCommand
)

class TableWindow(QWidget):
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    VIEW_COLUMN_NAMES = C.VIEW_COLUMN_NAMES
    VIEW_TO_DF_COL_MAP = {
        C.VIEW_COL_NUM_INTERV: C.ROW_NUMBER_COL_IDENTIFIER, C.VIEW_COL_ID: C.COL_ID,
        C.VIEW_COL_SCENE: C.COL_SCENE, C.VIEW_COL_IN: C.COL_IN, C.VIEW_COL_OUT: C.COL_OUT,
        C.VIEW_COL_DURATION: C.DURATION_COL_IDENTIFIER, C.VIEW_COL_CHARACTER: C.COL_PERSONAJE,
        C.VIEW_COL_DIALOGUE: C.COL_DIALOGO, C.VIEW_COL_EUSKERA: C.COL_EUSKERA,
        C.VIEW_COL_OHARRAK: C.COL_OHARRAK, C.VIEW_COL_BOOKMARK: C.COL_BOOKMARK
    }
    DF_COLUMN_ORDER = C.DF_COLUMN_ORDER

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None,
                 guion_manager = None, get_icon_func=None):
        super().__init__()
        self._init_internal_state(video_player_widget, main_window, guion_manager, get_icon_func)
        self.file_io_handler = FileIOHandler(self)
        self._init_timers()
        self.setup_ui()
        self.update_action_buttons_state()
        self._connect_signals()
        self.clear_script_state()
        self.update_window_title()
        QTimer.singleShot(0, self.hide_default_columns)

    def open_docx_dialog(self) -> None:
        self.file_io_handler.load_docx()
        
    def load_from_docx_path(self, file_path: str):
        self.file_io_handler._load_docx_path(file_path)

    def import_from_excel_dialog(self) -> None:
        self.file_io_handler.import_excel()

    def load_from_excel_path(self, file_path: str):
        self.file_io_handler._load_excel_path(file_path)

    def load_from_json_dialog(self) -> None:
        self.file_io_handler.load_json()

    def load_from_json_path(self, file_path: str):
        self.file_io_handler._load_json_path(file_path)

    def export_to_excel_dialog(self) -> bool:
        return self.file_io_handler.export_excel()

    def save_to_json_dialog(self) -> bool:
        return self.file_io_handler.save_as_json()
        
    def hide_default_columns(self):
        self.table_view.horizontalHeader().setSectionsMovable(True)
        self.table_view.setColumnHidden(C.VIEW_COL_BOOKMARK, True)

    def _init_internal_state(self, video_player_widget, main_window, guion_manager, get_icon_func):
        self.get_icon = get_icon_func
        self.main_window = main_window
        self.video_player_widget = video_player_widget
        self.guion_manager = guion_manager if guion_manager else GuionManager()
        self.current_font_size = 9
        self.f6_key_pressed_internally = False
        self.action_buttons = {}
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.pandas_model = PandasTableModel(column_map=self.VIEW_TO_DF_COL_MAP, view_column_names=self.VIEW_COLUMN_NAMES)
        self.unsaved_changes = False
        self.undo_stack = QUndoStack(self)
        self.current_script_name: Optional[str] = None
        self.current_script_path: Optional[str] = None
        self.clipboard_text: str = ""
        self.link_out_to_next_in_enabled = True
        self._is_marking_out = False
        self._out_mark_original_value = None; self._out_mark_final_value = None; self._out_mark_df_row_idx = -1
        self.last_focused_dialog_text: Optional[str] = None
        self.last_focused_dialog_cursor_pos: int = -1
        self.last_focused_dialog_index: Optional[QModelIndex] = None
        self.subtitle_source_column = C.COL_DIALOGO
        if self.get_icon:
            self.icon_expand_less, self.icon_expand_more = self.get_icon("toggle_header_collapse_icon.svg"), self.get_icon("toggle_header_expand_icon.svg")
        else: self.icon_expand_less, self.icon_expand_more = QIcon(), QIcon()
        self.time_error_indicator_button: Optional[QPushButton] = None
        self.error_df_indices: List[int] = []; self._current_error_nav_idx: int = -1
        self.scene_error_indicator_button: Optional[QPushButton] = None
        self.scene_error_df_indices: List[int] = []; self._current_scene_error_nav_idx: int = -1
        self.line_error_indicator_button: Optional[QPushButton] = None
        self.line_error_df_indices: List[int] = []; self._current_line_error_nav_idx: int = -1
        self.bookmark_indicator_button: Optional[QPushButton] = None
        self.bookmark_df_indices: List[int] = []; self._current_bookmark_nav_idx: int = -1
        self._current_header_data_for_undo: Dict[str, Any] = {}
        self.cached_subtitle_timeline: List[Tuple[int, int, str]] = []
        self._time_cache: List[Tuple[int, int]] = []; self._currently_synced_row: int = -1

    def _init_timers(self):
        self._resize_rows_timer = QTimer(self); self._resize_rows_timer.setSingleShot(True); self._resize_rows_timer.setInterval(100)
        self._update_error_indicator_timer = QTimer(self); self._update_error_indicator_timer.setSingleShot(True); self._update_error_indicator_timer.setInterval(0)
        self._update_scene_error_indicator_timer = QTimer(self); self._update_scene_error_indicator_timer.setSingleShot(True); self._update_scene_error_indicator_timer.setInterval(0)
        self._update_line_error_indicator_timer = QTimer(self); self._update_line_error_indicator_timer.setSingleShot(True); self._update_line_error_indicator_timer.setInterval(0)
        self._update_bookmark_indicator_timer = QTimer(self); self._update_bookmark_indicator_timer.setSingleShot(True); self._update_bookmark_indicator_timer.setInterval(0)
        self._recache_timer = QTimer(self); self._recache_timer.setSingleShot(True); self._recache_timer.setInterval(150)
        self._header_change_timer: Optional[QTimer] = None

    def _connect_signals(self):
        self._resize_rows_timer.timeout.connect(self._perform_resize_rows_to_contents)
        self._update_error_indicator_timer.timeout.connect(self.update_time_error_indicator)
        self._update_scene_error_indicator_timer.timeout.connect(self.update_scene_error_indicator)
        self._update_line_error_indicator_timer.timeout.connect(self.update_line_error_indicator)
        self._update_bookmark_indicator_timer.timeout.connect(self.update_bookmark_indicator)
        self._recache_timer.timeout.connect(self._recache_subtitle_timeline)
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out_from_player)
            self.video_player_widget.out_released.connect(self.select_next_row_after_out_release)
        for signal in [self.pandas_model.dataChanged, self.pandas_model.layoutChanged, self.pandas_model.modelReset]:
            signal.connect(self._request_error_indicator_update)
            signal.connect(self._request_scene_error_indicator_update)
            signal.connect(self._request_bookmark_indicator_update)
            signal.connect(self._request_line_error_indicator_update)
            signal.connect(self._request_recache_subtitles)
        self.pandas_model.dataChanged.connect(self.on_model_data_changed)
        self.pandas_model.layoutChanged.connect(self.on_model_layout_changed)
        self.undo_stack.canUndoChanged.connect(self._update_undo_action_state)
        self.undo_stack.canRedoChanged.connect(self._update_redo_action_state)
        self.undo_stack.cleanChanged.connect(self._handle_clean_changed)

    def _update_undo_action_state(self, can_undo: bool):
        if self.main_window and hasattr(self.main_window, 'actions') and "edit_undo" in self.main_window.actions: self.main_window.actions["edit_undo"].setEnabled(can_undo)
    def _update_redo_action_state(self, can_redo: bool):
        if self.main_window and hasattr(self.main_window, 'actions') and "edit_redo" in self.main_window.actions: self.main_window.actions["edit_redo"].setEnabled(can_redo)
    def _handle_clean_changed(self, is_clean: bool): self.set_unsaved_changes(not is_clean)
    def _request_error_indicator_update(self): self._update_error_indicator_timer.start()
    def _request_scene_error_indicator_update(self): self._update_scene_error_indicator_timer.start()
    def _request_bookmark_indicator_update(self): self._update_bookmark_indicator_timer.start()
    def _request_line_error_indicator_update(self): self._update_line_error_indicator_timer.start()

    def update_line_error_indicator(self):
        if not hasattr(self, 'line_error_indicator_button') or self.line_error_indicator_button is None or not hasattr(self.pandas_model, '_line_validation_status'): return
        all_errors, error_indices = self.pandas_model._line_validation_status, []
        for idx, status_dict in all_errors.items():
            if not status_dict.get(C.COL_DIALOGO, True) or not status_dict.get(C.COL_EUSKERA, True): error_indices.append(idx)
        self.line_error_df_indices = sorted(error_indices)
        has_errors = bool(self.line_error_df_indices)
        if not has_errors: self._current_line_error_nav_idx = -1
        self.line_error_indicator_button.setVisible(has_errors)
        if has_errors:
            self.line_error_indicator_button.setText("⚠️ LÍNEAS")
            self.line_error_indicator_button.setProperty("hasErrors", True)
            self.line_error_indicator_button.setToolTip(f"Avisos de líneas detectados en DIÁLOGO o EUSKERA. Pulse para ir al siguiente.\nFilas: {', '.join(map(str, [i+1 for i in self.line_error_df_indices]))}")
        if self.line_error_indicator_button.style():
            self.line_error_indicator_button.style().unpolish(self.line_error_indicator_button)
            self.line_error_indicator_button.style().polish(self.line_error_indicator_button)

    def go_to_next_line_error(self):
        if not self.line_error_df_indices: return
        self._current_line_error_nav_idx = (self._current_line_error_nav_idx + 1) % len(self.line_error_df_indices)
        target_df_idx = self.line_error_df_indices[self._current_line_error_nav_idx]
        self.table_view.clearSelection(); self.table_view.selectRow(target_df_idx)
        self.table_view.scrollTo(self.pandas_model.index(target_df_idx, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table_view.setFocus()

    def _request_recache_subtitles(self): self._recache_timer.start()

    def _recache_subtitle_timeline(self):
        self.cached_subtitle_timeline.clear()
        df = self.pandas_model.dataframe()
        if df.empty or self.subtitle_source_column not in df.columns: return
        for i in range(len(df)):
            try:
                in_tc, out_tc, subtitle_text = str(df.at[i, C.COL_IN]), str(df.at[i, C.COL_OUT]), str(df.at[i, self.subtitle_source_column])
                in_ms, out_ms = self.convert_time_code_to_milliseconds(in_tc), self.convert_time_code_to_milliseconds(out_tc)
                if in_ms is not None and out_ms is not None and in_ms < out_ms: self.cached_subtitle_timeline.append((in_ms, out_ms, subtitle_text))
            except (KeyError, ValueError, TypeError): continue
        self.cached_subtitle_timeline.sort(key=lambda x: x[0])

    def trigger_recache_with_source(self, source_column: str):
        if source_column in self.DF_COLUMN_ORDER: self.subtitle_source_column = source_column; self._request_recache_subtitles()

    def get_subtitle_timeline(self) -> List[Tuple[int, int, str]]: return self.cached_subtitle_timeline
    
    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        icon_size_header_toggle = QSize(20, 20)
        self.toggle_header_button = QPushButton()
        self.toggle_header_button.setIconSize(icon_size_header_toggle)
        self.toggle_header_button.setObjectName("toggle_header_button_css")
        self.toggle_header_button.clicked.connect(self.toggle_header_visibility)
        main_layout.addWidget(self.toggle_header_button)
        self.header_details_widget = QWidget()
        self.header_details_widget.setObjectName("header_details_container")
        self.header_form_layout = QFormLayout()
        self.header_form_layout.setContentsMargins(15, 15, 15, 15)
        self.header_form_layout.setHorizontalSpacing(15)
        self.header_form_layout.setVerticalSpacing(10)
        self.header_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.header_form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.header_details_widget.setLayout(self.header_form_layout)
        self.setup_header_fields(self.header_form_layout)
        main_layout.addWidget(self.header_details_widget)
        self.header_details_widget.setVisible(False)
        self._update_toggle_header_button_text_and_icon()
        self.setup_buttons(main_layout)
        self.setup_table_view(main_layout)
        self.load_stylesheet()

    def setup_header_fields(self, form_layout: QFormLayout) -> None:
        field_max_width = 200
        product_field_min_width = 300
        self.reference_edit = QLineEdit()
        self.reference_edit.setValidator(QIntValidator(0, 999999, self))
        self.reference_edit.setMaxLength(6)
        self.reference_edit.setPlaceholderText("Máximo 6 dígitos")
        self.reference_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.reference_edit.setMaximumWidth(field_max_width)
        self.product_edit = QLineEdit()
        self.product_edit.setPlaceholderText("Nombre del producto")
        self.product_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.product_edit.setMinimumWidth(product_field_min_width)
        self.chapter_edit = QLineEdit()
        self.chapter_edit.setPlaceholderText("Número de capítulo")
        self.chapter_edit.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.chapter_edit.setMaximumWidth(field_max_width)
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Ficcion", "Animacion", "Documental"])
        self.type_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.type_combo.setMaximumWidth(field_max_width)
        form_layout.addRow("Número de referencia:", self.reference_edit)
        form_layout.addRow("Nombre del Producto:", self.product_edit)
        form_layout.addRow("N.º Capítulo:", self.chapter_edit)
        form_layout.addRow("Tipo:", self.type_combo)
        for widget in [self.reference_edit, self.product_edit, self.chapter_edit, self.type_combo]:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._header_field_changed)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._header_field_changed)

    def _header_field_changed(self, *args):
        self._update_toggle_header_button_text_and_icon()
        if self._header_change_timer is None:
            self._header_change_timer = QTimer(self)
            self._header_change_timer.setSingleShot(True)
            self._header_change_timer.timeout.connect(self._process_header_change_for_undo)
        self._header_change_timer.start(250)

    def _process_header_change_for_undo(self):
        current_ui_header_data = self._get_header_data_from_ui()
        if current_ui_header_data != self._current_header_data_for_undo:
            command = HeaderEditCommand(self, self._current_header_data_for_undo, current_ui_header_data)
            self.undo_stack.push(command)

    def toggle_header_visibility(self) -> None:
        self.header_details_widget.setVisible(not self.header_details_widget.isVisible())
        self._update_toggle_header_button_text_and_icon()

    def setup_buttons(self, layout: QVBoxLayout) -> None:
        self.top_controls_row_widget = QWidget()
        self.top_controls_row_widget.setObjectName("top_controls_row_widget_css")
        buttons_overall_container_layout = QHBoxLayout(self.top_controls_row_widget)
        buttons_overall_container_layout.setContentsMargins(0,0,0,0)
        buttons_overall_container_layout.setSpacing(10)
        self.table_actions_widget = QWidget()
        self.table_actions_widget.setObjectName("table_actions_bar")
        actions_bar_internal_layout = QHBoxLayout(self.table_actions_widget)
        actions_bar_internal_layout.setContentsMargins(0, 0, 0, 0)
        actions_bar_internal_layout.setSpacing(4)
        action_icon_size = QSize(16, 16)
        actions_map = [
            (" Agregar Línea", self.add_new_row, "add_row_icon.svg", False, "edit_add_row", None),
            (" Eliminar Fila", self.remove_row, "delete_row_icon.svg", False, "edit_delete_row", None),
            (" Marcapáginas", self.toggle_bookmark, "bookmark_icon.svg", False, "edit_toggle_bookmark", "Marcar/Desmarcar Fila(s)"),
            ("", self.move_row_up, "move_up_icon.svg", True, "edit_move_up", "Mover Fila Arriba"),
            ("", self.move_row_down, "move_down_icon.svg", True, "edit_move_down", "Mover Fila Abajo"),
            (" Ajustar Diálogos", self.main_window.call_adjust_dialogs, "adjust_dialogs_icon.svg", False, "edit_adjust_dialogs", None),
            (" Separar", self.split_intervention, "split_intervention_icon.svg", False, "edit_split_intervention", None),
            (" Juntar", self.merge_interventions, "merge_intervention_icon.svg", False, "edit_merge_interventions", None),
            (" Copiar IN/OUT", self.copy_in_out_to_next, "copy_in_out_icon.svg", False, "edit_copy_in_out", "Copiar IN/OUT a Siguiente")
        ]
        for btn_text, method, icon_name, is_only_icon, action_obj_name, tooltip_override in actions_map:
            button = QPushButton()
            if self.get_icon and icon_name:
                button.setIcon(self.get_icon(icon_name))
                button.setIconSize(action_icon_size)
            final_tooltip = tooltip_override if tooltip_override else btn_text.strip()
            if is_only_icon:
                button.setProperty("iconOnlyButton", True)
                final_tooltip = tooltip_override if tooltip_override else method.__name__.replace("_", " ").title()
            else:
                button.setText(btn_text)
            button.setToolTip(final_tooltip)
            button.clicked.connect(method)
            actions_bar_internal_layout.addWidget(button)
            self.action_buttons[action_obj_name] = button
        buttons_overall_container_layout.addWidget(self.table_actions_widget)
        buttons_overall_container_layout.addStretch(1)
        self.error_indicators_container = QWidget()
        self.error_indicators_container.setObjectName("error_indicators_container")
        error_indicators_layout = QHBoxLayout(self.error_indicators_container)
        error_indicators_layout.setContentsMargins(0,0,0,0)
        error_indicators_layout.setSpacing(5)
        self.time_error_indicator_button = QPushButton("")
        self.time_error_indicator_button.setObjectName("timeErrorIndicatorButton")
        self.time_error_indicator_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.time_error_indicator_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.time_error_indicator_button.setVisible(False)
        self.time_error_indicator_button.clicked.connect(self.go_to_next_time_error)
        error_indicators_layout.addWidget(self.time_error_indicator_button)
        self.scene_error_indicator_button = QPushButton("")
        self.scene_error_indicator_button.setObjectName("sceneErrorIndicatorButton")
        self.scene_error_indicator_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.scene_error_indicator_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scene_error_indicator_button.setVisible(False)
        self.scene_error_indicator_button.clicked.connect(self.go_to_next_scene_error)
        error_indicators_layout.addWidget(self.scene_error_indicator_button)
        self.line_error_indicator_button = QPushButton("")
        self.line_error_indicator_button.setObjectName("lineErrorIndicatorButton")
        self.line_error_indicator_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.line_error_indicator_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.line_error_indicator_button.setVisible(False)
        self.line_error_indicator_button.clicked.connect(self.go_to_next_line_error)
        error_indicators_layout.addWidget(self.line_error_indicator_button)
        self.bookmark_indicator_button = QPushButton("")
        self.bookmark_indicator_button.setObjectName("bookmarkIndicatorButton")
        self.bookmark_indicator_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.bookmark_indicator_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.bookmark_indicator_button.setVisible(False)
        self.bookmark_indicator_button.clicked.connect(self.go_to_next_bookmark)
        error_indicators_layout.addWidget(self.bookmark_indicator_button)
        buttons_overall_container_layout.addWidget(self.error_indicators_container)
        self.link_out_in_checkbox = QCheckBox("OUT->IN")
        self.link_out_in_checkbox.setChecked(self.link_out_to_next_in_enabled)
        self.link_out_in_checkbox.setToolTip("Si está marcado, al definir un OUT también se definirá el IN de la siguiente fila.")
        self.link_out_in_checkbox.stateChanged.connect(self.toggle_link_out_to_next_in_checkbox)
        buttons_overall_container_layout.addWidget(self.link_out_in_checkbox)
        self.sync_video_checkbox = QCheckBox("Sincronizar con Video")
        self.sync_video_checkbox.setToolTip("Si está marcado, la tabla se desplazará y resaltará la fila correspondiente al tiempo del video.")
        self.sync_video_checkbox.setChecked(True)
        buttons_overall_container_layout.addWidget(self.sync_video_checkbox)
        layout.addWidget(self.top_controls_row_widget)

    def _handle_model_change_for_time_errors(self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]):
        if not top_left.isValid(): return
        if Qt.ItemDataRole.BackgroundRole in roles or Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.EditRole in roles:
            if top_left.column() <= C.VIEW_COL_OUT and bottom_right.column() >= C.VIEW_COL_IN:
                self._request_error_indicator_update()

    def update_time_error_indicator(self):
        if not hasattr(self, 'time_error_indicator_button') or self.time_error_indicator_button is None or not hasattr(self.pandas_model, '_time_validation_status'): return
        self.error_df_indices = sorted([idx for idx, status in self.pandas_model._time_validation_status.items() if status is not True])
        has_errors = bool(self.error_df_indices)
        if not has_errors: self._current_error_nav_idx = -1
        self.time_error_indicator_button.setVisible(has_errors)
        if has_errors:
            self.time_error_indicator_button.setText("⚠️ TIEMPOS")
            self.time_error_indicator_button.setProperty("hasErrors", True)
            self.time_error_indicator_button.setToolTip(f"Errores de tiempo detectados. Pulse para ir al siguiente.\nFilas: {', '.join(map(str, [i+1 for i in self.error_df_indices]))}")
        if self.time_error_indicator_button.style():
            self.time_error_indicator_button.style().unpolish(self.time_error_indicator_button)
            self.time_error_indicator_button.style().polish(self.time_error_indicator_button)

    def update_scene_error_indicator(self):
        if not hasattr(self, 'scene_error_indicator_button') or self.scene_error_indicator_button is None or not hasattr(self.pandas_model, '_scene_validation_status'): return
        self.scene_error_df_indices = sorted([idx for idx, status in self.pandas_model._scene_validation_status.items() if status is not True])
        has_errors = bool(self.scene_error_df_indices)
        if not has_errors: self._current_scene_error_nav_idx = -1
        self.scene_error_indicator_button.setVisible(has_errors)
        if has_errors:
            self.scene_error_indicator_button.setText("⚠️ ESCENAS")
            self.scene_error_indicator_button.setProperty("hasErrors", True)
            self.scene_error_indicator_button.setToolTip(f"Errores de escena detectados. Pulse para ir al siguiente.\nFilas: {', '.join(map(str, [i+1 for i in self.scene_error_df_indices]))}")
        if self.scene_error_indicator_button.style():
            self.scene_error_indicator_button.style().unpolish(self.scene_error_indicator_button)
            self.scene_error_indicator_button.style().polish(self.scene_error_indicator_button)

    def update_bookmark_indicator(self):
        if not hasattr(self, 'bookmark_indicator_button') or self.bookmark_indicator_button is None: return
        df = self.pandas_model.dataframe()
        if df.empty or C.COL_BOOKMARK not in df.columns: self.bookmark_indicator_button.setVisible(False); return
        self.bookmark_df_indices = df.index[df[C.COL_BOOKMARK]].tolist()
        num_bookmarks = len(self.bookmark_df_indices)
        self.bookmark_indicator_button.setVisible(num_bookmarks > 0)
        if num_bookmarks > 0:
            self.bookmark_indicator_button.setText(f"🔖 {num_bookmarks}")
            self.bookmark_indicator_button.setToolTip(f"{num_bookmarks} marcapáginas. Pulse para ir al siguiente.")
        if not self.bookmark_df_indices: self._current_bookmark_nav_idx = -1

    def go_to_next_bookmark(self):
        if not self.bookmark_df_indices: return
        self._current_bookmark_nav_idx = (self._current_bookmark_nav_idx + 1) % len(self.bookmark_df_indices)
        target_df_idx = self.bookmark_df_indices[self._current_bookmark_nav_idx]
        self.table_view.clearSelection(); self.table_view.selectRow(target_df_idx)
        self.table_view.scrollTo(self.pandas_model.index(target_df_idx, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table_view.setFocus()

    def go_to_next_time_error(self):
        if not self.error_df_indices: return
        self._current_error_nav_idx = (self._current_error_nav_idx + 1) % len(self.error_df_indices)
        target_df_idx = self.error_df_indices[self._current_error_nav_idx]
        error_message = self.pandas_model._time_validation_status.get(target_df_idx, "Error desconocido.")
        if error_message is True: return
        view_col_to_highlight = C.VIEW_COL_OUT if "OUT" in str(error_message) else C.VIEW_COL_IN
        self.table_view.clearSelection()
        self.table_view.selectRow(target_df_idx)
        self.table_view.setCurrentIndex(self.pandas_model.index(target_df_idx, view_col_to_highlight))
        self.table_view.scrollTo(self.pandas_model.index(target_df_idx, view_col_to_highlight), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table_view.setFocus()
        cell_index = self.pandas_model.index(target_df_idx, view_col_to_highlight)
        cell_rect = self.table_view.visualRect(cell_index)
        tooltip_pos = self.table_view.viewport().mapToGlobal(cell_rect.topLeft())
        QToolTip.showText(tooltip_pos + QPoint(0, cell_rect.height()), str(error_message), self.table_view, cell_rect, 3000)

    def go_to_next_scene_error(self):
        if not self.scene_error_df_indices: return
        self._current_scene_error_nav_idx = (self._current_scene_error_nav_idx + 1) % len(self.scene_error_df_indices)
        target_df_idx = self.scene_error_df_indices[self._current_scene_error_nav_idx]
        self.table_view.clearSelection()
        self.table_view.selectRow(target_df_idx)
        self.table_view.setCurrentIndex(self.pandas_model.index(target_df_idx, C.VIEW_COL_SCENE))
        self.table_view.scrollTo(self.pandas_model.index(target_df_idx, C.VIEW_COL_SCENE), QAbstractItemView.ScrollHint.PositionAtCenter)
        self.table_view.setFocus()
        error_message = self.pandas_model._scene_validation_status.get(target_df_idx, "Error de escena desconocido.")
        if error_message is True: return
        cell_index = self.pandas_model.index(target_df_idx, C.VIEW_COL_SCENE)
        cell_rect = self.table_view.visualRect(cell_index)
        tooltip_pos = self.table_view.viewport().mapToGlobal(cell_rect.topLeft())
        QToolTip.showText(tooltip_pos + QPoint(0, cell_rect.height()), str(error_message), self.table_view, cell_rect, 3000)

    def setup_table_view(self, layout: QVBoxLayout) -> None:
        self.table_view = CustomTableView()
        self.table_view.setModel(self.pandas_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        layout.addWidget(self.table_view)
        self.table_view.setColumnWidth(C.VIEW_COL_NUM_INTERV, 40)
        self.table_view.setColumnHidden(C.VIEW_COL_ID, True)
        self.table_view.selectionModel().selectionChanged.connect(self.update_action_buttons_state)
        time_delegate = TimeCodeDelegate(parent=self.table_view, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_IN, time_delegate)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_OUT, time_delegate)
        char_delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_CHARACTER, char_delegate)
        self.dialog_delegate = DialogDelegate(parent=self.table_view, font_size=self.current_font_size, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_DIALOGUE, self.dialog_delegate)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_EUSKERA, self.dialog_delegate)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_OHARRAK, self.dialog_delegate)
        self.table_view.cellCtrlClicked.connect(self.handle_ctrl_click_on_cell)
        self.table_view.cellAltClicked.connect(self.handle_alt_click_on_cell)
        self.pandas_model.dataChanged.connect(self.on_model_data_changed)
        self.pandas_model.layoutChanged.connect(self.on_model_layout_changed)
        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().sectionResized.connect(self.handle_column_resized)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    def show_header_context_menu(self, position: QPoint) -> None:
        menu = QMenu(self)
        header = self.table_view.horizontalHeader()
        for view_col_idx, col_view_name in enumerate(self.VIEW_COLUMN_NAMES):
            if view_col_idx == C.VIEW_COL_ID: continue
            action = QAction(col_view_name, self, checkable=True)
            action.setChecked(not self.table_view.isColumnHidden(view_col_idx))
            action.setData(view_col_idx)
            action.toggled.connect(self.toggle_column_visibility)
            menu.addAction(action)
        menu.exec(header.mapToGlobal(position))

    def toggle_column_visibility(self, checked: bool) -> None:
        action = self.sender()
        if isinstance(action, QAction) and isinstance(action.data(), int):
            self.table_view.setColumnHidden(action.data(), not checked)

    def handle_column_resized(self, logical_index: int, old_size: int, new_size: int):
        if logical_index in [C.VIEW_COL_DIALOGUE, C.VIEW_COL_EUSKERA, C.VIEW_COL_OHARRAK]:
            self.request_resize_rows_to_contents_deferred()

    def load_stylesheet(self) -> None:
        try:
            css_path = os.path.join(os.path.dirname(__file__), '..', 'styles', 'table_styles.css')
            if os.path.exists(css_path):
                with open(css_path, 'r', encoding='utf-8') as f: self.table_view.setStyleSheet(f.read())
        except Exception as e: QMessageBox.warning(self, "Error de Estilos", f"Error al cargar CSS para TableView: {str(e)}")

    def update_key_listeners(self): pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.main_window and hasattr(self.main_window, 'mark_out_hold_key_sequence'):
            current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
            if not current_mark_out_shortcut.isEmpty() and event.keyCombination() == current_mark_out_shortcut[0]:
                if not event.isAutoRepeat() and not self.f6_key_pressed_internally:
                    self.f6_key_pressed_internally = True
                    if self.video_player_widget: self.video_player_widget.handle_out_button_pressed()
                    event.accept()
                    return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if self.main_window and hasattr(self.main_window, 'mark_out_hold_key_sequence'):
            current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
            if not current_mark_out_shortcut.isEmpty() and event.keyCombination() == current_mark_out_shortcut[0]:
                if not event.isAutoRepeat() and self.f6_key_pressed_internally:
                    self.f6_key_pressed_internally = False
                    if self.video_player_widget: self.video_player_widget.handle_out_button_released()
                    event.accept()
                    return
        super().keyReleaseEvent(event)

    def _populate_header_ui(self, header_data: Dict[str, Any]):
        widgets_to_block = [self.reference_edit, self.product_edit, self.chapter_edit, self.type_combo]
        for widget in widgets_to_block: widget.blockSignals(True)
        self.reference_edit.setText(str(header_data.get("reference_number", "")))
        self.product_edit.setText(str(header_data.get("product_name", "")))
        self.chapter_edit.setText(str(header_data.get("chapter_number", "")))
        tipo = str(header_data.get("type", "Ficcion"))
        idx = self.type_combo.findText(tipo, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive)
        self.type_combo.setCurrentIndex(idx if idx != -1 else 0)
        for widget in widgets_to_block: widget.blockSignals(False)
        self._current_header_data_for_undo = self._get_header_data_from_ui()

    def _get_header_data_from_ui(self) -> Dict[str, Any]:
        return {"reference_number": self.reference_edit.text(), "product_name": self.product_edit.text(), "chapter_number": self.chapter_edit.text(), "type": self.type_combo.currentText()}

    def _post_load_script_actions(self, file_path: str, df: pd.DataFrame, header_data: Dict[str, Any]):
        self.pandas_model.set_dataframe(df)
        self._populate_header_ui(header_data)
        self.undo_stack.clear()
        self.current_script_name, self.current_script_path = os.path.basename(file_path), file_path
        if self.main_window and hasattr(self.main_window, 'add_to_recent_files'): self.main_window.add_to_recent_files(file_path)
        if self.main_window and self.main_window.statusBar(): self.main_window.statusBar().showMessage(f"Guion '{self.current_script_name}' cargado.", 5000)
        self.update_window_title()
        self.adjust_all_row_heights_and_validate()
        self._update_toggle_header_button_text_and_icon()
        self._request_error_indicator_update(); self._request_scene_error_indicator_update()
        self._request_bookmark_indicator_update(); self._request_recache_subtitles()
        self._recache_times()
    
    def open_shift_timecodes_dialog(self):
        if self.pandas_model.dataframe().empty: QMessageBox.information(self, "Desplazar Timecodes", "No hay datos en el guion para desplazar."); return
        dialog = ShiftTimecodeDialog(default_fps=int(C.FPS), get_icon_func=self.get_icon, parent=self)
        if dialog.exec():
            values = dialog.get_values()
            if values and values[1] > 0: self.undo_stack.push(ShiftTimecodesCommand(self, *values)); QMessageBox.information(self, "Éxito", "Los timecodes han sido desplazados.")

    def _generate_default_filename(self, extension: str) -> str:
        header_data = self._get_header_data_from_ui()
        product = str(header_data.get("product_name", "")).strip().replace(" ", "_")
        chapter = str(header_data.get("chapter_number", "")).strip().replace(" ", "_")
        base_name_parts = [part for part in [product, chapter] if part]
        return f"{'_'.join(base_name_parts) if base_name_parts else 'guion'}.{extension}"

    def update_action_buttons_state(self):
        selected_rows = self.table_view.selectionModel().selectedRows()
        num_selected = len(selected_rows)
        is_main_window_available = self.main_window and hasattr(self.main_window, 'actions')
        can_move, df_idx = (num_selected == 1), selected_rows[0].row() if num_selected == 1 else -1
        actions_state = {
            "edit_delete_row": num_selected > 0, "edit_toggle_bookmark": num_selected > 0,
            "edit_move_up": can_move and df_idx > 0, "edit_move_down": can_move and df_idx < self.pandas_model.rowCount() - 1,
            "edit_split_intervention": can_move, "edit_merge_interventions": num_selected >= 1,
            "edit_copy_in_out": can_move and df_idx < self.pandas_model.rowCount() - 1, "edit_increment_scene": can_move,
        }
        for name, is_enabled in actions_state.items():
            if is_main_window_available and name in self.main_window.actions: self.main_window.actions[name].setEnabled(is_enabled)
            if name in self.action_buttons: self.action_buttons[name].setEnabled(is_enabled)

    def clear_script_state(self):
        self.pandas_model.set_dataframe(pd.DataFrame(columns=self.DF_COLUMN_ORDER))
        self._populate_header_ui({})
        self.undo_stack.clear()
        self.current_script_name, self.current_script_path = None, None
        self._update_toggle_header_button_text_and_icon()
        self._request_error_indicator_update(); self._request_scene_error_indicator_update()
        self._request_bookmark_indicator_update(); self.update_window_title(); self._recache_times()

    def _perform_resize_rows_to_contents(self):
        if self.table_view.isVisible() and self.pandas_model.rowCount() > 0: self.table_view.resizeRowsToContents()
    def request_resize_rows_to_contents_deferred(self): self._resize_rows_timer.start()
    def adjust_all_row_heights_and_validate(self) -> None:
        self.request_resize_rows_to_contents_deferred()
        for row_idx in range(self.pandas_model.rowCount()):
            self.pandas_model.force_time_validation_update_for_row(row_idx)
            self.pandas_model.force_scene_validation_update_for_row(row_idx)

    def on_model_layout_changed(self): self.adjust_all_row_heights_and_validate(); self.update_character_completer_and_notify(); self._recache_times()

    def on_model_data_changed(self, top_left_index: QModelIndex, bottom_right_index: QModelIndex, roles: List[int]):
        if not top_left_index.isValid(): return
        self.set_unsaved_changes(True)
        for row in range(top_left_index.row(), bottom_right_index.row() + 1):
            df_col_name = self.pandas_model.get_df_column_name(top_left_index.column())
            if df_col_name in [C.COL_DIALOGO, C.COL_EUSKERA, C.COL_OHARRAK]: self.request_resize_rows_to_contents_deferred()
            elif df_col_name == C.COL_PERSONAJE: self.update_character_completer_and_notify()
        if top_left_index.column() <= C.VIEW_COL_OUT and bottom_right_index.column() >= C.VIEW_COL_IN:
            for row in range(top_left_index.row(), bottom_right_index.row() + 1): self._update_time_cache_for_row(row)

    def update_character_completer_and_notify(self):
        delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(C.VIEW_COL_CHARACTER, delegate)
        self.character_name_changed.emit()

    def copy_selected_time(self) -> None:
        idx = self.table_view.currentIndex()
        if idx.isValid() and idx.column() in [C.VIEW_COL_IN, C.VIEW_COL_OUT]:
            self.clipboard_text = str(self.pandas_model.data(idx, Qt.ItemDataRole.EditRole))

    def paste_time(self) -> None:
        idx = self.table_view.currentIndex()
        if self.clipboard_text and idx.isValid() and idx.column() in [C.VIEW_COL_IN, C.VIEW_COL_OUT]:
            old_value = str(self.pandas_model.data(idx, Qt.ItemDataRole.EditRole))
            if old_value != self.clipboard_text: self.undo_stack.push(EditCommand(self, idx.row(), idx.column(), old_value, self.clipboard_text))

    def adjust_dialogs(self, max_chars: int) -> None:
        if self.pandas_model.dataframe().empty: return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.undo_stack.beginMacro(f"Ajustar Diálogos ({C.COL_DIALOGO} y {C.COL_EUSKERA})")
            for col_name in [C.COL_DIALOGO, C.COL_EUSKERA]:
                view_col_idx = self.pandas_model.get_view_column_index(col_name)
                if view_col_idx is not None:
                    for df_idx in range(self.pandas_model.rowCount()):
                        original_text = str(self.pandas_model.dataframe().at[df_idx, col_name])
                        adjusted_text = ajustar_dialogo(original_text, max_chars)
                        if original_text != adjusted_text: self.undo_stack.push(EditCommand(self, df_idx, view_col_idx, original_text, adjusted_text))
            self.undo_stack.endMacro()
        finally:
            QApplication.restoreOverrideCursor()
            
        if not self.undo_stack.isClean() and self.undo_stack.command(self.undo_stack.count() - 1).text().startswith("Ajustar"):
            QMessageBox.information(self, "Éxito", "Diálogos y textos en Euskera ajustados.")
        else: QMessageBox.information(self, "Info", "No se encontraron textos que necesitaran ajuste.")

    def copy_in_out_to_next(self) -> None:
        selected_rows = self.table_view.selectionModel().selectedRows()
        if len(selected_rows) != 1: return
        df_idx_selected = selected_rows[0].row()
        if df_idx_selected >= self.pandas_model.rowCount() - 1: return
        current_df, df_idx_next = self.pandas_model.dataframe(), df_idx_selected + 1
        in_time, out_time = str(current_df.at[df_idx_selected, C.COL_IN]), str(current_df.at[df_idx_selected, C.COL_OUT])
        self.undo_stack.beginMacro("Copiar IN/OUT a Siguiente")
        old_in_next = str(current_df.at[df_idx_next, C.COL_IN])
        if in_time != old_in_next: self.undo_stack.push(EditCommand(self, df_idx_next, C.VIEW_COL_IN, old_in_next, in_time))
        old_out_next = str(current_df.at[df_idx_next, C.COL_OUT])
        if out_time != old_out_next: self.undo_stack.push(EditCommand(self, df_idx_next, C.VIEW_COL_OUT, old_out_next, out_time))
        self.undo_stack.endMacro()

    def add_new_row(self) -> None:
        selected_rows = self.table_view.selectionModel().selectedRows()
        insert_at_view_row = selected_rows[0].row() + 1 if selected_rows else self.pandas_model.rowCount()
        self.undo_stack.push(AddRowCommand(self, insert_at_view_row, insert_at_view_row))

    def remove_row(self) -> None:
        selected_rows = self.table_view.selectionModel().selectedRows()
        if not selected_rows: return
        df_indices_to_remove = sorted([index.row() for index in selected_rows])
        reply = QMessageBox.question(self, "Confirmar Eliminación", f"¿Eliminar {len(df_indices_to_remove)} fila(s)?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes: self.undo_stack.push(RemoveRowsCommand(self, df_indices_to_remove))

    def toggle_bookmark(self) -> None:
        selected_rows = self.table_view.selectionModel().selectedRows()
        if not selected_rows: return
        self.undo_stack.push(ToggleBookmarkCommand(self, sorted([index.row() for index in selected_rows])))

    def move_row_up(self) -> None:
        idx = self.table_view.currentIndex()
        if idx.isValid() and idx.row() > 0: self.undo_stack.push(MoveRowCommand(self, idx.row(), idx.row() - 1))

    def move_row_down(self) -> None:
        idx = self.table_view.currentIndex()
        if idx.isValid() and idx.row() < self.pandas_model.rowCount() - 1: self.undo_stack.push(MoveRowCommand(self, idx.row(), idx.row() + 1))

    def handle_dialog_editor_state_on_focus_out(self, text: str, cursor_pos: int, index_edited: QModelIndex):
        self.last_focused_dialog_text, self.last_focused_dialog_cursor_pos, self.last_focused_dialog_index = text, cursor_pos, index_edited

    def split_intervention(self) -> None:
        current_idx = self.table_view.currentIndex()
        if not current_idx.isValid():
            QMessageBox.warning(self, "Separar", "Por favor, seleccione una fila para separar.")
            return
        text_to_split: Optional[str] = None
        cursor_pos: int = -1
        df_col_name: Optional[str] = None
        active_editor = self.table_view.focusWidget()
        if isinstance(active_editor, CustomTextEdit) and self.table_view.state() == QAbstractItemView.State.EditingState:
            text_to_split = active_editor.toPlainText()
            cursor_pos = active_editor.textCursor().position()
            editor_index = self.table_view.indexAt(active_editor.pos())
            if editor_index.isValid():
                df_col_name = self.pandas_model.get_df_column_name(editor_index.column())
        elif self.last_focused_dialog_index and self.last_focused_dialog_index.row() == current_idx.row():
            text_to_split = self.last_focused_dialog_text
            cursor_pos = self.last_focused_dialog_cursor_pos
            df_col_name = self.pandas_model.get_df_column_name(self.last_focused_dialog_index.column())
        if text_to_split is None or cursor_pos == -1 or df_col_name not in [C.COL_DIALOGO, C.COL_EUSKERA]:
            QMessageBox.information(self, "Separar", "Para separar una intervención:\n\n1. Haz doble clic en una celda de 'DIÁLOGO' o 'EUSKERA'.\n2. Coloca el cursor en el punto exacto de la división.\n3. Pulsa el botón 'Separar' (o su atajo).\n")
            return
        self.last_focused_dialog_index = None
        if not (0 <= cursor_pos <= len(text_to_split)):
            QMessageBox.warning(self, "Separar", "La posición del cursor es inválida.")
            return
        before_text, after_text = text_to_split[:cursor_pos].strip(), text_to_split[cursor_pos:].strip()
        if not after_text:
            QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención después del cursor.")
            return
        command = SplitInterventionCommand(self, current_idx.row(), before_text, after_text, text_to_split, df_col_name)
        self.undo_stack.push(command)

    def merge_interventions(self) -> None:
        selected_rows = self.table_view.selectionModel().selectedRows()
        if not selected_rows: return
        df_idx_curr, df_idx_next = selected_rows[0].row(), selected_rows[0].row() + 1
        if df_idx_next >= self.pandas_model.rowCount(): QMessageBox.warning(self, "Juntar", "No se puede juntar la última fila."); return
        df = self.pandas_model.dataframe()
        if str(df.at[df_idx_curr, C.COL_PERSONAJE]) != str(df.at[df_idx_next, C.COL_PERSONAJE]): QMessageBox.warning(self, "Juntar", "Solo se pueden juntar intervenciones del mismo personaje."); return
        merged_dialog = f"{str(df.at[df_idx_curr, C.COL_DIALOGO])} {str(df.at[df_idx_next, C.COL_DIALOGO])}".strip()
        merged_euskera = f"{str(df.at[df_idx_curr, C.COL_EUSKERA])} {str(df.at[df_idx_next, C.COL_EUSKERA])}".strip()
        self.undo_stack.push(MergeInterventionsCommand(self, df_idx_curr, merged_dialog, merged_euskera, df_idx_next, str(df.at[df_idx_curr, C.COL_OUT])))

    def convert_time_code_to_milliseconds(self, time_code: str) -> Optional[int]:
        try:
            h, m, s, f = map(int, time_code.split(':'))
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / C.FPS) * 1000.0))
        except (ValueError, TypeError): return None

    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        if ms < 0: ms = 0
        total_seconds, rem_ms = divmod(ms, 1000)
        h, rem_seconds = divmod(total_seconds, 3600)
        m, s = divmod(rem_seconds, 60)
        f = min(int(round(rem_ms / (1000.0 / C.FPS))), int(C.FPS - 1))
        return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"

    def update_in_out_from_player(self, action_type: str, position_ms: int) -> None:
        idx = self.table_view.currentIndex()
        if not idx.isValid(): return
        time_code_str, df_row_idx = self.convert_milliseconds_to_time_code(position_ms), idx.row()
        if action_type.upper() == "IN":
            view_col, model_idx = C.VIEW_COL_IN, self.pandas_model.index(df_row_idx, C.VIEW_COL_IN)
            old_value = str(self.pandas_model.data(model_idx, Qt.ItemDataRole.EditRole))
            if time_code_str != old_value: self.undo_stack.push(EditCommand(self, df_row_idx, view_col, old_value, time_code_str))
        elif action_type.upper() == "OUT":
            if not self._is_marking_out:
                self._is_marking_out = True
                self._out_mark_original_value = str(self.pandas_model.data(self.pandas_model.index(df_row_idx, C.VIEW_COL_OUT), Qt.ItemDataRole.EditRole))
                self._out_mark_df_row_idx = df_row_idx
            self._out_mark_final_value = time_code_str

    def toggle_link_out_to_next_in_checkbox(self, state: int): self.link_out_to_next_in_enabled = (Qt.CheckState(state) == Qt.CheckState.Checked)

    def select_next_row_after_out_release(self) -> None:
        if self._is_marking_out:
            if self._out_mark_original_value != self._out_mark_final_value:
                self.undo_stack.push(EditCommand(self, self._out_mark_df_row_idx, C.VIEW_COL_OUT, self._out_mark_original_value, self._out_mark_final_value))
            self._is_marking_out, self._out_mark_original_value, self._out_mark_final_value, self._out_mark_df_row_idx = False, None, None, -1
        idx = self.table_view.currentIndex()
        if not idx.isValid(): return
        next_row = idx.row() + 1
        if next_row >= self.pandas_model.rowCount(): return
        self.table_view.selectRow(next_row)
        self.table_view.scrollTo(self.pandas_model.index(next_row, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        if self.link_out_to_next_in_enabled:
            out_time, old_in_next = str(self.pandas_model.dataframe().at[idx.row(), C.COL_OUT]), str(self.pandas_model.dataframe().at[next_row, C.COL_IN])
            if out_time != old_in_next: self.undo_stack.push(EditCommand(self, next_row, C.VIEW_COL_IN, old_in_next, out_time))

    def change_scene(self) -> None:
        idx = self.table_view.currentIndex()
        if idx.isValid(): self.undo_stack.push(ChangeSceneCommand(self, idx.row()))

    def has_scene_numbers(self) -> bool:
        df = self.pandas_model.dataframe()
        if df.empty or C.COL_SCENE not in df.columns: return False
        unique_scenes = set(str(s).strip() for s in df[C.COL_SCENE].unique() if pd.notna(s) and str(s).strip())
        return len(unique_scenes) > 1 or (len(unique_scenes) == 1 and ("1" not in unique_scenes))

    def handle_ctrl_click_on_cell(self, view_row_idx: int) -> None:
        if 0 <= view_row_idx < self.pandas_model.rowCount():
            in_tc = str(self.pandas_model.dataframe().at[view_row_idx, C.COL_IN])
            ms = self.convert_time_code_to_milliseconds(in_tc)
            if ms is not None: self.in_out_signal.emit("IN", ms)

    def handle_alt_click_on_cell(self, view_row_idx: int) -> None:
        if 0 <= view_row_idx < self.pandas_model.rowCount():
            out_tc = str(self.pandas_model.dataframe().at[view_row_idx, C.COL_OUT])
            ms = self.convert_time_code_to_milliseconds(out_tc)
            if ms is not None: self.in_out_signal.emit("OUT", ms)

    def _recache_times(self):
        self._time_cache.clear()
        df = self.pandas_model.dataframe()
        if df.empty: return
        for position in range(len(df)):
            in_tc = df.iloc[position][C.COL_IN]
            start_ms = self.convert_time_code_to_milliseconds(str(in_tc))
            if start_ms is not None: self._time_cache.append((start_ms, position))
        self._time_cache.sort(key=lambda x: x[0])

    def _update_time_cache_for_row(self, df_row_idx: int):
        self._time_cache = [item for item in self._time_cache if item[1] != df_row_idx]
        current_df = self.pandas_model.dataframe()
        if df_row_idx >= len(current_df): return
        new_in_tc = str(current_df.iloc[df_row_idx][C.COL_IN])
        new_start_ms = self.convert_time_code_to_milliseconds(new_in_tc)
        if new_start_ms is not None: bisect.insort(self._time_cache, (new_start_ms, df_row_idx))

    def sync_with_video_position(self, position_ms: int):
        if self._is_marking_out or not self.sync_video_checkbox.isChecked() or not self._time_cache: return
        insertion_point = bisect.bisect_right([item[0] for item in self._time_cache], position_ms)
        active_row_index = -1
        if insertion_point > 0:
            candidate_start_ms, candidate_row_index = self._time_cache[insertion_point - 1]
            current_df = self.pandas_model.dataframe()
            if candidate_row_index < len(current_df):
                out_tc = current_df.iloc[candidate_row_index][C.COL_OUT]
                end_ms = self.convert_time_code_to_milliseconds(str(out_tc))
                if end_ms is not None and candidate_start_ms <= position_ms < end_ms: active_row_index = candidate_row_index
        if active_row_index != self._currently_synced_row:
            self._currently_synced_row = active_row_index
            self.table_view.selectionModel().clear()
            if active_row_index != -1:
                self.table_view.selectRow(active_row_index)
                self.table_view.scrollTo(self.pandas_model.index(active_row_index, 0), QAbstractItemView.ScrollHint.PositionAtCenter)

    def get_character_names_from_model(self) -> List[str]:
        df = self.pandas_model.dataframe()
        if df.empty or C.COL_PERSONAJE not in df.columns: return []
        return sorted(list(set(str(name).strip() for name in df[C.COL_PERSONAJE].unique() if pd.notna(name) and str(name).strip())))

    def update_multiple_character_names(self, old_names_list: List[str], new_name: str):
        if not new_name.strip(): QMessageBox.warning(self, "Nombre Inválido", "El nombre del personaje no puede estar vacío."); return
        self.undo_stack.push(UpdateMultipleCharactersCommand(self, old_names_list, new_name))

    def trim_all_character_names(self):
        df = self.pandas_model.dataframe()
        if df.empty or C.COL_PERSONAJE not in df.columns: return
        if not (df[C.COL_PERSONAJE].astype(str) != df[C.COL_PERSONAJE].astype(str).str.strip()).any():
            QMessageBox.information(self, "Limpiar Nombres", "No se encontraron nombres que necesiten limpieza."); return
        self.undo_stack.push(TrimAllCharactersCommand(self))
        QMessageBox.information(self, "Limpieza Completa", "Se han limpiado los espacios sobrantes de los nombres de personaje.")

    def find_and_replace(self, find_text: str, replace_text: str, search_in_character: bool, search_in_dialogue: bool, search_in_euskera: bool) -> None:
        if self.pandas_model.dataframe().empty or not find_text: return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        changed_count = 0
        try:
            self.undo_stack.beginMacro("Buscar y Reemplazar Todo")
            cols_to_search = []
            if search_in_character: cols_to_search.append(C.COL_PERSONAJE)
            if search_in_dialogue: cols_to_search.append(C.COL_DIALOGO)
            if search_in_euskera: cols_to_search.append(C.COL_EUSKERA)
            
            for col_name in cols_to_search:
                view_col_idx = self.pandas_model.get_view_column_index(col_name)
                if view_col_idx is not None:
                    for df_idx in range(self.pandas_model.rowCount()):
                        original_text = str(self.pandas_model.dataframe().at[df_idx, col_name])
                        new_text, num_subs = re.subn(re.escape(find_text), replace_text, original_text, flags=re.IGNORECASE)
                        if num_subs > 0: 
                            self.undo_stack.push(EditCommand(self, df_idx, view_col_idx, original_text, new_text))
                            changed_count += num_subs
            self.undo_stack.endMacro()
        finally:
            QApplication.restoreOverrideCursor()
            
        QMessageBox.information(self, "Reemplazar Todo", f"{changed_count} reemplazo(s) realizado(s).")

    def replace_in_current_match(self, df_idx: int, find_text: str, replace_text: str, in_char: bool, in_dialogue: bool, in_euskera: bool) -> bool:
        if self.pandas_model.dataframe().empty or not find_text or not (0 <= df_idx < self.pandas_model.rowCount()): return False
        cols_to_check = []
        if in_char: cols_to_check.append(C.COL_PERSONAJE)
        if in_dialogue: cols_to_check.append(C.COL_DIALOGO)
        if in_euskera: cols_to_check.append(C.COL_EUSKERA)
        for col_name in cols_to_check:
            original_text = str(self.pandas_model.dataframe().at[df_idx, col_name])
            if re.search(re.escape(find_text), original_text, flags=re.IGNORECASE):
                new_text, _ = re.subn(re.escape(find_text), replace_text, original_text, count=1, flags=re.IGNORECASE)
                view_col_idx = self.pandas_model.get_view_column_index(col_name)
                if view_col_idx is not None: self.undo_stack.push(EditCommand(self, df_idx, view_col_idx, original_text, new_text)); return True
        return False

    def update_window_title(self) -> None:
        prefix = "*" if self.unsaved_changes else ""
        script_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window: self.main_window.setWindowTitle(f"{prefix}Editor Guion - {script_name}")

    def set_unsaved_changes(self, changed: bool):
        if self.unsaved_changes != changed: self.unsaved_changes = changed; self.update_window_title()

    def get_next_id(self) -> int: return self.pandas_model.get_next_id()
    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]: return self.pandas_model.find_df_index_by_id(id_value)
    def get_dataframe_column_name(self, table_col_index: int) -> Optional[str]: return self.pandas_model.get_df_column_name(table_col_index)
    def handle_exception(self, exception: Exception, message: str) -> None: import traceback; QMessageBox.critical(self, "Error", f"{message}:\n{str(exception)}")

    def apply_font_size_to_dialogs(self, font_size: int) -> None:
        self.current_font_size = font_size
        if hasattr(self, 'dialog_delegate'): self.dialog_delegate.setFontSize(font_size)
        font = self.table_view.font(); font.setPointSize(font_size); self.table_view.setFont(font)
        header = self.table_view.horizontalHeader(); header_font = header.font(); header_font.setPointSize(font_size); header.setFont(header_font)

    def _check_header_fields_completeness(self) -> bool:
        if hasattr(self, 'reference_edit'): return all(w.text().strip() for w in [self.reference_edit, self.product_edit, self.chapter_edit])
        return True

    def _update_toggle_header_button_text_and_icon(self):
        if not hasattr(self, 'toggle_header_button'): return
        is_visible = self.header_details_widget.isVisible()
        text, icon = (" Ocultar Detalles del Guion", self.icon_expand_less) if is_visible else (" Mostrar Detalles del Guion", self.icon_expand_more)
        if not is_visible and not self._check_header_fields_completeness(): text += " (Campos Incompletos)"
        self.toggle_header_button.setText(text)
        if self.get_icon: self.toggle_header_button.setIcon(icon)

    def convert_all_characters_to_uppercase(self):
        if self.pandas_model.dataframe().empty: return
        self.undo_stack.beginMacro("Convertir Personajes a Mayúsculas")
        view_col_char = self.pandas_model.get_view_column_index(C.COL_PERSONAJE)
        if view_col_char is not None:
            for df_idx in range(self.pandas_model.rowCount()):
                old_name = str(self.pandas_model.dataframe().at[df_idx, C.COL_PERSONAJE])
                new_name = old_name.upper()
                if old_name != new_name: self.undo_stack.push(EditCommand(self, df_idx, view_col_char, old_name, new_name))
        self.undo_stack.endMacro()
        if not self.undo_stack.isClean() and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Convertir"):
            QMessageBox.information(self, "Información", "Todos los nombres de personaje ya estaban en mayúsculas.")

    def split_character_rows(self, old_name: str, new_name1: str, new_name2: str):
        if not all([old_name, new_name1, new_name2]): QMessageBox.warning(self, "Error", "Los nombres de personaje no pueden estar vacíos."); return
        self.undo_stack.push(SplitCharacterCommand(self, old_name, new_name1, new_name2))

    def reset_all_scenes(self):
        if self.pandas_model.dataframe().empty: return
        reply = QMessageBox.question(self, "Confirmar Acción", "¿Cambiar TODAS las escenas a '1'?\n(Se puede deshacer con Ctrl+Z)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.undo_stack.push(ResetScenesCommand(self))

    def reset_all_timecodes(self):
        if self.pandas_model.dataframe().empty: return
        reply = QMessageBox.question(self, "Confirmar Acción", "¿Reiniciar TODOS los IN/OUT a 00:00:00:00?\n(Se puede deshacer con Ctrl+Z)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: self.undo_stack.push(ResetTimecodesCommand(self))

    def delete_all_interventions_by_character(self, character_name: str):
        df = self.pandas_model.dataframe()
        if df.empty: return
        indices_to_remove = df.index[df[C.COL_PERSONAJE] == character_name].tolist()
        if not indices_to_remove: QMessageBox.information(self, "Eliminar Personaje", f"No se encontraron intervenciones para '{character_name}'."); return
        reply = QMessageBox.question(self, "Confirmar Eliminación Masiva", f"¿Eliminar las {len(indices_to_remove)} intervenciones de '{character_name}'?\n(Reversible con Ctrl+Z)", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes: self.undo_stack.push(RemoveRowsCommand(self, indices_to_remove))

    def copy_in_to_previous_out(self):
        if self.pandas_model.dataframe().empty: QMessageBox.information(self, "Operación no posible", "No hay datos en el guion."); return
        reply = QMessageBox.question(self, "Confirmar Operación", "Esto sobrescribirá todos los valores de la columna 'OUT' (excepto el de la última fila) con los valores 'IN' de la fila siguiente.\n\n¿Desea continuar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Yes:
            self.undo_stack.push(CopyInToPreviousOutCommand(self))
            QMessageBox.information(self, "Éxito", "Los tiempos OUT han sido actualizados.")

    def get_ui_states(self) -> Dict[str, bool]:
        """Devuelve el estado actual de los widgets de control de la UI."""
        return {
            "link_out_in_enabled": self.link_out_in_checkbox.isChecked(),
            "sync_video_enabled": self.sync_video_checkbox.isChecked()
        }

    def set_ui_states(self, states: Dict[str, bool]):
        """Establece el estado de los widgets de control de la UI a partir de un diccionario."""
        self.link_out_in_checkbox.setChecked(states.get("link_out_in_enabled", True))
        self.sync_video_checkbox.setChecked(states.get("sync_video_enabled", True))