# guion_editor/widgets/table_window.py

import json
import os
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize, QModelIndex, QTimer, QKeyCombination, QPoint
from PyQt6.QtGui import QFont, QColor, QIntValidator, QBrush, QIcon, QKeyEvent, QKeySequence, QAction
from PyQt6.QtWidgets import (
    QWidget, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QInputDialog, QCheckBox, QMenu
)
from PyQt6.QtGui import QUndoStack, QUndoCommand

from guion_editor.widgets.custom_table_view import CustomTableView
from guion_editor.models.pandas_table_model import PandasTableModel, ROW_NUMBER_COL_IDENTIFIER
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.delegates.guion_delegate import DialogDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.utils.guion_manager import GuionManager
from guion_editor.widgets.custom_text_edit import CustomTextEdit


class TableWindow(QWidget):
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    COL_NUM_INTERV_VIEW = 0
    COL_ID_VIEW = 1         
    COL_SCENE_VIEW = 2      
    COL_IN_VIEW = 3         
    COL_OUT_VIEW = 4        
    COL_CHARACTER_VIEW = 5  
    COL_DIALOGUE_VIEW = 6   
    COL_EUSKERA_VIEW = 7 # NUEVA COLUMNA VISUAL

    VIEW_COLUMN_NAMES = ["Nº", "ID", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO", "EUSKERA"] # AÑADIDO
    
    VIEW_TO_DF_COL_MAP = {
        COL_NUM_INTERV_VIEW: ROW_NUMBER_COL_IDENTIFIER,
        COL_ID_VIEW: 'ID', 
        COL_SCENE_VIEW: 'SCENE', 
        COL_IN_VIEW: 'IN',
        COL_OUT_VIEW: 'OUT', 
        COL_CHARACTER_VIEW: 'PERSONAJE', 
        COL_DIALOGUE_VIEW: 'DIÁLOGO',
        COL_EUSKERA_VIEW: 'EUSKERA' # AÑADIDO
    }
    # AÑADIR 'EUSKERA' A DF_COLUMN_ORDER
    DF_COLUMN_ORDER = ['ID', 'SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA']

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None,
                 guion_manager: Optional[GuionManager] = None, get_icon_func=None):
        super().__init__()
        self.get_icon = get_icon_func
        self.main_window = main_window 
        self.current_font_size = 9
        self.f6_key_pressed_internally = False 

        self._resize_rows_timer = QTimer(self)
        self._resize_rows_timer.setSingleShot(True)
        self._resize_rows_timer.setInterval(100) 
        self._resize_rows_timer.timeout.connect(self._perform_resize_rows_to_contents)

        # Timer para actualizar el indicador de error de tiempo de forma diferida
        self._update_error_indicator_timer = QTimer(self)
        self._update_error_indicator_timer.setSingleShot(True)
        self._update_error_indicator_timer.setInterval(0) # Ejecutar tan pronto como sea posible en el siguiente ciclo de eventos
        self._update_error_indicator_timer.timeout.connect(self.update_time_error_indicator)

        self.action_buttons = {}
        self.video_player_widget = video_player_widget
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out_from_player) 
            self.video_player_widget.out_released.connect(self.select_next_row_after_out_release) 

        self.guion_manager = guion_manager if guion_manager else GuionManager()
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

        if self.get_icon:
            self.icon_expand_less = self.get_icon("toggle_header_collapse_icon.svg")
            self.icon_expand_more = self.get_icon("toggle_header_expand_icon.svg")
        else:
            self.icon_expand_less, self.icon_expand_more = QIcon(), QIcon()

        self.time_error_indicator_label: Optional[QLabel] = None

        self.setup_ui() # setup_ui se llama aquí
        self.update_action_buttons_state() # Llamada inicial para establecer el estado correcto

        self.pandas_model.dataChanged.connect(self._request_error_indicator_update) # Cambiado
        self.pandas_model.layoutChanged.connect(self._request_error_indicator_update) # Cambiado
        self.pandas_model.modelReset.connect(self._request_error_indicator_update) # Cambiado


        self.clear_script_state() 
        self.update_window_title()

        QTimer.singleShot(0, lambda: self.table_view.setColumnHidden(self.COL_EUSKERA_VIEW, True))

    def _request_error_indicator_update(self):
        """Solicita una actualización del indicador de error de tiempo de forma diferida."""
        self._update_error_indicator_timer.start()

    def setup_ui(self) -> None: 
        main_layout = QVBoxLayout(self)
        icon_size_header_toggle = QSize(20, 20)
        self.toggle_header_button = QPushButton()
        self.toggle_header_button.setIconSize(icon_size_header_toggle) # Asegúrate que esto esté antes de setObjectName si CSS depende de ello
        self.toggle_header_button.setObjectName("toggle_header_button_css")
        self.toggle_header_button.clicked.connect(self.toggle_header_visibility)
        main_layout.addWidget(self.toggle_header_button)

        self.header_details_widget = QWidget()
        # --- INICIO CORRECCIÓN ---
        self.header_form_layout = QFormLayout() # Crear el QFormLayout aquí
        # --- FIN CORRECCIÓN ---
        self.header_details_widget.setLayout(self.header_form_layout) # Asignar el layout al widget
        
        self.setup_header_fields(self.header_form_layout) # Ahora self.header_form_layout existe
        main_layout.addWidget(self.header_details_widget)

        self.header_details_widget.setVisible(False) 
        self._update_toggle_header_button_text_and_icon() 

        self.setup_buttons(main_layout)
        self.setup_table_view(main_layout)
        self.load_stylesheet()

    def setup_header_fields(self, form_layout: QFormLayout) -> None:
        self.reference_edit = QLineEdit(); self.reference_edit.setValidator(QIntValidator(0, 999999, self))
        self.reference_edit.setMaxLength(6); self.reference_edit.setPlaceholderText("Máximo 6 dígitos")
        form_layout.addRow("Número de referencia:", self.reference_edit)
        self.product_edit = QLineEdit(); self.product_edit.setPlaceholderText("Nombre del producto")
        form_layout.addRow("Nombre del Producto:", self.product_edit)
        self.chapter_edit = QLineEdit(); self.chapter_edit.setPlaceholderText("Número de capítulo")
        form_layout.addRow("N.º Capítulo:", self.chapter_edit)
        self.type_combo = QComboBox(); self.type_combo.addItems(["Ficcion", "Animacion", "Documental"])
        form_layout.addRow("Tipo:", self.type_combo)
        for widget in [self.reference_edit, self.product_edit, self.chapter_edit, self.type_combo]:
            if isinstance(widget, QLineEdit): widget.textChanged.connect(self._header_field_changed)
            elif isinstance(widget, QComboBox): widget.currentIndexChanged.connect(self._header_field_changed)

    def _header_field_changed(self, *args): # Changed to accept arbitrary args from signals
        self.set_unsaved_changes(True)
        self._update_toggle_header_button_text_and_icon()
        # Update internal state if needed, or rely on _get_header_data_from_ui() when saving

    def toggle_header_visibility(self) -> None:
        current_visibility = self.header_details_widget.isVisible()
        self.header_details_widget.setVisible(not current_visibility)
        self._update_toggle_header_button_text_and_icon()

    def setup_buttons(self, layout: QVBoxLayout) -> None:
        buttons_layout_top_row = QHBoxLayout()
        icon_size = QSize(18, 18)
        actions_map = [
            # (texto, método, icono, solo_icono, nombre_accion_mainwindow)
            (" Agregar Línea", self.add_new_row, "add_row_icon.svg", False, "edit_add_row"),
            (" Eliminar Fila", self.remove_row, "delete_row_icon.svg", False, "edit_delete_row"),
            ("", self.move_row_up, "move_up_icon.svg", True, "edit_move_up"),
            ("", self.move_row_down, "move_down_icon.svg", True, "edit_move_down"),
            (" Ajustar Diálogos", self.adjust_dialogs, "adjust_dialogs_icon.svg", False, "edit_adjust_dialogs"),
            (" Separar", self.split_intervention, "split_intervention_icon.svg", False, "edit_split_intervention"),
            (" Juntar", self.merge_interventions, "merge_intervention_icon.svg", False, "edit_merge_interventions"),
            # NUEVO: Identificador para el botón de Copiar IN/OUT para control de estado
            (" Copiar IN/OUT", self.copy_in_out_to_next, "copy_in_out_icon.svg", False, "edit_copy_in_out")
        ]
        for text, method, icon_name, only_icon, action_obj_name in actions_map: # CAMBIO action_obj_name
            button = QPushButton(text)
            if self.get_icon and icon_name: button.setIcon(self.get_icon(icon_name)); button.setIconSize(icon_size)
            if only_icon: button.setFixedSize(QSize(icon_size.width() + 16, icon_size.height() + 12)); button.setToolTip(text.strip() if text.strip() else method.__name__.replace("_", " ").title())
            button.clicked.connect(method)
            buttons_layout_top_row.addWidget(button)
            self.action_buttons[action_obj_name] = button

        self.time_error_indicator_label = QLabel("")
        self.time_error_indicator_label.setObjectName("timeErrorIndicatorLabel")
        buttons_layout_top_row.addWidget(self.time_error_indicator_label)

        self.link_out_in_checkbox = QCheckBox("OUT->IN")
        self.link_out_in_checkbox.setChecked(self.link_out_to_next_in_enabled)
        self.link_out_in_checkbox.setToolTip("Si está marcado, al definir un OUT también se definirá el IN de la siguiente fila.")
        self.link_out_in_checkbox.stateChanged.connect(self.toggle_link_out_to_next_in_checkbox) # Renamed
        buttons_layout_top_row.addWidget(self.link_out_in_checkbox)
        layout.addLayout(buttons_layout_top_row)

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
        # La lógica interna de esta función permanece igual que antes,
        # pero ahora se llama de forma diferida.
        if not self.time_error_indicator_label or not hasattr(self.pandas_model, '_time_validation_status'):
            return

        has_errors = False
        error_rows_interventions = [] 

        if self.pandas_model.rowCount() > 0 and isinstance(self.pandas_model._time_validation_status, dict):
            # Iterar sobre una copia de los items si hay riesgo de modificación concurrente (poco probable aquí)
            for df_row_idx, is_valid in sorted(list(self.pandas_model._time_validation_status.items())):
                if not is_valid:
                    has_errors = True
                    error_rows_interventions.append(str(df_row_idx + 1))
        
        if has_errors:
            self.time_error_indicator_label.setText("⚠️ TIEMPOS")
            self.time_error_indicator_label.setStyleSheet("color: red; font-weight: bold;")
            if error_rows_interventions:
                tooltip_text = "Errores en intervenciones: " + ", ".join(error_rows_interventions)
                self.time_error_indicator_label.setToolTip(tooltip_text)
            else:
                self.time_error_indicator_label.setToolTip("Se detectaron errores de tiempo, pero no se pudieron listar las filas afectadas.")
        else:
            self.time_error_indicator_label.setText("") 
            self.time_error_indicator_label.setStyleSheet("") 
            self.time_error_indicator_label.setToolTip("")

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

        time_delegate = TimeCodeDelegate(self.table_view)
        self.table_view.setItemDelegateForColumn(self.COL_IN_VIEW, time_delegate)
        self.table_view.setItemDelegateForColumn(self.COL_OUT_VIEW, time_delegate)
        
        char_delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, char_delegate)

        self.dialog_delegate = DialogDelegate(parent=self.table_view, font_size=self.current_font_size, table_window_instance=self)
        self.table_view.setItemDelegateForColumn(self.COL_DIALOGUE_VIEW, self.dialog_delegate)
        self.table_view.setItemDelegateForColumn(self.COL_EUSKERA_VIEW, self.dialog_delegate)

        self.table_view.cellCtrlClicked.connect(self.handle_ctrl_click_on_cell)
        self.table_view.cellAltClicked.connect(self.handle_alt_click_on_cell)  
        self.pandas_model.dataChanged.connect(self.on_model_data_changed)
        self.pandas_model.layoutChanged.connect(self.on_model_layout_changed)

        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False)

        # Configurar la política del menú contextual para la cabecera horizontal
        self.table_view.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.horizontalHeader().sectionResized.connect(self.handle_column_resized)
        self.table_view.horizontalHeader().customContextMenuRequested.connect(self.show_header_context_menu)

    def show_header_context_menu(self, position: QPoint) -> None: # CAMBIADO
        """Muestra un menú contextual para alternar la visibilidad de las columnas."""
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
        """Slot para ocultar o mostrar una columna según el estado de la acción."""
        action = self.sender() # Obtener la QAction que emitió la señal
        if isinstance(action, QAction):
            view_col_idx = action.data() # Recuperar el índice de la columna de la vista
            if isinstance(view_col_idx, int):
                # Ocultar la columna si 'checked' es False (se desmarcó), mostrarla si es True
                self.table_view.setColumnHidden(view_col_idx, not checked)

    def handle_column_resized(self, logical_index: int, old_size: int, new_size: int):
        """
        Llamado cuando una columna es redimensionada manualmente.
        Si es una columna de diálogo, solicita redimensionar las filas.
        """
        # logical_index es el índice de la columna en la vista (view column index)
        
        # Nos interesa principalmente si las columnas de DIÁLOGO o EUSKERA son redimensionadas,
        # ya que su contenido afecta directamente la altura necesaria.
        if logical_index == self.COL_DIALOGUE_VIEW or logical_index == self.COL_EUSKERA_VIEW:
            self.request_resize_rows_to_contents_deferred()

    def load_stylesheet(self) -> None: # No changes here
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')
            if not os.path.exists(css_path):
                alt_css_path = os.path.join(os.path.dirname(current_file_dir), 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path): css_path = alt_css_path
                else: print(f"Advertencia: Stylesheet no encontrado: {css_path}"); return
            with open(css_path, 'r', encoding='utf-8') as f: self.table_view.setStyleSheet(f.read())
        except Exception as e: QMessageBox.warning(self, "Error de Estilos", f"Error al cargar CSS para TableView: {str(e)}")

    def update_key_listeners(self):
        # Called by ShortcutManager if shortcuts change.
        # For "video_mark_out_hold", its QKeySequence is stored in the QAction.
        # KeyPress/Release events in this widget will query this QAction's shortcut.
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        # print(f"VPW KeyPress: key={event.key()}, combo={event.keyCombination()}, focus={QApplication.focusWidget()}")
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence'): # Comprueba el nuevo atributo
            super().keyPressEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence
        # print(f"  VPW: Expected F6 combo from main_window: {current_mark_out_shortcut[0] if not current_mark_out_shortcut.isEmpty() else 'EMPTY'}")
            
        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            # event.keyCombination() es la forma correcta de obtener la combinación del evento
            if event.keyCombination() == current_mark_out_shortcut[0]: 
                key_match = True
        
        if key_match and not event.isAutoRepeat() and not self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = True
            # --- CORRECCIÓN AQUÍ ---
            if self.video_player_widget and hasattr(self.video_player_widget, 'handle_out_button_pressed'):
                self.video_player_widget.handle_out_button_pressed()
            # --- FIN DE LA CORRECCIÓN ---
            event.accept()
            return
        
        # Si F6 no coincidió, deja que las QActions de este widget (si las tuviera) o del padre se procesen
        super().keyPressEvent(event)


    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        # Comprobar si main_window y el atributo existen, y si video_player_widget está disponible
        if not self.main_window or not hasattr(self.main_window, 'mark_out_hold_key_sequence') or not self.video_player_widget:
            super().keyReleaseEvent(event)
            return

        current_mark_out_shortcut: QKeySequence = self.main_window.mark_out_hold_key_sequence

        key_match = False
        if not current_mark_out_shortcut.isEmpty():
            # event.keyCombination() es la forma correcta de obtener la combinación del evento
            if event.keyCombination() == current_mark_out_shortcut[0]: # Compara con la primera (y usualmente única) combinación en la secuencia
                key_match = True

        if key_match and not event.isAutoRepeat() and self.f6_key_pressed_internally:
            self.f6_key_pressed_internally = False
            # --- CORRECCIÓN AQUÍ ---
            # Delegar la acción al video_player_widget
            if hasattr(self.video_player_widget, 'handle_out_button_released'): # Asegurarse que el método existe
                self.video_player_widget.handle_out_button_released()
            # --- FIN DE LA CORRECCIÓN ---
            event.accept()
            return
        
        super().keyReleaseEvent(event)

    def _populate_header_ui(self, header_data: Dict[str, Any]):
        self.reference_edit.setText(str(header_data.get("reference_number", ""))) # Ensure string
        self.product_edit.setText(str(header_data.get("product_name", "")))
        self.chapter_edit.setText(str(header_data.get("chapter_number", "")))
        tipo = str(header_data.get("type", "Ficcion"))
        idx = self.type_combo.findText(tipo, Qt.MatchFlag.MatchFixedString | Qt.MatchFlag.MatchCaseSensitive) # More precise match
        self.type_combo.setCurrentIndex(idx if idx != -1 else 0)

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
        self.set_unsaved_changes(False) 
        if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
            self.main_window.add_to_recent_files(file_path)
        
        status_bar = self.main_window.statusBar() if self.main_window else None
        if status_bar: status_bar.showMessage(f"Guion '{self.current_script_name}' cargado.", 5000)
        else: print(f"INFO: Guion '{self.current_script_name}' cargado.")
        
        self.adjust_all_row_heights_and_validate() 
        self._update_toggle_header_button_text_and_icon()
        
        # Solicitar actualización del indicador de error de forma diferida
        self._request_error_indicator_update() # MODIFICADO

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
        base_name_parts = [part for part in [product, chapter] if part] # Filter empty parts
        return f"{'_'.join(base_name_parts) if base_name_parts else 'guion'}.{extension}"

    def export_to_excel_dialog(self) -> bool:
        if self.pandas_model.dataframe().empty: QMessageBox.information(self, "Exportar", "No hay datos para exportar."); return False
        default_filename = self._generate_default_filename("xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_filename, "Archivos Excel (*.xlsx)")
        if path:
            try:
                self.guion_manager.save_to_excel(path, self.pandas_model.dataframe(), self._get_header_data_from_ui())
                QMessageBox.information(self, "Éxito", "Guion guardado en Excel.")
                self.current_script_name = os.path.basename(path); self.current_script_path = path
                self.set_unsaved_changes(False)
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e: self.handle_exception(e, "Error al guardar en Excel"); return False
        return False

    def save_to_json_dialog(self) -> bool:
        if self.pandas_model.dataframe().empty: QMessageBox.information(self, "Guardar", "No hay datos para guardar."); return False
        default_filename = self._generate_default_filename("json")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar como JSON", default_filename, "Archivos JSON (*.json)")
        if path:
            try:
                self.guion_manager.save_to_json(path, self.pandas_model.dataframe(), self._get_header_data_from_ui())
                QMessageBox.information(self, "Éxito", "Guion guardado como JSON.")
                self.current_script_name = os.path.basename(path); self.current_script_path = path
                self.set_unsaved_changes(False)
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e: self.handle_exception(e, "Error al guardar como JSON"); return False
        return False

    def update_action_buttons_state(self):
        """Actualiza el estado (enabled/disabled) de los botones y QActions basado en la selección."""
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        num_selected = len(selected_model_indices)
        is_main_window_available = self.main_window and hasattr(self.main_window, 'actions')

        # Acciones que siempre están habilitadas (o cuya lógica interna maneja la selección)
        # "edit_add_row", "edit_adjust_dialogs" (opera en todo), "file_..."

        # --- Acciones que dependen del número de filas seleccionadas ---

        # Eliminar Fila: Habilitado si al menos una fila seleccionada
        can_delete = num_selected > 0
        if is_main_window_available and "edit_delete_row" in self.main_window.actions:
            self.main_window.actions["edit_delete_row"].setEnabled(can_delete)
        if "edit_delete_row" in self.action_buttons:
            self.action_buttons["edit_delete_row"].setEnabled(can_delete)

        # Mover Arriba/Abajo: Solo si exactamente UNA fila está seleccionada
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


        # Separar Intervención: Solo si exactamente UNA fila está seleccionada
        can_split = num_selected == 1
        if is_main_window_available and "edit_split_intervention" in self.main_window.actions:
            self.main_window.actions["edit_split_intervention"].setEnabled(can_split)
        if "edit_split_intervention" in self.action_buttons:
            self.action_buttons["edit_split_intervention"].setEnabled(can_split)

        # Juntar Intervenciones:
        # Necesita al menos dos filas seleccionadas y que sean contiguas y del mismo personaje.
        # O, si se seleccionan N filas, juntar la primera con la segunda, si cumplen.
        # Por simplicidad, vamos a permitirlo si hay >= 1 seleccionada, y la lógica interna de merge_interventions
        # se encargará de si es posible con la *siguiente* fila.
        can_merge_check = num_selected >= 1 # La lógica de merge_interventions verifica si hay una siguiente
        if is_main_window_available and "edit_merge_interventions" in self.main_window.actions:
            self.main_window.actions["edit_merge_interventions"].setEnabled(can_merge_check)
        if "edit_merge_interventions" in self.action_buttons:
            self.action_buttons["edit_merge_interventions"].setEnabled(can_merge_check)


        # Copiar IN/OUT a Siguiente: Solo si exactamente UNA fila está seleccionada y NO es la última.
        can_copy_in_out = (num_selected == 1 and selected_model_indices[0].row() < self.pandas_model.rowCount() - 1)
        if is_main_window_available and "edit_copy_in_out" in self.main_window.actions:
            self.main_window.actions["edit_copy_in_out"].setEnabled(can_copy_in_out)
        if "edit_copy_in_out" in self.action_buttons: # Asegúrate que el key coincida con el de setup_buttons
            self.action_buttons["edit_copy_in_out"].setEnabled(can_copy_in_out)

        # Incrementar Escena: Solo si exactamente UNA fila está seleccionada
        can_change_scene = num_selected == 1
        if is_main_window_available and "edit_increment_scene" in self.main_window.actions:
            self.main_window.actions["edit_increment_scene"].setEnabled(can_change_scene)

    def clear_script_state(self):
        self.pandas_model.set_dataframe(pd.DataFrame(columns=self.DF_COLUMN_ORDER))
        self._populate_header_ui({}) 
        self.undo_stack.clear()
        self.current_script_name = None
        self.current_script_path = None
        self.set_unsaved_changes(False)
        self._update_toggle_header_button_text_and_icon()
        # Solicitar actualización del indicador de error de forma diferida
        self._request_error_indicator_update() # MODIFICADO


    def _perform_resize_rows_to_contents(self):
        if self.table_view.isVisible() and self.pandas_model.rowCount() > 0:
            self.table_view.resizeRowsToContents()

    def request_resize_rows_to_contents_deferred(self):
        self._resize_rows_timer.start()

    def adjust_all_row_heights_and_validate(self) -> None:
        self.request_resize_rows_to_contents_deferred()
        for row_idx in range(self.pandas_model.rowCount()):
            self.pandas_model.force_time_validation_update_for_row(row_idx) # Use model's method

    def on_model_layout_changed(self): # Connected to model's layoutChanged signal
        self.adjust_all_row_heights_and_validate()
        self.update_character_completer_and_notify() # Renamed

    def on_model_data_changed(self, top_left_index: QModelIndex, bottom_right_index: QModelIndex, roles: List[int]):
        if not top_left_index.isValid(): return
        self.set_unsaved_changes(True)
        for row in range(top_left_index.row(), bottom_right_index.row() + 1):
            view_col_idx = top_left_index.column() # Usar el índice de la columna de la celda cambiada
            df_col_name = self.pandas_model.get_df_column_name(view_col_idx)
            
            # Si la columna DIÁLOGO o EUSKERA cambian, solicitar redimensionar filas
            if df_col_name in ['DIÁLOGO', 'EUSKERA']:
                self.request_resize_rows_to_contents_deferred()
            elif df_col_name == 'PERSONAJE':
                self.update_character_completer_and_notify()

    def update_character_completer_and_notify(self): # Renamed
        # Re-instantiate delegate to update its completer list
        delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, delegate)
        self.character_name_changed.emit() # Notify CastWindow etc.

    def copy_selected_time(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_index = selected_indexes[0] # First selected cell in the current row/selection
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

    def adjust_dialogs(self) -> None:
        if self.pandas_model.dataframe().empty: return
        self.undo_stack.beginMacro("Ajustar Diálogos")
        changed_any = False
        view_col_dialogue = self.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialogue is None: self.undo_stack.endMacro(); return
        for df_idx in range(self.pandas_model.rowCount()):
            dialog_text_original = str(self.pandas_model.dataframe().at[df_idx, 'DIÁLOGO'])
            adjusted_text = ajustar_dialogo(dialog_text_original)
            if dialog_text_original != adjusted_text:
                command = EditCommand(self, df_idx, view_col_dialogue, dialog_text_original, adjusted_text)
                self.undo_stack.push(command); changed_any = True
        self.undo_stack.endMacro()
        if changed_any: QMessageBox.information(self, "Éxito", "Diálogos ajustados.")
        else: QMessageBox.information(self, "Info", "No hubo diálogos que necesitaban ajuste.")

    def copy_in_out_to_next(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        if not selected_model_indices or len(selected_model_indices) != 1: # Solo para una fila
            QMessageBox.warning(self, "Copiar Tiempos", "Por favor, seleccione exactamente una fila.")
            return

        df_idx_selected = selected_model_indices[0].row() # df_idx de la fila seleccionada
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
        # current_view_row es el índice de la vista. Para el modelo pandas (df_insert_idx),
        # si es -1 (no hay selección y tabla vacía), insertamos en 0.
        # Si es la última fila, insertamos después.
        if current_view_row == -1 and self.pandas_model.rowCount() == 0: # Tabla vacía
            df_insert_idx = 0
        elif current_view_row != -1: # Hay selección o filas
            df_insert_idx = current_view_row + 1
        else: # No hay selección, pero hay filas, añadir al final
            df_insert_idx = self.pandas_model.rowCount()

        command = AddRowCommand(self, df_insert_idx, df_insert_idx)
        self.undo_stack.push(command)

    def remove_row(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows()
        if not selected_model_indices:
            QMessageBox.warning(self, "Eliminar Fila", "Por favor, seleccione una o más filas para eliminar.")
            return
        
        # Obtener los índices de DataFrame (df_row) de las filas seleccionadas en la vista
        df_indices_to_remove = sorted([index.row() for index in selected_model_indices]) # Ya está ordenado ascendente
        
        num_filas_a_eliminar = len(df_indices_to_remove)
        confirm_msg = f"¿Está seguro de que desea eliminar {num_filas_a_eliminar} fila(s)?" \
            if num_filas_a_eliminar > 1 else "¿Está seguro de que desea eliminar la fila seleccionada?"
            
        confirm = QMessageBox.question(self, "Confirmar Eliminación", confirm_msg,
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            # RemoveRowsCommand espera los índices de DataFrame, ordenados ascendentemente
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
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Separar", "Seleccione una fila para separar la intervención."); return
        current_row_index = selected_indexes[0].row()
        dialog_col_view_idx = self.pandas_model.get_view_column_index('DIÁLOGO')
        if dialog_col_view_idx is None: QMessageBox.warning(self, "Error", "No se pudo encontrar la columna de diálogo."); return
        dialog_cell_to_split_index = self.pandas_model.index(current_row_index, dialog_col_view_idx)
        
        cursor_pos = -1; text_that_was_split = None
        if self.last_focused_dialog_index and \
           self.last_focused_dialog_index.row() == dialog_cell_to_split_index.row() and \
           self.last_focused_dialog_index.column() == dialog_cell_to_split_index.column() and \
           self.last_focused_dialog_cursor_pos != -1:
            cursor_pos = self.last_focused_dialog_cursor_pos
            text_that_was_split = self.last_focused_dialog_text
        else:
            QMessageBox.information(self, "Separar Intervención",
                                    "Por favor, edite la celda de diálogo y coloque el cursor\n"
                                    "en el punto de división deseado antes de usar 'Separar'.\n"
                                    "(Asegúrese de que la celda pierda el foco después de editar y antes de separar).")
            self.last_focused_dialog_index = None; self.last_focused_dialog_cursor_pos = -1
            return
        self.last_focused_dialog_index = None; self.last_focused_dialog_cursor_pos = -1 # Reset state
        if text_that_was_split is None: QMessageBox.warning(self, "Error Interno", "No se pudo obtener el texto para dividir."); return
        if not text_that_was_split.strip(): QMessageBox.information(self, "Separar", "No hay texto significativo para dividir."); return
        if not (0 <= cursor_pos <= len(text_that_was_split)):
            QMessageBox.information(self, "Separar", f"Posición de cursor inválida ({cursor_pos}). Debe estar entre 0 y {len(text_that_was_split)}."); return
        
        before_text = text_that_was_split[:cursor_pos].strip(); after_text = text_that_was_split[cursor_pos:].strip()
        if not after_text: QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención después de la posición del cursor."); return
        
        command = SplitInterventionCommand(self, current_row_index, before_text, after_text, text_that_was_split)
        self.undo_stack.push(command)

    def merge_interventions(self) -> None:
        selected_model_indices = self.table_view.selectionModel().selectedRows() # Obtener las filas de la vista
        if not selected_model_indices:
            QMessageBox.warning(self, "Juntar", "Por favor, seleccione la primera de las dos filas a juntar.")
            return

        # Operar sobre la primera fila seleccionada en la vista
        df_idx_curr = selected_model_indices[0].row() # df_idx de la primera fila seleccionada
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
        original_out_first = str(current_df.at[df_idx_curr, 'OUT'])

        command = MergeInterventionsCommand(self, df_idx_curr, merged_dialog, df_idx_next, original_out_first)
        self.undo_stack.push(command)

    def convert_time_code_to_milliseconds(self, time_code: str) -> int:
        try:
            parts = time_code.split(':'); h, m, s, f = map(int, parts)
            if len(parts) != 4 or not all(0 <= x < 100 for x in [h,m,s]) or not (0 <= f < 60): # Basic validation
                raise ValueError("Formato de Timecode inválido")
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0)) # Assuming 25 FPS
        except ValueError: return 0 
        except Exception as e: self.handle_exception(e, f"Error convirtiendo '{time_code}' a milisegundos"); return 0

    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        try:
            if ms < 0: ms = 0
            total_seconds, rem_ms = divmod(ms, 1000)
            h, rem_seconds = divmod(total_seconds, 3600)
            m, s = divmod(rem_seconds, 60)
            f = int(round(rem_ms / (1000.0 / 25.0))) # Assuming 25 FPS
            if f >= 25: f = 24 
            return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"
        except Exception: return "00:00:00:00"

    def update_in_out_from_player(self, action_type: str, position_ms: int) -> None: # Renamed
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        df_idx = selected_indexes[0].row()
        if df_idx >= self.pandas_model.rowCount(): return # Should not happen if selection is valid
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

    def toggle_link_out_to_next_in_checkbox(self, state: int): # Renamed
        self.link_out_to_next_in_enabled = (Qt.CheckState(state) == Qt.CheckState.Checked)

    def select_next_row_after_out_release(self) -> None: # Renamed
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

        if current_view_row >= self.pandas_model.rowCount() - 1: return # No next row
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

    def change_scene(self) -> None: # Called by MainWindow's action
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Cambiar Escena", "Por favor, seleccione una fila."); return
        df_idx = selected_indexes[0].row()
        command = ChangeSceneCommand(self, df_idx)
        self.undo_stack.push(command)

    def has_scene_numbers(self) -> bool: # Dynamic check
        current_df = self.pandas_model.dataframe()
        if 'SCENE' not in current_df.columns or current_df.empty: return False
        # Consider non-empty, non-"1" strings as scene numbers
        unique_scenes = set(str(s).strip() for s in current_df['SCENE'].unique() if pd.notna(s) and str(s).strip())
        # True if more than one unique scene, or one unique scene that isn't "1" or empty.
        return len(unique_scenes) > 1 or \
               (len(unique_scenes) == 1 and ("1" not in unique_scenes and "" not in unique_scenes))


    def handle_ctrl_click_on_cell(self, view_row_idx: int) -> None: # Renamed
        if view_row_idx >= self.pandas_model.rowCount(): return
        model_idx_in = self.pandas_model.index(view_row_idx, self.COL_IN_VIEW)
        in_time_code = str(self.pandas_model.data(model_idx_in, Qt.ItemDataRole.EditRole))
        ms = self.convert_time_code_to_milliseconds(in_time_code)
        self.in_out_signal.emit("IN", ms) # Signal to MainWindow to tell VideoPlayer

    def handle_alt_click_on_cell(self, view_row_idx: int) -> None: # Renamed
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
        if changed_any: self.update_character_completer_and_notify() # This emits character_name_changed

    def find_and_replace(self, find_text: str, replace_text: str, search_in_character: bool = True, search_in_dialogue: bool = True) -> None:
        if self.pandas_model.dataframe().empty or not find_text: return # Do nothing if no find_text
        self.undo_stack.beginMacro("Buscar y Reemplazar")
        changed_count = 0
        view_col_char = self.pandas_model.get_view_column_index('PERSONAJE')
        view_col_dialog = self.pandas_model.get_view_column_index('DIÁLOGO')
        
        # Case-insensitive find, case-sensitive replace (Python's default for str.replace)
        # If truly case-insensitive replace is needed, it's more complex (regex with flags)
        find_text_lower = find_text.lower()

        for df_idx in range(self.pandas_model.rowCount()):
            if search_in_character and view_col_char is not None:
                char_text_orig = str(self.pandas_model.dataframe().at[df_idx, 'PERSONAJE'])
                if find_text_lower in char_text_orig.lower():
                    # Simple replace might not be ideal if find_text has different casing
                    # For now, use Python's default replace which is case-sensitive
                    # A true case-insensitive replace would involve regex or iterating matches
                    new_char_text = char_text_orig.replace(find_text, replace_text) # This is case-sensitive replace
                    if char_text_orig != new_char_text:
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_char, char_text_orig, new_char_text)); changed_count +=1
            
            if search_in_dialogue and view_col_dialog is not None:
                dialog_text_orig = str(self.pandas_model.dataframe().at[df_idx, 'DIÁLOGO'])
                if find_text_lower in dialog_text_orig.lower():
                    new_dialog_text = dialog_text_orig.replace(find_text, replace_text)
                    if dialog_text_orig != new_dialog_text:
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_dialog, dialog_text_orig, new_dialog_text)); changed_count += 1
        self.undo_stack.endMacro()
        QMessageBox.information(self, "Reemplazar", f"{changed_count} reemplazo(s) realizado(s)." if changed_count > 0 else "No se encontraron coincidencias para reemplazar.")

    def update_window_title(self) -> None:
        prefix = "*" if self.unsaved_changes else ""
        script_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window: self.main_window.setWindowTitle(f"{prefix}Editor Guion - {script_name}")

    def set_unsaved_changes(self, changed: bool):
        if self.unsaved_changes != changed:
            self.unsaved_changes = changed
            self.update_window_title()

    def renumerar_escenas_a_uno(self) -> None: # Renamed from renumerar_escenas
        current_df = self.pandas_model.dataframe()
        if not self.has_scene_numbers() and not current_df.empty: # Check if already effectively "1"
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
        
        # Update font for the whole table (excluding delegate-rendered parts like dialog)
        table_font = self.table_view.font()
        table_font.setPointSize(font_size)
        self.table_view.setFont(table_font)
        
        header = self.table_view.horizontalHeader()
        header_font = header.font()
        header_font.setPointSize(font_size) # Keep header font same as table or slightly larger
        header.setFont(header_font)

        self.request_resize_rows_to_contents_deferred()

    def _check_header_fields_completeness(self) -> bool:
        """Verifica si los campos clave de la cabecera están rellenos."""
        if not hasattr(self, 'reference_edit') or \
           not hasattr(self, 'product_edit') or \
           not hasattr(self, 'chapter_edit'): # Si los widgets aún no existen
            return True # Asumir completo para evitar errores tempranos si se llama antes de que todo esté listo

        ref_empty = not self.reference_edit.text().strip()
        prod_empty = not self.product_edit.text().strip()
        chap_empty = not self.chapter_edit.text().strip()
        
        return not (ref_empty or prod_empty or chap_empty)

    # --- FUNCIÓN FALTANTE ---
    def _update_toggle_header_button_text_and_icon(self):
        """Actualiza el texto y el icono del botón para mostrar/ocultar detalles."""
        if not hasattr(self, 'toggle_header_button') or not hasattr(self, 'header_details_widget'):
            # Puede ocurrir si se llama antes de que setup_ui esté completamente terminado
            # o si hay un error en el orden de inicialización.
            return 

        is_visible = self.header_details_widget.isVisible()
        
        if not is_visible: # Si está oculto, el botón dirá "Mostrar..."
            text = " Mostrar Detalles del Guion"
            if not self._check_header_fields_completeness():
                text += " (Campos Incompletos)"
            icon_to_set = self.icon_expand_more
        else: # Si está visible, el botón dirá "Ocultar..."
            text = " Ocultar Detalles del Guion"
            icon_to_set = self.icon_expand_less
        
        self.toggle_header_button.setText(text)
        if self.get_icon and icon_to_set: # Solo si la función get_icon está disponible y el icono no es None
            self.toggle_header_button.setIcon(icon_to_set)
        elif not self.get_icon: # Si no hay get_icon, al menos quitar cualquier icono previo
            self.toggle_header_button.setIcon(QIcon())


    def toggle_header_visibility(self) -> None:
        current_visibility = self.header_details_widget.isVisible()
        self.header_details_widget.setVisible(not current_visibility)
        self._update_toggle_header_button_text_and_icon() # Llamar a la función unificada

class EditCommand(QUndoCommand): 
    def __init__(self, table_window: TableWindow, df_row_index: int, view_col_index: int, old_value: Any, new_value: Any):
        super().__init__()
        self.tw = table_window; self.df_row_idx = df_row_index; self.view_col_idx = view_col_index
        self.old_value = old_value; self.new_value = new_value
        df_col_name = self.tw.pandas_model.get_df_column_name(self.view_col_idx) or f"Col {view_col_index}"
        self.setText(f"Editar '{df_col_name}' en fila {self.df_row_idx + 1}")
    def _apply_value(self, value_to_apply: Any):
        model_idx = self.tw.pandas_model.index(self.df_row_idx, self.view_col_idx)
        if model_idx.isValid(): self.tw.pandas_model.setData(model_idx, value_to_apply, Qt.ItemDataRole.EditRole)
    def undo(self): self._apply_value(self.old_value); self.tw.set_unsaved_changes(True)
    def redo(self): self._apply_value(self.new_value); self.tw.set_unsaved_changes(True)

class AddRowCommand(QUndoCommand): # No changes
    def __init__(self, table_window: TableWindow, view_row_insert_at: int, df_row_insert_at: int):
        super().__init__()
        self.tw = table_window; self.view_row_insert_at = view_row_insert_at; self.df_row_insert_at = df_row_insert_at
        self.new_row_id = -1; self.new_row_data: Optional[Dict] = None; self.setText("Agregar fila")
    def redo(self):
        self.new_row_id = self.tw.pandas_model.get_next_id()
        current_df = self.tw.pandas_model.dataframe()
        scene, char = ("1" if not self.tw.has_scene_numbers() else ""), "" # Default scene based on current state
        if 0 < self.df_row_insert_at <= len(current_df): # Inserting in middle or after existing
            prev_df_idx = self.df_row_insert_at - 1
            scene = str(current_df.at[prev_df_idx, 'SCENE'])
            char = str(current_df.at[prev_df_idx, 'PERSONAJE'])
        elif not current_df.empty and self.df_row_insert_at == len(current_df): # Appending
            last_df_idx = len(current_df) - 1
            scene = str(current_df.at[last_df_idx, 'SCENE'])
            char = str(current_df.at[last_df_idx, 'PERSONAJE'])

        self.new_row_data = {'ID':self.new_row_id, 'SCENE':scene, 'IN':'00:00:00:00', 'OUT':'00:00:00:00', 'PERSONAJE':char, 'DIÁLOGO':''}
        self.tw.pandas_model.insert_row_data(self.df_row_insert_at, self.new_row_data)
        self.tw.table_view.selectRow(self.view_row_insert_at)
        idx_to_scroll = self.tw.pandas_model.index(self.view_row_insert_at, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
        self.setText(f"Agregar fila (ID {self.new_row_id}) en pos. {self.df_row_insert_at + 1}")
    def undo(self):
        if self.new_row_id == -1: return
        # Find by ID first, then fallback to original insertion index if ID not found (should not happen)
        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is None: idx_to_remove = self.df_row_insert_at 
        if idx_to_remove is not None and 0 <= idx_to_remove < self.tw.pandas_model.rowCount():
            self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()

class RemoveRowsCommand(QUndoCommand): # No changes
    def __init__(self, table_window: TableWindow, df_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices = sorted(df_indices_to_remove) # Store original df_indices sorted ascending
        self.removed_data_list: List[Tuple[int, pd.Series]] = [] # Store (original_df_idx, data)
        self.setText(f"Eliminar {len(self.df_indices)} fila(s)")
    def redo(self):
        self.removed_data_list.clear()
        # Remove from highest index to lowest to maintain correct subsequent indices during removal
        for df_idx in sorted(self.df_indices, reverse=True):
            removed_series = self.tw.pandas_model.remove_row_by_df_index(df_idx)
            if removed_series is not None: self.removed_data_list.insert(0, (df_idx, removed_series)) # Keep original index
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
    def undo(self):
        # Insert from lowest original index to highest
        for original_df_idx, row_data_series in sorted(self.removed_data_list, key=lambda x: x[0]):
            self.tw.pandas_model.insert_row_data(original_df_idx, row_data_series.to_dict())
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()

class MoveRowCommand(QUndoCommand): # No changes
    def __init__(self, table_window: TableWindow, df_source_idx: int, df_target_idx: int):
        super().__init__(); self.tw = table_window
        self.df_source_idx, self.df_target_idx = df_source_idx, df_target_idx
        self.setText(f"Mover fila {df_source_idx + 1} a {df_target_idx + 1}")
    def _move(self, from_idx, to_idx):
        if self.tw.pandas_model.move_df_row(from_idx, to_idx):
            self.tw.table_view.selectRow(to_idx) # Select the new position of the moved row
            idx_to_scroll = self.tw.pandas_model.index(to_idx, 0)
            if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
            self.tw.set_unsaved_changes(True)
    def undo(self): self._move(self.df_target_idx, self.df_source_idx) # Reverse the move
    def redo(self): self._move(self.df_source_idx, self.df_target_idx)

class SplitInterventionCommand(QUndoCommand): # No changes
    def __init__(self, table_window: TableWindow, df_idx_split: int, before_txt: str, after_txt: str, text_before_split: str):
        super().__init__(); self.tw = table_window; self.df_idx_split = df_idx_split
        self.before_txt, self.after_txt, self.text_that_was_split = before_txt, after_txt, text_before_split
        self.new_row_id = -1; self.setText(f"Separar intervención en fila {df_idx_split + 1}")
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if not (0 <= self.df_idx_split < len(current_df)): return
        self.new_row_id = self.tw.pandas_model.get_next_id()
        view_col_dialog = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialog is None: return

        original_row_data_for_new_row = current_df.iloc[self.df_idx_split].copy().to_dict()
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx_split, view_col_dialog), self.before_txt, Qt.ItemDataRole.EditRole)
        new_row_full_data = {**original_row_data_for_new_row, 'ID': self.new_row_id, 'DIÁLOGO': self.after_txt}
        self.tw.pandas_model.insert_row_data(self.df_idx_split + 1, new_row_full_data)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx_split + 1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split + 1, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.request_resize_rows_to_contents_deferred()
    def undo(self):
        if self.new_row_id == -1: return
        view_col_dialog = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialog is None: return
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx_split, view_col_dialog), self.text_that_was_split, Qt.ItemDataRole.EditRole)
        
        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is None: idx_to_remove = self.df_idx_split + 1 
        if idx_to_remove is not None and 0 <= idx_to_remove < self.tw.pandas_model.rowCount():
            self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)

        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx_split)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.request_resize_rows_to_contents_deferred()

class MergeInterventionsCommand(QUndoCommand): # No changes
    def __init__(self, tw: TableWindow, df_idx1: int, merged_dlg: str, df_idx2_removed_orig: int, orig_out1: str):
        super().__init__(); self.tw = tw
        self.df_idx1, self.merged_dlg, self.df_idx2_rem_orig, self.orig_out1 = df_idx1, merged_dlg, df_idx2_removed_orig, orig_out1
        self.orig_dlg1: Optional[str] = None; self.data_df_idx2: Optional[pd.Series] = None
        self.setText(f"Juntar filas {df_idx1 + 1} y {df_idx1 + 2}")
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        df_idx_actual_second_row_to_merge = self.df_idx1 + 1 # This is the df index of the second row
        if not (0 <= self.df_idx1 < len(current_df) and 0 <= df_idx_actual_second_row_to_merge < len(current_df)): return
        
        if self.orig_dlg1 is None: self.orig_dlg1 = str(current_df.at[self.df_idx1, 'DIÁLOGO'])
        if self.data_df_idx2 is None: self.data_df_idx2 = current_df.iloc[df_idx_actual_second_row_to_merge].copy()
        
        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')
        if view_col_dlg is None or view_col_out is None: return

        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.merged_dlg, Qt.ItemDataRole.EditRole)
        if 'OUT' in self.data_df_idx2 and pd.notna(self.data_df_idx2['OUT']):
             self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.data_df_idx2['OUT'], Qt.ItemDataRole.EditRole)
        
        self.tw.pandas_model.remove_row_by_df_index(df_idx_actual_second_row_to_merge) # Remove the second row
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
    def undo(self):
        if self.orig_dlg1 is None or self.data_df_idx2 is None: return
        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')
        if view_col_dlg is None or view_col_out is None: return

        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.orig_dlg1, Qt.ItemDataRole.EditRole)
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.orig_out1, Qt.ItemDataRole.EditRole)
        self.tw.pandas_model.insert_row_data(self.df_idx2_rem_orig, self.data_df_idx2.to_dict()) # Re-insert at original second row pos
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer_and_notify()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)

class ChangeSceneCommand(QUndoCommand): # No changes
    def __init__(self, table_window: TableWindow, df_start_idx: int):
        super().__init__(); self.tw = table_window; self.df_start_idx = df_start_idx
        self.old_scenes_map: Dict[int, str] = {}; self.new_scene_base_val: Optional[str] = None
        self.setText(f"Incrementar escena desde fila {df_start_idx + 1}")
    def _apply_scenes(self, scene_map: Dict[int, str], select_row: Optional[int]):
        view_col_scene = self.tw.pandas_model.get_view_column_index('SCENE')
        if view_col_scene is None: return
        for df_idx, scene_val in scene_map.items():
            if 0 <= df_idx < self.tw.pandas_model.rowCount(): # Check bounds
                self.tw.pandas_model.setData(self.tw.pandas_model.index(df_idx, view_col_scene), scene_val, Qt.ItemDataRole.EditRole)
        if select_row is not None and 0 <= select_row < self.tw.pandas_model.rowCount():
            self.tw.table_view.selectRow(select_row)
            idx_to_scroll = self.tw.pandas_model.index(select_row, 0)
            if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll, QAbstractItemView.ScrollHint.EnsureVisible)
        self.tw.set_unsaved_changes(True)
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if not (0 <= self.df_start_idx < len(current_df)): self.setText(f"Incrementar escena (fila {self.df_start_idx+1} inválida)"); return
        
        self.old_scenes_map.clear(); new_scenes_map_for_redo: Dict[int, str] = {}
        scene_val_at_start_str = str(current_df.at[self.df_start_idx, 'SCENE']).strip()
        
        try:
            scene_val_at_start_num = int(scene_val_at_start_str) if scene_val_at_start_str.isdigit() else 0
        except ValueError: # If not a simple integer (e.g. "1A", or empty)
            QMessageBox.warning(self.tw, "Cambiar Escena", f"El valor de escena en la fila {self.df_start_idx + 1} ('{scene_val_at_start_str}') no es un número simple. No se puede autoincrementar.")
            self.setText("Incrementar escena (base no numérica simple)")
            return # Do not proceed if base is not a simple number
            
        self.new_scene_base_val = str(scene_val_at_start_num + 1)
        for df_idx in range(self.df_start_idx, len(current_df)):
            self.old_scenes_map[df_idx] = str(current_df.at[df_idx, 'SCENE'])
            new_scenes_map_for_redo[df_idx] = self.new_scene_base_val
        
        self._apply_scenes(new_scenes_map_for_redo, self.df_start_idx)
        self.setText(f"Incrementar escena a '{self.new_scene_base_val}' desde fila {self.df_start_idx + 1}")
    def undo(self):
        if not self.old_scenes_map: self.setText(f"Incrementar escena (sin datos para undo)"); return # Nothing to undo
        self._apply_scenes(self.old_scenes_map, self.df_start_idx)
        # Text reset by redo or initial if redo failed

