# guion_editor/widgets/table_window.py

import json
import os
import re 
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize, QModelIndex, QTimer, QKeyCombination, QPoint
from PyQt6.QtGui import QFont, QColor, QIntValidator, QBrush, QIcon, QKeyEvent, QKeySequence, QAction
from PyQt6.QtWidgets import (
    QWidget, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QInputDialog, QCheckBox, QMenu, QSizePolicy
)
from PyQt6.QtGui import QUndoStack

from guion_editor.widgets.custom_table_view import CustomTableView
from guion_editor.models.pandas_table_model import PandasTableModel, ROW_NUMBER_COL_IDENTIFIER
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.delegates.guion_delegate import DialogDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.utils.guion_manager import GuionManager
from guion_editor.widgets.custom_text_edit import CustomTextEdit
from guion_editor.commands.undo_commands import (
    EditCommand, AddRowCommand, RemoveRowsCommand, MoveRowCommand, 
    SplitInterventionCommand, MergeInterventionsCommand, ChangeSceneCommand, HeaderEditCommand
)


class TableWindow(QWidget):
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    # -> INICIO: CONSTANTES DE COLUMNA ACTUALIZADAS
    COL_NUM_INTERV_VIEW = 0
    COL_ID_VIEW = 1         
    COL_SCENE_VIEW = 2      
    COL_IN_VIEW = 3         
    COL_OUT_VIEW = 4        
    COL_CHARACTER_VIEW = 5  
    COL_DIALOGUE_VIEW = 6   
    COL_EUSKERA_VIEW = 7 
    COL_OHARRAK_VIEW = 8 # Nueva columna

    VIEW_COLUMN_NAMES = ["Nº", "ID", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO", "EUSKERA", "OHARRAK"] 
    
    VIEW_TO_DF_COL_MAP = {
        COL_NUM_INTERV_VIEW: ROW_NUMBER_COL_IDENTIFIER,
        COL_ID_VIEW: 'ID', 
        COL_SCENE_VIEW: 'SCENE', 
        COL_IN_VIEW: 'IN',
        COL_OUT_VIEW: 'OUT', 
        COL_CHARACTER_VIEW: 'PERSONAJE', 
        COL_DIALOGUE_VIEW: 'DIÁLOGO',
        COL_EUSKERA_VIEW: 'EUSKERA',
        COL_OHARRAK_VIEW: 'OHARRAK' # Nuevo mapeo
    }
    DF_COLUMN_ORDER = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA', 'OHARRAK']
    # -> FIN: CONSTANTES DE COLUMNA ACTUALIZADAS

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None,
                 guion_manager: Optional[GuionManager] = None, get_icon_func=None):
        super().__init__()
        
        # 1. Inicializar estado interno (variables, modelos)
        self._init_internal_state(video_player_widget, main_window, guion_manager, get_icon_func)
        
        # 2. Inicializar temporizadores
        self._init_timers()

        # 3. Configurar la interfaz de usuario
        self.setup_ui()
        self.update_action_buttons_state()

        # 4. Conectar todas las señales y slots
        self._connect_signals()

        # 5. Establecer el estado final inicial
        self.clear_script_state()
        self.update_window_title()
        QTimer.singleShot(0, lambda: self.table_view.setColumnHidden(self.COL_EUSKERA_VIEW, True))
        
    def _init_internal_state(self, video_player_widget, main_window, guion_manager, get_icon_func):
        """Inicializa las variables de estado, modelos y referencias."""
        self.get_icon = get_icon_func
        self.main_window = main_window 
        self.video_player_widget = video_player_widget
        self.guion_manager = guion_manager if guion_manager else GuionManager()

        self.current_font_size = 9
        self.f6_key_pressed_internally = False 
        self.action_buttons = {}
        
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.pandas_model = PandasTableModel(column_map=self.VIEW_TO_DF_COL_MAP,
                                             view_column_names=self.VIEW_COLUMN_NAMES)
        
        self.unsaved_changes = False
        self.undo_stack = QUndoStack(self)
        self.current_script_name: Optional[str] = None
        self.current_script_path: Optional[str] = None
        self.clipboard_text: str = "" 

        self.link_out_to_next_in_enabled = True

        self.last_focused_dialog_text: Optional[str] = None
        self.last_focused_dialog_cursor_pos: int = -1
        self.last_focused_dialog_index: Optional[QModelIndex] = None
        
        # -> INICIO: SOLUCIÓN DEL ERROR
        # Inicializamos la columna de origen de subtítulos con un valor por defecto.
        self.subtitle_source_column = 'DIÁLOGO'
        # -> FIN: SOLUCIÓN DEL ERROR

        if self.get_icon:
            self.icon_expand_less = self.get_icon("toggle_header_collapse_icon.svg")
            self.icon_expand_more = self.get_icon("toggle_header_expand_icon.svg")
        else:
            self.icon_expand_less, self.icon_expand_more = QIcon(), QIcon()

        self.time_error_indicator_button: Optional[QPushButton] = None
        self.error_df_indices: List[int] = []
        self._current_error_nav_idx: int = -1

        self.scene_error_indicator_button: Optional[QPushButton] = None
        self.scene_error_df_indices: List[int] = []
        self._current_scene_error_nav_idx: int = -1
        
        self._current_header_data_for_undo: Dict[str, Any] = {}
        self.cached_subtitle_timeline: List[Tuple[int, int, str]] = []

    def _init_timers(self):
        """Configura todos los QTimer para operaciones diferidas."""
        self._resize_rows_timer = QTimer(self)
        self._resize_rows_timer.setSingleShot(True)
        self._resize_rows_timer.setInterval(100) 

        self._update_error_indicator_timer = QTimer(self)
        self._update_error_indicator_timer.setSingleShot(True)
        self._update_error_indicator_timer.setInterval(0)

        self._update_scene_error_indicator_timer = QTimer(self)
        self._update_scene_error_indicator_timer.setSingleShot(True)
        self._update_scene_error_indicator_timer.setInterval(0)
        
        self._recache_timer = QTimer(self)
        self._recache_timer.setSingleShot(True)
        self._recache_timer.setInterval(150)

        self._header_change_timer: Optional[QTimer] = None

    def _connect_signals(self):
        """Centraliza todas las conexiones de señales y slots."""
        # Conexiones de Timers
        self._resize_rows_timer.timeout.connect(self._perform_resize_rows_to_contents)
        self._update_error_indicator_timer.timeout.connect(self.update_time_error_indicator)
        self._update_scene_error_indicator_timer.timeout.connect(self.update_scene_error_indicator)
        self._recache_timer.timeout.connect(self._recache_subtitle_timeline)
        
        # Conexiones del Video Player
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out_from_player) 
            self.video_player_widget.out_released.connect(self.select_next_row_after_out_release)

        # Conexiones del Modelo
        self.pandas_model.dataChanged.connect(self._request_error_indicator_update) 
        self.pandas_model.layoutChanged.connect(self._request_error_indicator_update) 
        self.pandas_model.modelReset.connect(self._request_error_indicator_update) 

        self.pandas_model.dataChanged.connect(self._request_scene_error_indicator_update)
        self.pandas_model.layoutChanged.connect(self._request_scene_error_indicator_update)
        self.pandas_model.modelReset.connect(self._request_scene_error_indicator_update)
        
        self.pandas_model.dataChanged.connect(self._request_recache_subtitles)
        self.pandas_model.layoutChanged.connect(self._request_recache_subtitles)
        self.pandas_model.modelReset.connect(self._request_recache_subtitles)
        
        self.pandas_model.dataChanged.connect(self.on_model_data_changed)
        self.pandas_model.layoutChanged.connect(self.on_model_layout_changed)

        # Conexiones del Stack de Deshacer/Rehacer
        self.undo_stack.canUndoChanged.connect(self._update_undo_action_state)
        self.undo_stack.canRedoChanged.connect(self._update_redo_action_state)
        self.undo_stack.cleanChanged.connect(self._handle_clean_changed)

    def _update_undo_action_state(self, can_undo: bool):
        if self.main_window and hasattr(self.main_window, 'actions') and "edit_undo" in self.main_window.actions:
            self.main_window.actions["edit_undo"].setEnabled(can_undo)

    def _update_redo_action_state(self, can_redo: bool):
        if self.main_window and hasattr(self.main_window, 'actions') and "edit_redo" in self.main_window.actions:
            self.main_window.actions["edit_redo"].setEnabled(can_redo)

    def _handle_clean_changed(self, is_clean: bool):
        self.set_unsaved_changes(not is_clean)

    def _request_error_indicator_update(self):
        self._update_error_indicator_timer.start()
    
    def _request_scene_error_indicator_update(self):
        self._update_scene_error_indicator_timer.start()

    def _request_recache_subtitles(self):
        self._recache_timer.start()

    def _recache_subtitle_timeline(self):
        self.cached_subtitle_timeline.clear()
        df = self.pandas_model.dataframe()
        if df.empty or self.subtitle_source_column not in df.columns:
            return
            
        for i in range(len(df)):
            try:
                in_tc = str(df.at[i, 'IN'])
                out_tc = str(df.at[i, 'OUT'])
                # Utiliza la columna de origen almacenada
                subtitle_text = str(df.at[i, self.subtitle_source_column])
                
                in_ms = self.convert_time_code_to_milliseconds(in_tc)
                out_ms = self.convert_time_code_to_milliseconds(out_tc)
                
                if in_ms < out_ms:
                    self.cached_subtitle_timeline.append((in_ms, out_ms, subtitle_text))
            except (KeyError, ValueError, TypeError) as e:
                print(f"Advertencia: Omitiendo fila {i} del caché de subtítulos por error: {e}")
                continue
        
        self.cached_subtitle_timeline.sort(key=lambda x: x[0])

    def trigger_recache_with_source(self, source_column: str):
        """
        Actualiza la columna de origen para los subtítulos y solicita un recacheo.
        """
        if source_column in self.DF_COLUMN_ORDER:
            self.subtitle_source_column = source_column
            self._request_recache_subtitles()


    def get_subtitle_timeline(self) -> List[Tuple[int, int, str]]:
        return self.cached_subtitle_timeline


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
        current_visibility = self.header_details_widget.isVisible()
        self.header_details_widget.setVisible(not current_visibility)
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

            final_tooltip = tooltip_override
            if is_only_icon:
                button.setProperty("iconOnlyButton", True) 
                if not final_tooltip: 
                    final_tooltip = method.__name__.replace("_", " ").title()
            else:
                button.setText(btn_text)
                if not final_tooltip:
                    final_tooltip = btn_text.strip()
            
            if final_tooltip:
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
        
        buttons_overall_container_layout.addWidget(self.error_indicators_container)

        self.link_out_in_checkbox = QCheckBox("OUT->IN")
        self.link_out_in_checkbox.setChecked(self.link_out_to_next_in_enabled)
        self.link_out_in_checkbox.setToolTip("Si está marcado, al definir un OUT también se definirá el IN de la siguiente fila.")
        self.link_out_in_checkbox.stateChanged.connect(self.toggle_link_out_to_next_in_checkbox)
        buttons_overall_container_layout.addWidget(self.link_out_in_checkbox)

        layout.addWidget(self.top_controls_row_widget)

    def _handle_model_change_for_time_errors(self, top_left: QModelIndex, bottom_right: QModelIndex, roles: list[int]):
        if not top_left.isValid(): return

        col_in_view = self.COL_IN_VIEW
        col_out_view = self.COL_OUT_VIEW
        
        update_needed = False
        if Qt.ItemDataRole.BackgroundRole in roles or Qt.ItemDataRole.DisplayRole in roles or Qt.ItemDataRole.EditRole in roles:
            for col_idx in range(top_left.column(), bottom_right.column() + 1):
                if col_idx == col_in_view or col_idx == col_out_view:
                    update_needed = True
                    break
        
        if update_needed:
            self._request_error_indicator_update()

    def update_time_error_indicator(self):
        if not hasattr(self, 'time_error_indicator_button') or self.time_error_indicator_button is None: 
            return
        if not hasattr(self.pandas_model, '_time_validation_status'):
            return

        has_errors = False
        error_rows_interventions_str = [] 
        old_error_count = len(self.error_df_indices)
        self.error_df_indices.clear()

        if self.pandas_model.rowCount() > 0 and isinstance(self.pandas_model._time_validation_status, dict):
            for df_row_idx, is_valid in sorted(list(self.pandas_model._time_validation_status.items())):
                if not is_valid:
                    has_errors = True
                    self.error_df_indices.append(df_row_idx) 
                    error_rows_interventions_str.append(str(df_row_idx + 1)) 
        if len(self.error_df_indices) != old_error_count or not self.error_df_indices:
            self._current_error_nav_idx = -1 
        elif self.error_df_indices and self._current_error_nav_idx >= len(self.error_df_indices):
             self._current_error_nav_idx = len(self.error_df_indices) -1 

        if has_errors:
            self.time_error_indicator_button.setText("⚠️ TIEMPOS")
            self.time_error_indicator_button.setProperty("hasErrors", True)
            
            tooltip_text = "Errores de tiempo detectados. Pulse para ir al siguiente.\nFilas con errores: " + ", ".join(error_rows_interventions_str)
            self.time_error_indicator_button.setToolTip(tooltip_text)
            self.time_error_indicator_button.setVisible(True)
            self.time_error_indicator_button.setEnabled(True)
        else:
            self.time_error_indicator_button.setText("") 
            self.time_error_indicator_button.setProperty("hasErrors", False)
            self.time_error_indicator_button.setToolTip("")
            self.time_error_indicator_button.setVisible(False)
            self.time_error_indicator_button.setEnabled(False)
            self._current_error_nav_idx = -1 

        if self.time_error_indicator_button.style() is not None:
            self.time_error_indicator_button.style().unpolish(self.time_error_indicator_button)
            self.time_error_indicator_button.style().polish(self.time_error_indicator_button)

    def update_scene_error_indicator(self):
        if not hasattr(self, 'scene_error_indicator_button') or self.scene_error_indicator_button is None:
            return
        if not hasattr(self.pandas_model, '_scene_validation_status'):
            return

        has_errors = False
        error_rows_interventions_str = []
        old_error_count = len(self.scene_error_df_indices)
        self.scene_error_df_indices.clear()

        if self.pandas_model.rowCount() > 0 and isinstance(self.pandas_model._scene_validation_status, dict):
            for df_row_idx, is_valid in sorted(list(self.pandas_model._scene_validation_status.items())):
                if not is_valid:
                    has_errors = True
                    self.scene_error_df_indices.append(df_row_idx)
                    error_rows_interventions_str.append(str(df_row_idx + 1))
        
        if len(self.scene_error_df_indices) != old_error_count or not self.scene_error_df_indices:
            self._current_scene_error_nav_idx = -1
        elif self.scene_error_df_indices and self._current_scene_error_nav_idx >= len(self.scene_error_df_indices):
            self._current_scene_error_nav_idx = len(self.scene_error_df_indices) - 1

        if has_errors:
            self.scene_error_indicator_button.setText("⚠️ ESCENAS")
            self.scene_error_indicator_button.setProperty("hasErrors", True)
            tooltip_text = "Errores de escena detectados. Pulse para ir al siguiente.\nFilas con errores: " + ", ".join(error_rows_interventions_str)
            self.scene_error_indicator_button.setToolTip(tooltip_text)
            self.scene_error_indicator_button.setVisible(True)
            self.scene_error_indicator_button.setEnabled(True)
        else:
            self.scene_error_indicator_button.setText("")
            self.scene_error_indicator_button.setProperty("hasErrors", False)
            self.scene_error_indicator_button.setToolTip("")
            self.scene_error_indicator_button.setVisible(False)
            self.scene_error_indicator_button.setEnabled(False)
            self._current_scene_error_nav_idx = -1
        
        if self.scene_error_indicator_button.style() is not None:
            self.scene_error_indicator_button.style().unpolish(self.scene_error_indicator_button)
            self.scene_error_indicator_button.style().polish(self.scene_error_indicator_button)


    def go_to_next_time_error(self):
        if not self.error_df_indices: 
            self._current_error_nav_idx = -1
            return

        self._current_error_nav_idx += 1
        if self._current_error_nav_idx >= len(self.error_df_indices):
            self._current_error_nav_idx = 0 
        
        if 0 <= self._current_error_nav_idx < len(self.error_df_indices):
            target_df_idx = self.error_df_indices[self._current_error_nav_idx]
            
            if 0 <= target_df_idx < self.pandas_model.rowCount():
                self.table_view.clearSelection() 
                self.table_view.selectRow(target_df_idx)
                
                col_to_focus = self.COL_IN_VIEW 
                model_idx_to_scroll = self.pandas_model.index(target_df_idx, col_to_focus)
                if model_idx_to_scroll.isValid():
                    self.table_view.scrollTo(model_idx_to_scroll, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.table_view.setFocus()
    
    def go_to_next_scene_error(self):
        if not self.scene_error_df_indices:
            self._current_scene_error_nav_idx = -1
            return

        self._current_scene_error_nav_idx += 1
        if self._current_scene_error_nav_idx >= len(self.scene_error_df_indices):
            self._current_scene_error_nav_idx = 0
        
        if 0 <= self._current_scene_error_nav_idx < len(self.scene_error_df_indices):
            target_df_idx = self.scene_error_df_indices[self._current_scene_error_nav_idx]

            if 0 <= target_df_idx < self.pandas_model.rowCount():
                self.table_view.clearSelection()
                self.table_view.selectRow(target_df_idx)

                col_to_focus = self.COL_SCENE_VIEW
                model_idx_to_scroll = self.pandas_model.index(target_df_idx, col_to_focus)
                if model_idx_to_scroll.isValid():
                    self.table_view.scrollTo(model_idx_to_scroll, QAbstractItemView.ScrollHint.PositionAtCenter)
                self.table_view.setFocus()

    def setup_table_view(self, layout: QVBoxLayout) -> None:
        self.table_view = CustomTableView()
        self.table_view.setModel(self.pandas_model)
        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table_view.setAlternatingRowColors(True)
        layout.addWidget(self.table_view)

        self.table_view.setColumnWidth(self.COL_NUM_INTERV_VIEW, 40) 
        self.table_view.setColumnHidden(self.COL_ID_VIEW, True) 
        self.table_view.selectionModel().selectionChanged.connect(self.update_action_buttons_state)

        # -> MODIFICADO: Pasar la instancia de TableWindow a los delegados
        time_delegate = TimeCodeDelegate(self.table_view, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(self.COL_IN_VIEW, time_delegate)
        self.table_view.setItemDelegateForColumn(self.COL_OUT_VIEW, time_delegate)
        
        char_delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, char_delegate)

        self.dialog_delegate = DialogDelegate(parent=self.table_view, font_size=self.current_font_size, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(self.COL_DIALOGUE_VIEW, self.dialog_delegate)
        self.table_view.setItemDelegateForColumn(self.COL_EUSKERA_VIEW, self.dialog_delegate)
        self.table_view.setItemDelegateForColumn(self.COL_OHARRAK_VIEW, self.dialog_delegate)

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
            if view_col_idx == self.COL_ID_VIEW:
                continue 

            action = QAction(col_view_name, self, checkable=True)
            action.setChecked(not self.table_view.isColumnHidden(view_col_idx))
            action.setData(view_col_idx)
            action.toggled.connect(self.toggle_column_visibility)
            menu.addAction(action)

        menu.exec(header.mapToGlobal(position))

    def toggle_column_visibility(self, checked: bool) -> None:
        action = self.sender() 
        if isinstance(action, QAction):
            view_col_idx = action.data() 
            if isinstance(view_col_idx, int):
                self.table_view.setColumnHidden(view_col_idx, not checked)

    def handle_column_resized(self, logical_index: int, old_size: int, new_size: int):
        # -> AÑADIDO: Redimensionar filas si se cambia el ancho de Oharrak
        if logical_index in [self.COL_DIALOGUE_VIEW, self.COL_EUSKERA_VIEW, self.COL_OHARRAK_VIEW]:
            self.request_resize_rows_to_contents_deferred()

    def load_stylesheet(self) -> None:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')
            
            if not os.path.exists(css_path):
                alt_css_path = os.path.join(os.path.dirname(current_file_dir), 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    return

            with open(css_path, 'r', encoding='utf-8') as f:
                self.table_view.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar CSS para TableView: {str(e)}")

    def update_key_listeners(self):
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence'): 
            super().keyPressEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
            
        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            if event.keyCombination() == current_mark_out_shortcut[0]: 
                key_match = True
        
        if key_match and not event.isAutoRepeat() and not self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = True
            if self.video_player_widget and hasattr(self.video_player_widget, 'handle_out_button_pressed'):
                self.video_player_widget.handle_out_button_pressed()
            event.accept()
            return
        
        super().keyPressEvent(event)


    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence') or not self.video_player_widget:
            super().keyReleaseEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence

        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            if event.keyCombination() == current_mark_out_shortcut[0]: 
                key_match = True

        if key_match and not event.isAutoRepeat() and self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = False
            if hasattr(self.video_player_widget, 'handle_out_button_released'): 
                self.video_player_widget.handle_out_button_released()
            event.accept()
            return
        
        super().keyReleaseEvent(event)

    def _populate_header_ui(self, header_data: Dict[str, Any]):
        widgets_to_block = [self.reference_edit, self.product_edit, self.chapter_edit, self.type_combo]
        for widget in widgets_to_block:
            widget.blockSignals(True)

        self.reference_edit.setText(str(header_data.get("reference_number", "")))
        self.product_edit.setText(str(header_data.get("product_name", "")))
        self.chapter_edit.setText(str(header_data.get("chapter_number", "")))
        tipo = str(header_data.get("type", "Ficcion"))
        idx = self.type_combo.findText(tipo, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive)
        self.type_combo.setCurrentIndex(idx if idx != -1 else 0)

        for widget in widgets_to_block:
            widget.blockSignals(False)
        
        self._current_header_data_for_undo = self._get_header_data_from_ui()

    def _get_header_data_from_ui(self) -> Dict[str, Any]:
        return {
            "reference_number": self.reference_edit.text(), "product_name": self.product_edit.text(),
            "chapter_number": self.chapter_edit.text(), "type": self.type_combo.currentText()
        }

    def _post_load_script_actions(self, file_path: str, df: pd.DataFrame, header_data: Dict[str, Any]):
        self.pandas_model.set_dataframe(df)
        self._populate_header_ui(header_data)
        self.undo_stack.clear()
        self.current_script_name = os.path.basename(file_path)
        self.current_script_path = file_path
        if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
            self.main_window.add_to_recent_files(file_path)
        
        status_bar = self.main_window.statusBar() if self.main_window else None
        if status_bar: status_bar.showMessage(f"Guion '{self.current_script_name}' cargado.", 5000)
        
        self.update_window_title()
        self.adjust_all_row_heights_and_validate() 
        self._update_toggle_header_button_text_and_icon()
        
        self._request_error_indicator_update() 
        self._request_scene_error_indicator_update()
        self._request_recache_subtitles()

    def open_docx_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Guion DOCX", "", "Documentos Word (*.docx)")
        if file_name: self.load_from_docx_path(file_name)

    def load_from_docx_path(self, file_path: str):
        try: df, header_data, _ = self.guion_manager.load_from_docx(file_path); self._post_load_script_actions(file_path, df, header_data)
        except Exception as e: self.handle_exception(e, f"Error al cargar DOCX: {file_path}"); self.clear_script_state()

    def import_from_excel_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar Guion desde Excel", "", "Archivos Excel (*.xlsx)")
        if path: self.load_from_excel_path(path)

    def load_from_excel_path(self, file_path: str):
        try: df, header_data, _ = self.guion_manager.load_from_excel(file_path); self._post_load_script_actions(file_path, df, header_data)
        except Exception as e: self.handle_exception(e, f"Error al cargar Excel: {file_path}"); self.clear_script_state()

    def load_from_json_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cargar Guion desde JSON", "", "Archivos JSON (*.json)")
        if path: self.load_from_json_path(path)

    def load_from_json_path(self, file_path: str):
        try: df, header_data, _ = self.guion_manager.load_from_json(file_path); self._post_load_script_actions(file_path, df, header_data)
        except Exception as e: self.handle_exception(e, f"Error al cargar JSON: {file_path}"); self.clear_script_state()

    def _generate_default_filename(self, extension: str) -> str:
        header_data = self._get_header_data_from_ui()
        product = str(header_data.get("product_name", "")).strip().replace(" ", "_")
        chapter = str(header_data.get("chapter_number", "")).strip().replace(" ", "_")
        base_name_parts = [part for part in [product, chapter] if part] 
        return f"{'_'.join(base_name_parts) if base_name_parts else 'guion'}.{extension}"

    def export_to_excel_dialog(self) -> bool:
        if self.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return False
        default_filename = self._generate_default_filename("xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_filename, "Archivos Excel (*.xlsx)")
        if path:
            try:
                self.guion_manager.save_to_excel(path, self.pandas_model.dataframe(), self._get_header_data_from_ui())
                QMessageBox.information(self, "Éxito", "Guion guardado en Excel.")
                self.current_script_name = os.path.basename(path)
                self.current_script_path = path
                self.undo_stack.setClean() 
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al guardar en Excel")
                return False
        return False
    
    def save_to_json_dialog(self) -> bool:
        if self.pandas_model.dataframe().empty:
            QMessageBox.information(self, "Guardar", "No hay datos para guardar.")
            return False
        default_filename = self._generate_default_filename("json")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar como JSON", default_filename, "Archivos JSON (*.json)")
        if path:
            try:
                self.guion_manager.save_to_json(path, self.pandas_model.dataframe(), self._get_header_data_from_ui())
                QMessageBox.information(self, "Éxito", "Guion guardado como JSON.")
                self.current_script_name = os.path.basename(path)
                self.current_script_path = path
                self.undo_stack.setClean() 
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al guardar como JSON")
                return False
        return False

    def update_action_buttons_state(self):
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        num_selected = len(selected_model_indices)
        is_main_window_available = self.main_window and hasattr(self.main_window, 'actions')

        can_delete = num_selected > 0
        if is_main_window_available and "edit_delete_row" in self.main_window.actions:
            self.main_window.actions["edit_delete_row"].setEnabled(can_delete)
        if "edit_delete_row" in self.action_buttons:
            self.action_buttons["edit_delete_row"].setEnabled(can_delete)

        can_move = num_selected == 1
        if is_main_window_available:
            if "edit_move_up" in self.main_window.actions:
                df_idx = selected_model_indices[0].row() if can_move else -1
                self.main_window.actions["edit_move_up"].setEnabled(can_move and df_idx > 0)
            if "edit_move_down" in self.main_window.actions:
                df_idx = selected_model_indices[0].row() if can_move else -1
                self.main_window.actions["edit_move_down"].setEnabled(can_move and df_idx < self.pandas_model.rowCount() - 1)
        if "edit_move_up" in self.action_buttons:
            df_idx = selected_model_indices[0].row() if can_move else -1
            self.action_buttons["edit_move_up"].setEnabled(can_move and df_idx > 0)
        if "edit_move_down" in self.action_buttons:
            df_idx = selected_model_indices[0].row() if can_move else -1
            self.action_buttons["edit_move_down"].setEnabled(can_move and df_idx < self.pandas_model.rowCount() - 1)


        can_split = num_selected == 1
        if is_main_window_available and "edit_split_intervention" in self.main_window.actions:
            self.main_window.actions["edit_split_intervention"].setEnabled(can_split)
        if "edit_split_intervention" in self.action_buttons:
            self.action_buttons["edit_split_intervention"].setEnabled(can_split)

        can_merge_check = num_selected >= 1 
        if is_main_window_available and "edit_merge_interventions" in self.main_window.actions:
            self.main_window.actions["edit_merge_interventions"].setEnabled(can_merge_check)
        if "edit_merge_interventions" in self.action_buttons:
            self.action_buttons["edit_merge_interventions"].setEnabled(can_merge_check)


        can_copy_in_out = (num_selected == 1 and selected_model_indices[0].row() < self.pandas_model.rowCount() - 1)
        if is_main_window_available and "edit_copy_in_out" in self.main_window.actions:
            self.main_window.actions["edit_copy_in_out"].setEnabled(can_copy_in_out)
        if "edit_copy_in_out" in self.action_buttons: 
            self.action_buttons["edit_copy_in_out"].setEnabled(can_copy_in_out)

        can_change_scene = num_selected == 1
        if is_main_window_available and "edit_increment_scene" in self.main_window.actions:
            self.main_window.actions["edit_increment_scene"].setEnabled(can_change_scene)

    def clear_script_state(self):
        self.pandas_model.set_dataframe(pd.DataFrame(columns=self.DF_COLUMN_ORDER))
        self._populate_header_ui({}) 
        self.undo_stack.clear()
        self.current_script_name = None
        self.current_script_path = None
        self._update_toggle_header_button_text_and_icon()
        self._request_error_indicator_update() 
        self._request_scene_error_indicator_update()
        self.update_window_title()


    def _perform_resize_rows_to_contents(self):
        if self.table_view.isVisible() and self.pandas_model.rowCount() > 0:
            self.table_view.resizeRowsToContents()

    def request_resize_rows_to_contents_deferred(self):
        self._resize_rows_timer.start()

    def adjust_all_row_heights_and_validate(self) -> None:
        self.request_resize_rows_to_contents_deferred()
        for row_idx in range(self.pandas_model.rowCount()):
            self.pandas_model.force_time_validation_update_for_row(row_idx) 
            self.pandas_model.force_scene_validation_update_for_row(row_idx)

    def on_model_layout_changed(self): 
        self.adjust_all_row_heights_and_validate()
        self.update_character_completer_and_notify() 

    def on_model_data_changed(self, top_left_index: QModelIndex, bottom_right_index: QModelIndex, roles: List[int]):
        if not top_left_index.isValid(): return
        self.set_unsaved_changes(True)
        for row in range(top_left_index.row(), bottom_right_index.row() + 1):
            view_col_idx = top_left_index.column() 
            df_col_name = self.pandas_model.get_df_column_name(view_col_idx)
            
            if df_col_name in ['DIÁLOGO', 'EUSKERA', 'OHARRAK']: # -> AÑADIDO OHARRAK
                self.request_resize_rows_to_contents_deferred()
            elif df_col_name == 'PERSONAJE':
                self.update_character_completer_and_notify()

    def update_character_completer_and_notify(self): 
        delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, delegate)
        self.character_name_changed.emit() 

    def copy_selected_time(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_index = selected_indexes[0] 
        view_col_idx = current_index.column()
        if view_col_idx == self.COL_IN_VIEW or view_col_idx == self.COL_OUT_VIEW:
            self.clipboard_text = str(self.pandas_model.data(current_index, Qt.ItemDataRole.EditRole))

    def paste_time(self) -> None:
        if not self.clipboard_text: return
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_index = selected_indexes[0]
        df_idx, view_col_idx = current_index.row(), current_index.column()
        if view_col_idx == self.COL_IN_VIEW or view_col_idx == self.COL_OUT_VIEW:
            old_value = str(self.pandas_model.data(current_index, Qt.ItemDataRole.EditRole))
            if old_value != self.clipboard_text:
                command = EditCommand(self, df_idx, view_col_idx, old_value, self.clipboard_text)
                self.undo_stack.push(command)

    # ----> MODIFICACIÓN CLAVE AQUÍ <----
    def adjust_dialogs(self, max_chars: int) -> None:
        if self.pandas_model.dataframe().empty:
            return

        self.undo_stack.beginMacro("Ajustar Diálogos (DIÁLOGO y EUSKERA)") 
        changed_any = False

        view_col_dialogue = self.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_euskera = self.pandas_model.get_view_column_index('EUSKERA')

        for df_idx in range(self.pandas_model.rowCount()):
            if view_col_dialogue is not None:
                dialog_text_original = str(self.pandas_model.dataframe().at[df_idx, 'DIÁLOGO'])
                adjusted_dialog_text = ajustar_dialogo(dialog_text_original, max_chars)
                if dialog_text_original != adjusted_dialog_text:
                    command_dialog = EditCommand(self, df_idx, view_col_dialogue, dialog_text_original, adjusted_dialog_text)
                    self.undo_stack.push(command_dialog)
                    changed_any = True
            
            if view_col_euskera is not None:
                euskera_text_original = str(self.pandas_model.dataframe().at[df_idx, 'EUSKERA'])
                adjusted_euskera_text = ajustar_dialogo(euskera_text_original, max_chars) 
                if euskera_text_original != adjusted_euskera_text:
                    command_euskera = EditCommand(self, df_idx, view_col_euskera, euskera_text_original, adjusted_euskera_text)
                    self.undo_stack.push(command_euskera)
                    changed_any = True

        self.undo_stack.endMacro()

        if changed_any:
            QMessageBox.information(self, "Éxito", "Diálogos y textos en Euskera ajustados.")
        else:
            QMessageBox.information(self, "Info", "No hubo diálogos ni textos en Euskera que necesitaran ajuste.")

    def copy_in_out_to_next(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        if not selected_model_indices or len(selected_model_indices) != 1: 
            QMessageBox.warning(self, "Copiar Tiempos", "Por favor, seleccione exactamente una fila.")
            return

        df_idx_selected = selected_model_indices[0].row() 
        if df_idx_selected >= self.pandas_model.rowCount() - 1:
            QMessageBox.warning(self, "Copiar Tiempos", "No se puede copiar a la siguiente fila desde la última fila.")
            return

        current_df = self.pandas_model.dataframe()
        in_time = str(current_df.at[df_idx_selected, 'IN'])
        out_time = str(current_df.at[df_idx_selected, 'OUT'])
        df_idx_next = df_idx_selected + 1

        self.undo_stack.beginMacro("Copiar IN/OUT a Siguiente")
        old_in_next = str(current_df.at[df_idx_next, 'IN'])
        if in_time != old_in_next:
            self.undo_stack.push(EditCommand(self, df_idx_next, self.COL_IN_VIEW, old_in_next, in_time))
        old_out_next = str(current_df.at[df_idx_next, 'OUT'])
        if out_time != old_out_next:
            self.undo_stack.push(EditCommand(self, df_idx_next, self.COL_OUT_VIEW, old_out_next, out_time))
        self.undo_stack.endMacro()

    def add_new_row(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        current_view_row = selected_model_indices[0].row() if selected_model_indices else self.pandas_model.rowCount() -1
        if current_view_row == -1 and self.pandas_model.rowCount() == 0: 
            df_insert_idx = 0
        elif current_view_row != -1: 
            df_insert_idx = current_view_row + 1
        else: 
            df_insert_idx = self.pandas_model.rowCount()

        command = AddRowCommand(self, df_insert_idx, df_insert_idx)
        self.undo_stack.push(command)

    def remove_row(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        if not selected_model_indices:
            QMessageBox.warning(self, "Eliminar Fila", "Por favor, seleccione una o más filas para eliminar.")
            return
        
        df_indices_to_remove = sorted([index.row() for index in selected_model_indices]) 
        
        num_filas_a_eliminar = len(df_indices_to_remove)
        confirm_msg = f"¿Está seguro de que desea eliminar {num_filas_a_eliminar} fila(s)?" \
            if num_filas_a_eliminar > 1 else "¿Está seguro de que desea eliminar la fila seleccionada?"
            
        confirm = QMessageBox.question(self, "Confirmar Eliminación", confirm_msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.Yes)
        if confirm == QMessageBox.StandardButton.Yes:
            command = RemoveRowsCommand(self, df_indices_to_remove)
            self.undo_stack.push(command)

    def move_row_up(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        df_source_idx = selected_indexes[0].row()
        if df_source_idx > 0:
            command = MoveRowCommand(self, df_source_idx, df_source_idx - 1)
            self.undo_stack.push(command)

    def move_row_down(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        df_source_idx = selected_indexes[0].row()
        if df_source_idx < self.pandas_model.rowCount() - 1:
            command = MoveRowCommand(self, df_source_idx, df_source_idx + 1)
            self.undo_stack.push(command)

    def handle_dialog_editor_state_on_focus_out(self, text: str, cursor_pos: int, index_edited: QModelIndex):
        self.last_focused_dialog_text = text
        self.last_focused_dialog_cursor_pos = cursor_pos
        self.last_focused_dialog_index = index_edited

    def split_intervention(self) -> None:
        current_model_index = self.table_view.currentIndex()
        if not current_model_index.isValid():
            QMessageBox.warning(self, "Separar", "Seleccione una celda en la columna 'DIÁLOGO' o 'EUSKERA' para separar.")
            return

        current_row_index = current_model_index.row()
        current_view_col_idx = current_model_index.column()
        df_column_name_to_split = self.pandas_model.get_df_column_name(current_view_col_idx)

        if df_column_name_to_split not in ['DIÁLOGO', 'EUSKERA']:
            QMessageBox.warning(self, "Separar", "Por favor, seleccione una celda en la columna 'DIÁLOGO' o 'EUSKERA'.")
            return
        
        cell_to_split_qmodelindex = self.pandas_model.index(current_row_index, current_view_col_idx)

        cursor_pos = -1
        text_that_was_split = None
        
        if self.last_focused_dialog_index and \
           self.last_focused_dialog_index.row() == cell_to_split_qmodelindex.row() and \
           self.last_focused_dialog_index.column() == cell_to_split_qmodelindex.column() and \
           self.last_focused_dialog_cursor_pos != -1:
            
            cursor_pos = self.last_focused_dialog_cursor_pos
            text_that_was_split = self.last_focused_dialog_text
        else:
            QMessageBox.information(self, "Separar Intervención",
                                    f"Por favor, edite la celda '{df_column_name_to_split}' (fila {current_row_index + 1}) "
                                    "y coloque el cursor en el punto de división deseado.\n\n"
                                    "Luego, asegúrese de que la celda pierda el foco (ej. haciendo clic fuera o presionando Enter) "
                                    "antes de intentar 'Separar'.")
            self.last_focused_dialog_index = None
            self.last_focused_dialog_cursor_pos = -1
            return
        
        self.last_focused_dialog_index = None
        self.last_focused_dialog_cursor_pos = -1
        
        if text_that_was_split is None:
            QMessageBox.warning(self, "Error Interno", f"No se pudo obtener el texto de la celda '{df_column_name_to_split}' para dividir.")
            return
        
        if not text_that_was_split.strip():
            QMessageBox.information(self, "Separar", f"No hay texto significativo en la celda '{df_column_name_to_split}' para dividir.")
            return
            
        if not (0 <= cursor_pos <= len(text_that_was_split)):
            QMessageBox.information(self, "Separar", 
                                    f"Posición de cursor inválida ({cursor_pos}) para el texto actual. "
                                    f"Debe estar entre 0 y {len(text_that_was_split)}.")
            return
        
        before_text = text_that_was_split[:cursor_pos].strip()
        after_text = text_that_was_split[cursor_pos:].strip()
        
        if not after_text:
            QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención después de la posición del cursor.")
            return
        
        command = SplitInterventionCommand(self, current_row_index, 
                                           before_text, after_text, 
                                           text_that_was_split, df_column_name_to_split)
        self.undo_stack.push(command)

    def merge_interventions(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows() 
        if not selected_model_indices:
            QMessageBox.warning(self, "Juntar", "Por favor, seleccione la primera de las dos filas a juntar.")
            return

        df_idx_curr = selected_model_indices[0].row() 
        df_idx_next = df_idx_curr + 1

        if df_idx_next >= self.pandas_model.rowCount():
            QMessageBox.warning(self, "Juntar", "No se puede juntar la última fila con una inexistente o no hay fila siguiente a la primera seleccionada.")
            return

        current_df = self.pandas_model.dataframe()
        char_curr = str(current_df.at[df_idx_curr, 'PERSONAJE'])
        char_next = str(current_df.at[df_idx_next, 'PERSONAJE'])

        if char_curr != char_next:
            QMessageBox.warning(self, "Juntar", "Solo se pueden juntar intervenciones del mismo personaje.")
            return

        dialog_curr = str(current_df.at[df_idx_curr, 'DIÁLOGO'])
        dialog_next = str(current_df.at[df_idx_next, 'DIÁLOGO'])
        merged_dialog = f"{dialog_curr.strip()} {dialog_next.strip()}".strip()

        euskera_curr = str(current_df.at[df_idx_curr, 'EUSKERA'])
        euskera_next = str(current_df.at[df_idx_next, 'EUSKERA'])
        merged_euskera = f"{euskera_curr.strip()} {euskera_next.strip()}".strip()

        original_out_first = str(current_df.at[df_idx_curr, 'OUT'])

        command = MergeInterventionsCommand(
            self,
            df_idx_curr,
            merged_dialog,
            merged_euskera,
            df_idx_next,
            original_out_first
        )
        self.undo_stack.push(command)

    def convert_time_code_to_milliseconds(self, time_code: str) -> int:
        try:
            FPS_RATE = 25.0  # Definir la constante primero
            parts = time_code.split(':'); h, m, s, f = map(int, parts)
            
            # La validación ahora puede usar FPS_RATE de forma segura
            if len(parts) != 4 or not (0 <= m < 60 and 0 <= s < 60 and 0 <= f < FPS_RATE):
                raise ValueError(f"Formato o rango de Timecode inválido (MM:SS < 60, FF < {int(FPS_RATE)})")
            
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / FPS_RATE) * 1000.0))
        except ValueError:
            # Esta excepción ahora captura tanto los errores de formato como los de rango
            return 0
        except Exception as e:
            self.handle_exception(e, f"Error convirtiendo '{time_code}' a milisegundos")
            return 0

    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        try:
            if ms < 0: ms = 0
            total_seconds, rem_ms = divmod(ms, 1000)
            h, rem_seconds = divmod(total_seconds, 3600)
            m, s = divmod(rem_seconds, 60)
            f = int(round(rem_ms / (1000.0 / 25.0))) 
            if f >= 25: f = 24 
            return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"
        except Exception: return "00:00:00:00"

    def update_in_out_from_player(self, action_type: str, position_ms: int) -> None: 
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        df_idx = selected_indexes[0].row()
        if df_idx >= self.pandas_model.rowCount(): return 
        time_code_str = self.convert_milliseconds_to_time_code(position_ms)
        
        view_col_to_update = -1
        if action_type.upper() == "IN": view_col_to_update = self.COL_IN_VIEW
        elif action_type.upper() == "OUT": view_col_to_update = self.COL_OUT_VIEW
        else: return

        model_idx_to_update = self.pandas_model.index(df_idx, view_col_to_update)
        old_value = str(self.pandas_model.data(model_idx_to_update, Qt.ItemDataRole.EditRole))
        if time_code_str != old_value:
            command = EditCommand(self, df_idx, view_col_to_update, old_value, time_code_str)
            self.undo_stack.push(command)

    def toggle_link_out_to_next_in_checkbox(self, state: int): 
        self.link_out_to_next_in_enabled = (Qt.CheckState(state) == Qt.CheckState.Checked)

    def select_next_row_after_out_release(self) -> None: 
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_view_row = selected_indexes[0].row()
        
        if not self.link_out_to_next_in_enabled:
            if current_view_row < self.pandas_model.rowCount() - 1:
                df_idx_next = current_view_row + 1
                self.table_view.selectRow(df_idx_next)
                idx_to_scroll = self.pandas_model.index(df_idx_next, 0)
                if idx_to_scroll.isValid(): self.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.PositionAtCenter)
            return

        if current_view_row >= self.pandas_model.rowCount() - 1: return 
        df_idx_curr = current_view_row
        current_out_time_str = str(self.pandas_model.dataframe().at[df_idx_curr, 'OUT'])
        df_idx_next = current_view_row + 1
        self.table_view.selectRow(df_idx_next)
        
        model_idx_in_next = self.pandas_model.index(df_idx_next, self.COL_IN_VIEW)
        old_in_next = str(self.pandas_model.data(model_idx_in_next, Qt.ItemDataRole.EditRole))
        if current_out_time_str != old_in_next:
            command = EditCommand(self, df_idx_next, self.COL_IN_VIEW, old_in_next, current_out_time_str)
            self.undo_stack.push(command)
        self.table_view.scrollTo(model_idx_in_next, QAbstractItemView.ScrollHint.PositionAtCenter)

    def change_scene(self) -> None: 
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Cambiar Escena", "Por favor, seleccione una fila."); return
        df_idx = selected_indexes[0].row()
        command = ChangeSceneCommand(self, df_idx)
        self.undo_stack.push(command)

    def has_scene_numbers(self) -> bool: 
        current_df = self.pandas_model.dataframe()
        if 'SCENE' not in current_df.columns or current_df.empty: return False
        unique_scenes = set(str(s).strip() for s in current_df['SCENE'].unique() if pd.notna(s) and str(s).strip())
        return len(unique_scenes) > 1 or \
               (len(unique_scenes) == 1 and ("1" not in unique_scenes and "" not in unique_scenes))


    def handle_ctrl_click_on_cell(self, view_row_idx: int) -> None: 
        if view_row_idx >= self.pandas_model.rowCount(): return
        model_idx_in = self.pandas_model.index(view_row_idx, self.COL_IN_VIEW)
        in_time_code = str(self.pandas_model.data(model_idx_in, Qt.ItemDataRole.EditRole))
        ms = self.convert_time_code_to_milliseconds(in_time_code)
        self.in_out_signal.emit("IN", ms) 

    def handle_alt_click_on_cell(self, view_row_idx: int) -> None: 
        if view_row_idx >= self.pandas_model.rowCount(): return
        model_idx_out = self.pandas_model.index(view_row_idx, self.COL_OUT_VIEW)
        out_time_code = str(self.pandas_model.data(model_idx_out, Qt.ItemDataRole.EditRole))
        ms = self.convert_time_code_to_milliseconds(out_time_code)
        self.in_out_signal.emit("OUT", ms)

    def get_character_names_from_model(self) -> List[str]:
        current_df = self.pandas_model.dataframe()
        if current_df.empty or 'PERSONAJE' not in current_df.columns: return []
        return sorted(list(set(str(name) for name in current_df['PERSONAJE'].unique() if pd.notna(name) and str(name).strip())))

    def update_character_name(self, old_name: str, new_name: str) -> None:
        current_df = self.pandas_model.dataframe()
        if not new_name.strip(): QMessageBox.warning(self, "Nombre de Personaje Inválido", "El nombre del personaje no puede estar vacío."); return
        self.undo_stack.beginMacro(f"Cambiar nombre de personaje '{old_name}' a '{new_name}'")
        changed_any = False
        view_col_char = self.pandas_model.get_view_column_index('PERSONAJE')
        if view_col_char is None: self.undo_stack.endMacro(); return
        for df_idx in range(self.pandas_model.rowCount()):
            if str(current_df.at[df_idx, 'PERSONAJE']) == old_name:
                command = EditCommand(self, df_idx, view_col_char, old_name, new_name)
                self.undo_stack.push(command); changed_any = True
        self.undo_stack.endMacro()
        if changed_any: self.update_character_completer_and_notify() 

    # -> INICIO: MÉTODO `find_and_replace` CORREGIDO
    def find_and_replace(self, find_text: str, replace_text: str,
                         search_in_character: bool = True,
                         search_in_dialogue: bool = True,
                         search_in_euskera: bool = False) -> None:
        if self.pandas_model.dataframe().empty or not find_text:
            return
        
        self.undo_stack.beginMacro("Buscar y Reemplazar Todo")
        changed_count = 0
        
        view_col_char = self.pandas_model.get_view_column_index('PERSONAJE')
        view_col_dialog = self.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_euskera = self.pandas_model.get_view_column_index('EUSKERA')

        for df_idx in range(self.pandas_model.rowCount()):
            if search_in_character and view_col_char is not None:
                char_text_orig = str(self.pandas_model.dataframe().at[df_idx, 'PERSONAJE'])
                new_char_text, num_subs = re.subn(re.escape(find_text), replace_text, char_text_orig, flags=re.IGNORECASE)
                if num_subs > 0:
                    self.undo_stack.push(EditCommand(self, df_idx, view_col_char, char_text_orig, new_char_text))
                    changed_count += num_subs

            if search_in_dialogue and view_col_dialog is not None:
                dialog_text_orig = str(self.pandas_model.dataframe().at[df_idx, 'DIÁLOGO'])
                new_dialog_text, num_subs = re.subn(re.escape(find_text), replace_text, dialog_text_orig, flags=re.IGNORECASE)
                if num_subs > 0:
                    self.undo_stack.push(EditCommand(self, df_idx, view_col_dialog, dialog_text_orig, new_dialog_text))
                    changed_count += num_subs
            
            if search_in_euskera and view_col_euskera is not None:
                euskera_text_orig = str(self.pandas_model.dataframe().at[df_idx, 'EUSKERA'])
                new_euskera_text, num_subs = re.subn(re.escape(find_text), replace_text, euskera_text_orig, flags=re.IGNORECASE)
                if num_subs > 0:
                    self.undo_stack.push(EditCommand(self, df_idx, view_col_euskera, euskera_text_orig, new_euskera_text))
                    changed_count += num_subs

        self.undo_stack.endMacro()
        QMessageBox.information(self, "Reemplazar Todo",
                                f"{changed_count} reemplazo(s) realizado(s)." if changed_count > 0 else "No se encontraron coincidencias para reemplazar.")
    # -> FIN: MÉTODO `find_and_replace` CORREGIDO

    # -> INICIO: MÉTODO `replace_in_current_match` CORREGIDO
    def replace_in_current_match(self, df_idx: int, find_text: str, replace_text: str,
                                 in_char: bool, in_dialogue: bool, in_euskera: bool) -> bool:
        """Reemplaza la primera coincidencia encontrada en una fila específica."""
        if self.pandas_model.dataframe().empty or not find_text or not (0 <= df_idx < self.pandas_model.rowCount()):
            return False

        self.undo_stack.beginMacro(f"Reemplazar en fila {df_idx + 1}")
        changed = False

        columns_to_check = []
        if in_char: columns_to_check.append('PERSONAJE')
        if in_dialogue: columns_to_check.append('DIÁLOGO')
        if in_euskera: columns_to_check.append('EUSKERA')

        for col_name in columns_to_check:
            view_col_idx = self.pandas_model.get_view_column_index(col_name)
            if view_col_idx is None:
                continue

            original_text = str(self.pandas_model.dataframe().at[df_idx, col_name])
            
            new_text, num_subs = re.subn(re.escape(find_text), replace_text, original_text, count=1, flags=re.IGNORECASE)

            if num_subs > 0:
                self.undo_stack.push(EditCommand(self, df_idx, view_col_idx, original_text, new_text))
                changed = True
                break

        self.undo_stack.endMacro()
        return changed
    # -> FIN: MÉTODO `replace_in_current_match` CORREGIDO

    def update_window_title(self) -> None:
        prefix = "*" if self.unsaved_changes else ""
        script_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window: self.main_window.setWindowTitle(f"{prefix}Editor Guion - {script_name}")

    def set_unsaved_changes(self, changed: bool):
        if self.unsaved_changes != changed:
            self.unsaved_changes = changed
            self.update_window_title()

    def renumerar_escenas_a_uno(self) -> None: 
        current_df = self.pandas_model.dataframe()
        if not self.has_scene_numbers() and not current_df.empty: 
            self.undo_stack.beginMacro("Renumerar Escenas a '1'")
            view_col_scene = self.pandas_model.get_view_column_index('SCENE')
            if view_col_scene is not None:
                for df_idx in range(len(current_df)):
                    old_scene = str(current_df.at[df_idx, 'SCENE'])
                    if old_scene != "1":
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_scene, old_scene, "1"))
            self.undo_stack.endMacro()
            if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Renumerar"):
                 QMessageBox.information(self, "Escenas", "Escenas renumeradas a '1'.")


    def get_next_id(self) -> int: return self.pandas_model.get_next_id()
    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]: return self.pandas_model.find_df_index_by_id(id_value)
    def get_dataframe_column_name(self, table_col_index: int) -> Optional[str]: return self.pandas_model.get_df_column_name(table_col_index)

    def handle_exception(self, exception: Exception, message: str) -> None:
        import traceback
        error_details = f"ERROR: {message}\n{str(exception)}\n{traceback.format_exc()}"
        print(error_details)
        QMessageBox.critical(self, "Error", f"{message}:\n{str(exception)}")

    def apply_font_size_to_dialogs(self, font_size: int) -> None:
        self.current_font_size = font_size
        if hasattr(self, 'dialog_delegate') and self.dialog_delegate:
            self.dialog_delegate.setFontSize(font_size) 
        
        table_font = self.table_view.font()
        table_font.setPointSize(font_size)
        self.table_view.setFont(table_font)
        
        header = self.table_view.horizontalHeader()
        header_font = header.font()
        header_font.setPointSize(font_size) 
        header.setFont(header_font)

    def _check_header_fields_completeness(self) -> bool:
        if not hasattr(self, 'reference_edit') or \
           not hasattr(self, 'product_edit') or \
           not hasattr(self, 'chapter_edit'): 
            return True 

        ref_empty = not self.reference_edit.text().strip()
        prod_empty = not self.product_edit.text().strip()
        chap_empty = not self.chapter_edit.text().strip()
        
        return not (ref_empty or prod_empty or chap_empty)

    def _update_toggle_header_button_text_and_icon(self):
        if not hasattr(self, 'toggle_header_button') or not hasattr(self, 'header_details_widget'):
            return 

        is_visible = self.header_details_widget.isVisible()
        
        if not is_visible: 
            text = " Mostrar Detalles del Guion"
            if not self._check_header_fields_completeness():
                text += " (Campos Incompletos)"
            icon_to_set = self.icon_expand_more
        else: 
            text = " Ocultar Detalles del Guion"
            icon_to_set = self.icon_expand_less
        
        self.toggle_header_button.setText(text)
        if self.get_icon and icon_to_set: 
            self.toggle_header_button.setIcon(icon_to_set)
        elif not self.get_icon: 
            self.toggle_header_button.setIcon(QIcon())