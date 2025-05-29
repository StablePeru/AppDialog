# guion_editor/widgets/table_window.py

import json
import os
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize, QModelIndex, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QColor, QIntValidator, QBrush, QAction, QFontMetrics, QIcon
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QHeaderView, QInputDialog
)
from PyQt6.QtGui import QShortcut, QUndoStack, QUndoCommand

from guion_editor.widgets.custom_table_view import CustomTableView
from guion_editor.models.pandas_table_model import PandasTableModel
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.delegates.guion_delegate import DialogDelegate # Importar DialogDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.utils.guion_manager import GuionManager


class TableWindow(QWidget):
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    COL_ID_VIEW = 0
    COL_SCENE_VIEW = 1
    COL_IN_VIEW = 2
    COL_OUT_VIEW = 3
    COL_CHARACTER_VIEW = 4
    COL_DIALOGUE_VIEW = 5

    VIEW_COLUMN_NAMES = ["ID", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO"]
    VIEW_TO_DF_COL_MAP = {
        COL_ID_VIEW: 'ID',
        COL_SCENE_VIEW: 'SCENE',
        COL_IN_VIEW: 'IN',
        COL_OUT_VIEW: 'OUT',
        COL_CHARACTER_VIEW: 'PERSONAJE',
        COL_DIALOGUE_VIEW: 'DIÁLOGO'
    }

    class KeyPressFilter(QObject):
        def __init__(self, parent_window: 'TableWindow') -> None:
            super().__init__()
            self.table_window = parent_window
        def eventFilter(self, obj: QObject, event: QEvent) -> bool:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
                    if hasattr(self.table_window, 'video_player_widget') and self.table_window.video_player_widget:
                        self.table_window.video_player_widget.start_out_timer()
                    return True
            elif event.type() == QEvent.Type.KeyRelease:
                if event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
                    if hasattr(self.table_window, 'video_player_widget') and self.table_window.video_player_widget:
                        self.table_window.video_player_widget.stop_out_timer()
                    return True
            return super().eventFilter(obj, event)

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None,
                 guion_manager: Optional[GuionManager] = None, get_icon_func=None):
        super().__init__()
        self.get_icon = get_icon_func
        self.main_window = main_window
        self.current_font_size = 9 # Default font size, MainWindow puede actualizarlo

        self._resize_rows_timer = QTimer(self)
        self._resize_rows_timer.setSingleShot(True)
        self._resize_rows_timer.setInterval(100) 
        self._resize_rows_timer.timeout.connect(self._perform_resize_rows_to_contents)

        self.video_player_widget = video_player_widget
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out)
            self.video_player_widget.out_released.connect(self.select_next_row_and_set_in)

        self.guion_manager = guion_manager if guion_manager else GuionManager()
        self.key_filter = TableWindow.KeyPressFilter(self)
        self.installEventFilter(self.key_filter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.pandas_model = PandasTableModel(column_map=self.VIEW_TO_DF_COL_MAP, 
                                             view_column_names=self.VIEW_COLUMN_NAMES)

        self.unsaved_changes = False
        self.undo_stack = QUndoStack(self)
        self.has_scene_numbers = False
        self.current_script_name: Optional[str] = None
        self.current_script_path: Optional[str] = None
        self._tw_shortcuts: List[QShortcut] = []
        self.clipboard_text: str = ""

        self.reference_number = "" # Estos podrían ser parte de un objeto "HeaderData"
        self.product_name = ""
        self.chapter_number = ""
        self.selected_type = ""

        if self.get_icon:
            self.icon_expand_less = self.get_icon("toggle_header_collapse_icon.svg")
            self.icon_expand_more = self.get_icon("toggle_header_expand_icon.svg")
        else:
            self.icon_expand_less = QIcon()
            self.icon_expand_more = QIcon()

        self.setup_ui()
        self.clear_script_state()

    def setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        icon_size_header_toggle = QSize(20, 20)

        self.toggle_header_button = QPushButton()
        self.toggle_header_button.setIconSize(icon_size_header_toggle)
        self.toggle_header_button.setObjectName("toggle_header_button_css")
        self.toggle_header_button.clicked.connect(self.toggle_header_visibility)
        main_layout.addWidget(self.toggle_header_button)

        self.header_details_widget = QWidget()
        self.header_form_layout = QFormLayout()
        self.header_details_widget.setLayout(self.header_form_layout)

        self.setup_header_fields(self.header_form_layout)
        main_layout.addWidget(self.header_details_widget)

        self.setup_buttons(main_layout)
        self.setup_table_view(main_layout)
        self.load_stylesheet()

        self.header_details_widget.setVisible(True) # Inicialmente visible
        self.toggle_header_visibility() # Lo oculta
        self.toggle_header_visibility() # Lo muestra (estado inicial deseado)

    def setup_header_fields(self, form_layout: QFormLayout) -> None:
        self.reference_edit = QLineEdit()
        self.reference_edit.setValidator(QIntValidator(0, 999999, self))
        self.reference_edit.setMaxLength(6)
        self.reference_edit.setPlaceholderText("Máximo 6 dígitos")
        form_layout.addRow("Número de referencia:", self.reference_edit)

        self.product_edit = QLineEdit()
        self.product_edit.setPlaceholderText("Nombre del producto")
        form_layout.addRow("Nombre del Producto:", self.product_edit)

        self.chapter_edit = QLineEdit()
        self.chapter_edit.setPlaceholderText("Número de capítulo")
        form_layout.addRow("N.º Capítulo:", self.chapter_edit)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Ficcion", "Animacion", "Documental"])
        form_layout.addRow("Tipo:", self.type_combo)

        for widget in [self.reference_edit, self.product_edit, self.chapter_edit, self.type_combo]:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(lambda _text, w=widget: self._header_field_changed(w))
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(lambda _idx, w=widget: self._header_field_changed(w))
    
    def _header_field_changed(self, widget_sender: QWidget):
        """Slot para manejar cambios en los campos de cabecera y marcar unsaved_changes."""
        self.set_unsaved_changes(True)
        # Actualizar las variables de instancia si se usan en otro lugar
        self.reference_number = self.reference_edit.text()
        self.product_name = self.product_edit.text()
        self.chapter_number = self.chapter_edit.text()
        self.selected_type = self.type_combo.currentText()

    def toggle_header_visibility(self) -> None:
        if self.header_details_widget.isVisible():
            self.header_details_widget.setVisible(False)
            self.toggle_header_button.setText(" Mostrar Detalles del Guion")
            if self.get_icon: self.toggle_header_button.setIcon(self.icon_expand_more)
        else:
            self.header_details_widget.setVisible(True)
            self.toggle_header_button.setText(" Ocultar Detalles del Guion")
            if self.get_icon: self.toggle_header_button.setIcon(self.icon_expand_less)

    def setup_buttons(self, layout: QVBoxLayout) -> None:
        buttons_layout = QHBoxLayout()
        icon_size = QSize(18, 18)
        actions_map = [
            (" Agregar Línea", self.add_new_row, "add_row_icon.svg", False),
            (" Eliminar Fila", self.remove_row, "delete_row_icon.svg", False),
            ("", self.move_row_up, "move_up_icon.svg", True),
            ("", self.move_row_down, "move_down_icon.svg", True),
            (" Ajustar Diálogos", self.adjust_dialogs, "adjust_dialogs_icon.svg", False),
            (" Separar", self.split_intervention, "split_intervention_icon.svg", False),
            (" Juntar", self.merge_interventions, "merge_intervention_icon.svg", False),
        ]
        for text, method, icon_name, only_icon in actions_map:
            button = QPushButton(text)
            if self.get_icon and icon_name:
                button.setIcon(self.get_icon(icon_name))
                button.setIconSize(icon_size)
            if only_icon:
                 button.setFixedSize(QSize(icon_size.width() + 16, icon_size.height() + 12))
                 button.setToolTip(text.strip() if text.strip() else method.__name__.replace("_", " ").title())
            button.clicked.connect(method)
            buttons_layout.addWidget(button)
        layout.addLayout(buttons_layout)

    def setup_table_view(self, layout: QVBoxLayout) -> None:
        self.table_view = CustomTableView()
        self.table_view.setModel(self.pandas_model)

        self.table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.table_view.setAlternatingRowColors(True)

        layout.addWidget(self.table_view)
        
        self.table_view.setColumnHidden(self.COL_ID_VIEW, True)

        self.table_view.setItemDelegateForColumn(self.COL_IN_VIEW, TimeCodeDelegate(self.table_view))
        self.table_view.setItemDelegateForColumn(self.COL_OUT_VIEW, TimeCodeDelegate(self.table_view))
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view))
        
        # Usar el tamaño de fuente actual de TableWindow para el DialogDelegate
        self.dialog_delegate = DialogDelegate(parent=self.table_view, font_size=self.current_font_size)
        self.table_view.setItemDelegateForColumn(self.COL_DIALOGUE_VIEW, self.dialog_delegate)

        self.table_view.cellCtrlClicked.connect(self.handle_ctrl_click)
        self.table_view.cellAltClicked.connect(self.handle_alt_click)
        
        self.pandas_model.dataChanged.connect(self.on_model_data_changed)
        self.pandas_model.layoutChangedSignal.connect(self.on_model_layout_changed)

        self.table_view.horizontalHeader().setStretchLastSection(True)
        self.table_view.verticalHeader().setVisible(False) 

    def load_stylesheet(self) -> None:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')
            if not os.path.exists(css_path):
                alt_css_path = os.path.join(current_file_dir, 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path): css_path = alt_css_path
                else: print(f"Advertencia: Stylesheet no encontrado: {css_path}"); return
            with open(css_path, 'r', encoding='utf-8') as f:
                self.table_view.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar CSS: {str(e)}")

    def _populate_header_ui(self, header_data: Dict[str, Any]):
        self.reference_edit.setText(header_data.get("reference_number", ""))
        self.product_edit.setText(header_data.get("product_name", ""))
        self.chapter_edit.setText(header_data.get("chapter_number", ""))
        tipo = header_data.get("type", "Ficcion") # Default
        idx = self.type_combo.findText(tipo, Qt.MatchFlag.MatchExactly)
        if idx != -1: self.type_combo.setCurrentIndex(idx)
        else: self.type_combo.setCurrentIndex(0) # Default a 'Ficcion' si no se encuentra

    def _get_header_data_from_ui(self) -> Dict[str, Any]:
        return {
            "reference_number": self.reference_edit.text(),
            "product_name": self.product_edit.text(),
            "chapter_number": self.chapter_edit.text(),
            "type": self.type_combo.currentText()
        }

    def _post_load_script_actions(self, file_path: str, df: pd.DataFrame, header_data: Dict[str, Any], has_scenes: bool):
        self.pandas_model.set_dataframe(df)
        self._populate_header_ui(header_data)
        # self.has_scene_numbers se actualiza en on_model_layout_changed
        
        self.undo_stack.clear()
        self.current_script_name = os.path.basename(file_path)
        self.current_script_path = file_path
        self.update_window_title() # Llama a set_unsaved_changes(False) implícitamente si es necesario
        self.set_unsaved_changes(False) # Asegurar que esté en False después de cargar

        if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
            self.main_window.add_to_recent_files(file_path)
        QMessageBox.information(self, "Éxito", f"Guion '{self.current_script_name}' cargado.")

    def open_docx_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Guion DOCX", "", "Documentos Word (*.docx)")
        if file_name: self.load_from_docx_path(file_name)
    def load_from_docx_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_docx(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e: self.handle_exception(e, f"Error DOCX: {file_path}"); self.clear_script_state()
    def import_from_excel_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar Excel", "", "Archivos Excel (*.xlsx)")
        if path: self.load_from_excel_path(path)
    def load_from_excel_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_excel(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e: self.handle_exception(e, f"Error Excel: {file_path}"); self.clear_script_state()
    def load_from_json_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cargar JSON", "", "Archivos JSON (*.json)")
        if path: self.load_from_json_path(path)
    def load_from_json_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_json(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e: self.handle_exception(e, f"Error JSON: {file_path}"); self.clear_script_state()

    def _generate_default_filename(self, extension: str) -> str:
        header_data = self._get_header_data_from_ui()
        base_name = "guion"
        if header_data.get("product_name") and header_data.get("chapter_number"):
            base_name = f"{header_data['product_name']}_{header_data['chapter_number']}"
        elif header_data.get("product_name"):
            base_name = f"{header_data['product_name']}"
        return f"{base_name}.{extension}"

    def export_to_excel_dialog(self) -> bool:
        current_df = self.pandas_model.dataframe()
        if current_df.empty: QMessageBox.information(self, "Exportar", "No hay datos."); return False
        header_data = self._get_header_data_from_ui()
        default_filename = self._generate_default_filename("xlsx")
        path, _ = QFileDialog.getSaveFileName(self, "Exportar a Excel", default_filename, "Archivos Excel (*.xlsx)")
        if path:
            try:
                self.guion_manager.save_to_excel(path, current_df, header_data)
                QMessageBox.information(self, "Éxito", "Guardado en Excel.")
                self.current_script_name = os.path.basename(path); self.current_script_path = path
                self.set_unsaved_changes(False)
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e: self.handle_exception(e, "Error guardando Excel"); return False
        return False
    def save_to_json_dialog(self) -> bool:
        current_df = self.pandas_model.dataframe()
        if current_df.empty: QMessageBox.information(self, "Guardar", "No hay datos."); return False
        header_data = self._get_header_data_from_ui()
        default_filename = self._generate_default_filename("json")
        path, _ = QFileDialog.getSaveFileName(self, "Guardar como JSON", default_filename, "Archivos JSON (*.json)")
        if path:
            try:
                self.guion_manager.save_to_json(path, current_df, header_data)
                QMessageBox.information(self, "Éxito", "Guardado en JSON.")
                self.current_script_name = os.path.basename(path); self.current_script_path = path
                self.set_unsaved_changes(False)
                if self.main_window: self.main_window.add_to_recent_files(path)
                return True
            except Exception as e: self.handle_exception(e, "Error guardando JSON"); return False
        return False

    def clear_script_state(self):
        self.pandas_model.set_dataframe(pd.DataFrame(columns=list(self.VIEW_TO_DF_COL_MAP.values())))
        self._populate_header_ui({})
        # self.has_scene_numbers se actualiza en on_model_layout_changed
        self.undo_stack.clear()
        self.current_script_name = None
        self.current_script_path = None
        self.update_window_title()
        self.set_unsaved_changes(False)

    def _perform_resize_rows_to_contents(self):
        if self.table_view.isVisible() and self.pandas_model.rowCount() > 0:
            self.table_view.resizeRowsToContents()
    def request_resize_rows_to_contents_deferred(self):
        self._resize_rows_timer.start()

    def adjust_all_row_heights_and_validate(self) -> None:
        self.request_resize_rows_to_contents_deferred()
        for row_idx in range(self.pandas_model.rowCount()):
            self.validate_in_out_time_for_model(row_idx)

    def on_model_layout_changed(self):
        self.adjust_all_row_heights_and_validate()
        current_df = self.pandas_model.dataframe()
        if 'SCENE' in current_df.columns:
            unique_scenes = set(str(s).strip() for s in current_df['SCENE'].unique() if pd.notna(s))
            self.has_scene_numbers = len(unique_scenes) > 1 or \
                                     (len(unique_scenes) == 1 and "1" not in unique_scenes and "" not in unique_scenes)
        else: self.has_scene_numbers = False
        self.update_character_completer()

    def on_model_data_changed(self, top_left_index: QModelIndex, bottom_right_index: QModelIndex, roles: List[int]):
        if not top_left_index.isValid(): return

        for row in range(top_left_index.row(), bottom_right_index.row() + 1):
            view_col_idx = top_left_index.column()
            df_col_name = self.pandas_model.get_df_column_name(view_col_idx)

            if df_col_name == 'SCENE':
                current_df = self.pandas_model.dataframe()
                if 'SCENE' in current_df.columns:
                    unique_scenes = set(str(s).strip() for s in current_df['SCENE'].unique() if pd.notna(s))
                    self.has_scene_numbers = len(unique_scenes) > 1 or \
                                             (len(unique_scenes) == 1 and "1" not in unique_scenes and "" not in unique_scenes)
            elif df_col_name == 'DIÁLOGO':
                self.request_resize_rows_to_contents_deferred()
            elif df_col_name == 'PERSONAJE':
                self.update_character_completer()
                self.character_name_changed.emit()
            # La validación de IN/OUT y su repintado de fondo es manejado por el modelo en su setData
        self.set_unsaved_changes(True)

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
        df_idx = current_index.row(); view_col_idx = current_index.column()
        if view_col_idx == self.COL_IN_VIEW or view_col_idx == self.COL_OUT_VIEW:
            old_value = str(self.pandas_model.data(current_index, Qt.ItemDataRole.EditRole))
            if old_value != self.clipboard_text:
                command = EditCommand(self, df_idx, view_col_idx, old_value, self.clipboard_text)
                self.undo_stack.push(command)

    def adjust_dialogs(self) -> None:
        current_df = self.pandas_model.dataframe()
        if current_df.empty: return
        self.undo_stack.beginMacro("Ajustar Diálogos")
        changed_any = False
        view_col_dialogue = self.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialogue is None: self.undo_stack.endMacro(); return
        for df_idx in range(len(current_df)):
            dialog_text_original = str(current_df.at[df_idx, 'DIÁLOGO'])
            adjusted_text = ajustar_dialogo(dialog_text_original)
            if dialog_text_original != adjusted_text:
                command = EditCommand(self, df_idx, view_col_dialogue, dialog_text_original, adjusted_text)
                self.undo_stack.push(command); changed_any = True
        self.undo_stack.endMacro()
        if changed_any: QMessageBox.information(self, "Éxito", "Diálogos ajustados.")
        else: QMessageBox.information(self, "Info", "No hubo diálogos que ajustar.")

    def copy_in_out_to_next(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Copiar", "Seleccione fila."); return
        df_idx_selected = selected_indexes[0].row()
        if df_idx_selected >= self.pandas_model.rowCount() - 1:
            QMessageBox.warning(self, "Copiar", "No en la última fila."); return
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
        # QUndoCommand se encarga de set_unsaved_changes
        # QMessageBox.information(self, "Copiado", "Tiempos IN/OUT copiados.") # Quizás demasiado verboso

    def add_new_row(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        current_view_row = selected_indexes[0].row() if selected_indexes else -1
        # En modelo simple, view_row == df_row. Insertar después de la seleccionada, o al final.
        df_insert_idx = current_view_row + 1 if current_view_row != -1 else self.pandas_model.rowCount()
        command = AddRowCommand(self, df_insert_idx, df_insert_idx) # view_row_to_insert_at, df_row_to_insert_at
        self.undo_stack.push(command)
    def remove_row(self) -> None:
        selected_indexes = self.table_view.selectionModel().selectedRows() # Múltiples QModelIndex
        if not selected_indexes: QMessageBox.warning(self, "Eliminar", "Seleccione fila(s)."); return
        # Los índices de vista son los mismos que los del df en este modelo simple
        df_indices_to_remove = sorted([index.row() for index in selected_indexes])
        confirm = QMessageBox.question(self, "Confirmar", f"¿Eliminar {len(df_indices_to_remove)} fila(s)?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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

    def split_intervention(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Separar", "Seleccione fila."); return
        df_idx = selected_indexes[0].row()
        
        dialog_col_view_idx = self.pandas_model.get_view_column_index('DIÁLOGO')
        if dialog_col_view_idx is None: return
        dialog_model_index = self.pandas_model.index(df_idx, dialog_col_view_idx)
        text = str(self.pandas_model.data(dialog_model_index, Qt.ItemDataRole.EditRole))

        # Para obtener la posición del cursor de forma fiable, el delegado debería exponerla
        # o la acción debería ocurrir mientras el editor está activo.
        # Usamos QInputDialog como fallback.
        cursor_pos = -1
        # Intentar obtener el editor activo si la celda está en edición
        # Esto es complejo y no siempre fiable con QTableView y delegados.
        # current_editor_widget = self.table_view.focusWidget()
        # if isinstance(current_editor_widget, QTextEdit) and \
        #    self.table_view.editIndex() == dialog_model_index: # editIndex() es de QAbstractItemView
        #    cursor_pos = current_editor_widget.textCursor().position()
        # else:
        # Solicitar posición del cursor al usuario
        cursor_pos_str, ok = QInputDialog.getText(self, "Posición de División",
                                                    f"Texto: '{text[:30]}...' (longitud: {len(text)})\n"
                                                    "Introduce la posición del cursor (0-{len(text)-1}) para dividir:",
                                                    QLineEdit.EchoMode.Normal, "")
        if not ok or not cursor_pos_str: return
        try: 
            cursor_pos = int(cursor_pos_str)
            if not (0 < cursor_pos < len(text)): # No permitir dividir al puro inicio o fin
                QMessageBox.information(self, "Separar", "Posición de cursor inválida para división."); return
        except ValueError: QMessageBox.warning(self, "Error", "Posición debe ser un número."); return
        
        before_text = text[:cursor_pos].strip()
        after_text = text[cursor_pos:].strip()
        if not after_text: QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención."); return
        
        command = SplitInterventionCommand(self, df_idx, before_text, after_text)
        self.undo_stack.push(command)

    def merge_interventions(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: QMessageBox.warning(self, "Juntar", "Seleccione fila."); return
        current_view_row = selected_indexes[0].row()
        df_idx_curr, df_idx_next = current_view_row, current_view_row + 1
        if df_idx_next >= self.pandas_model.rowCount(): QMessageBox.warning(self, "Juntar", "Seleccione fila no última."); return
        
        current_df = self.pandas_model.dataframe()
        char_curr = str(current_df.at[df_idx_curr, 'PERSONAJE'])
        char_next = str(current_df.at[df_idx_next, 'PERSONAJE'])
        if char_curr != char_next: QMessageBox.warning(self, "Juntar", "Intervenciones de distinto personaje."); return
        
        dialog_curr = str(current_df.at[df_idx_curr, 'DIÁLOGO'])
        dialog_next = str(current_df.at[df_idx_next, 'DIÁLOGO'])
        merged_dialog = f"{dialog_curr.strip()} {dialog_next.strip()}".strip()
        original_out_first = str(current_df.at[df_idx_curr, 'OUT'])
        
        command = MergeInterventionsCommand(self, df_idx_curr, merged_dialog, df_idx_next, original_out_first)
        self.undo_stack.push(command)
        # QMessageBox.information(self, "Juntar", "Intervenciones juntadas.") # Quizás QUndoCommand lo dice

    def convert_time_code_to_milliseconds(self, time_code: str) -> int:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: raise ValueError("Formato TC inválido")
            h, m, s, f = map(int, parts)
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0)) 
        except ValueError: return 0 
        except Exception as e: self.handle_exception(e, f"Error convirtiendo '{time_code}' a ms"); return 0
    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        try:
            if ms < 0: ms = 0
            MS_PER_HOUR, MS_PER_MINUTE, MS_PER_SECOND = 3600000, 60000, 1000
            h, rem_h = divmod(ms, MS_PER_HOUR); m, rem_m = divmod(rem_h, MS_PER_MINUTE)
            s, rem_s_ms = divmod(rem_m, MS_PER_SECOND); f = int(round(rem_s_ms / (1000.0 / 25.0))) 
            if f >= 25: f = 24 
            return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"
        except: return "00:00:00:00"

    def update_in_out(self, action: str, position_ms: int) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_model_idx = selected_indexes[0]
        df_idx = current_model_idx.row()
        if df_idx >= self.pandas_model.rowCount(): return

        time_code_str = self.convert_milliseconds_to_time_code(position_ms)
        view_col_to_update = self.COL_IN_VIEW if action.upper() == "IN" else self.COL_OUT_VIEW if action.upper() == "OUT" else -1
        if view_col_to_update == -1: return

        model_idx_to_update = self.pandas_model.index(df_idx, view_col_to_update)
        old_value = str(self.pandas_model.data(model_idx_to_update, Qt.ItemDataRole.EditRole))
        if time_code_str != old_value:
            command = EditCommand(self, df_idx, view_col_to_update, old_value, time_code_str)
            self.undo_stack.push(command)

    def select_next_row_and_set_in(self) -> None:
        selected_indexes = self.table_view.selectedIndexes()
        if not selected_indexes: return
        current_view_row = selected_indexes[0].row()
        if current_view_row >= self.pandas_model.rowCount() - 1: return
        
        df_idx_curr = current_view_row
        current_df = self.pandas_model.dataframe()
        current_out_time_str = str(current_df.at[df_idx_curr, 'OUT'])
        
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
        if not selected_indexes: QMessageBox.warning(self, "Escena", "Seleccione fila."); return
        df_idx = selected_indexes[0].row()
        command = ChangeSceneCommand(self, df_idx)
        self.undo_stack.push(command)

    def validate_in_out_time_for_model(self, view_row_idx: int) -> bool:
        self.pandas_model.force_time_validation_update_for_row(view_row_idx)
        return self.pandas_model._time_validation_status.get(view_row_idx, True)

    def handle_ctrl_click(self, view_row_idx: int) -> None:
        df_idx = view_row_idx 
        if df_idx >= self.pandas_model.rowCount(): return
        model_idx_in = self.pandas_model.index(df_idx, self.COL_IN_VIEW)
        in_time_code = str(self.pandas_model.data(model_idx_in, Qt.ItemDataRole.EditRole))
        ms = self.convert_time_code_to_milliseconds(in_time_code)
        self.in_out_signal.emit("IN", ms)
    def handle_alt_click(self, view_row_idx: int) -> None:
        df_idx = view_row_idx
        if df_idx >= self.pandas_model.rowCount(): return
        model_idx_out = self.pandas_model.index(df_idx, self.COL_OUT_VIEW)
        out_time_code = str(self.pandas_model.data(model_idx_out, Qt.ItemDataRole.EditRole))
        ms = self.convert_time_code_to_milliseconds(out_time_code)
        self.in_out_signal.emit("OUT", ms)

    def get_character_names_from_model(self) -> List[str]:
        current_df = self.pandas_model.dataframe()
        if current_df.empty or 'PERSONAJE' not in current_df.columns: return []
        return sorted(list(set(str(name) for name in current_df['PERSONAJE'].unique() if pd.notna(name) and str(name).strip())))
    def update_character_completer(self) -> None:
        delegate = CharacterDelegate(get_names_callback=self.get_character_names_from_model, parent=self.table_view)
        self.table_view.setItemDelegateForColumn(self.COL_CHARACTER_VIEW, delegate)
    def update_character_name(self, old_name: str, new_name: str) -> None:
        current_df = self.pandas_model.dataframe()
        if not new_name.strip(): QMessageBox.warning(self, "Nombre Inválido", "Nombre no puede ser vacío."); return
        self.undo_stack.beginMacro(f"Cambiar '{old_name}' a '{new_name}'")
        changed_any = False
        view_col_char = self.pandas_model.get_view_column_index('PERSONAJE')
        if view_col_char is None: self.undo_stack.endMacro(); return
        for df_idx in range(len(current_df)):
            if str(current_df.at[df_idx, 'PERSONAJE']) == old_name:
                command = EditCommand(self, df_idx, view_col_char, old_name, new_name)
                self.undo_stack.push(command); changed_any = True
        self.undo_stack.endMacro()
        if changed_any: self.update_character_completer(); self.character_name_changed.emit()

    def find_and_replace(self, find_text: str, replace_text: str, search_in_character: bool = True, search_in_dialogue: bool = True) -> None:
        current_df = self.pandas_model.dataframe()
        if current_df.empty: return
        self.undo_stack.beginMacro("Buscar y Reemplazar")
        changed_count = 0
        view_col_char = self.pandas_model.get_view_column_index('PERSONAJE')
        view_col_dialog = self.pandas_model.get_view_column_index('DIÁLOGO')
        for df_idx in range(len(current_df)):
            if search_in_character and view_col_char is not None:
                char_text = str(current_df.at[df_idx, 'PERSONAJE'])
                if find_text.lower() in char_text.lower():
                    new_char_text = char_text.replace(find_text, replace_text)
                    if char_text != new_char_text:
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_char, char_text, new_char_text)); changed_count +=1
            if search_in_dialogue and view_col_dialog is not None:
                dialog_text = str(current_df.at[df_idx, 'DIÁLOGO'])
                if find_text.lower() in dialog_text.lower():
                    new_dialog_text = dialog_text.replace(find_text, replace_text)
                    if dialog_text != new_dialog_text:
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_dialog, dialog_text, new_dialog_text)); changed_count += 1
        self.undo_stack.endMacro()
        if changed_count > 0: QMessageBox.information(self, "Reemplazar", f"{changed_count} reemplazos.")
        else: QMessageBox.information(self, "Reemplazar", "No se encontraron coincidencias.")

    def update_window_title(self) -> None:
        prefix = "*" if self.unsaved_changes else ""
        script_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window: self.main_window.setWindowTitle(f"{prefix}Editor Guion - {script_name}")
    def set_unsaved_changes(self, changed: bool):
        if self.unsaved_changes != changed:
            self.unsaved_changes = changed
            self.update_window_title()
    def renumerar_escenas(self) -> None:
        current_df = self.pandas_model.dataframe()
        if not self.has_scene_numbers and not current_df.empty: # Solo si no hay números de escena o son todos "1"
            self.undo_stack.beginMacro("Renumerar Escenas a 1")
            changed_any = False
            view_col_scene = self.pandas_model.get_view_column_index('SCENE')
            if view_col_scene is not None:
                for df_idx in range(len(current_df)):
                    old_scene = str(current_df.at[df_idx, 'SCENE'])
                    if old_scene != "1":
                        self.undo_stack.push(EditCommand(self, df_idx, view_col_scene, old_scene, "1")); changed_any = True
            self.undo_stack.endMacro()
            # if changed_any: self.has_scene_numbers = True # Actualizado por on_model_data_changed

    def get_next_id(self) -> int: return self.pandas_model.get_next_id()
    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]: return self.pandas_model.find_df_index_by_id(id_value)
    def find_table_row_by_id(self, id_value: int) -> Optional[int]: return self.pandas_model.find_df_index_by_id(id_value)
    def get_dataframe_column_name(self, table_col_index: int) -> Optional[str]: return self.pandas_model.get_df_column_name(table_col_index)
    def handle_exception(self, exception: Exception, message: str) -> None:
        import traceback
        print(f"ERROR: {message}\n{str(exception)}"); traceback.print_exc()
        QMessageBox.critical(self, "Error", f"{message}:\n{str(exception)}")

    def apply_font_size_to_dialogs(self, font_size: int) -> None:
        self.current_font_size = font_size # Guardar para uso futuro del delegado
        if hasattr(self, 'dialog_delegate') and self.dialog_delegate:
            self.dialog_delegate.setFontSize(font_size)
        self.request_resize_rows_to_contents_deferred()

# --- QUndoCommand Subclasses ---
# (Se asume que las clases QUndoCommand ya están adaptadas para funcionar con el modelo
#  y que TableWindow (self.tw) les da acceso al self.pandas_model.
#  Sus métodos redo/undo llaman a self.tw.pandas_model.setData(), insert_row_data(), etc.)

class EditCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_row_index: int, view_col_index: int, old_value: Any, new_value: Any):
        super().__init__()
        self.tw = table_window
        self.df_row_idx = df_row_index
        self.view_col_idx = view_col_index
        self.old_value = old_value
        self.new_value = new_value
        df_col_name = self.tw.pandas_model.get_df_column_name(self.view_col_idx)
        self.setText(f"Editar {df_col_name} en fila {self.df_row_idx}") # Usar df_row_idx para mensaje
    def _apply_value(self, value_to_apply: Any):
        model_idx = self.tw.pandas_model.index(self.df_row_idx, self.view_col_idx)
        if model_idx.isValid():
            self.tw.pandas_model.setData(model_idx, value_to_apply, Qt.ItemDataRole.EditRole)
    def undo(self): self._apply_value(self.old_value); self.tw.set_unsaved_changes(True)
    def redo(self): self._apply_value(self.new_value); self.tw.set_unsaved_changes(True)

class AddRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, view_row_insert_at: int, df_row_insert_at: int):
        super().__init__()
        self.tw = table_window
        self.view_row_insert_at = view_row_insert_at
        self.df_row_insert_at = df_row_insert_at
        self.new_row_id = -1; self.new_row_data: Optional[Dict] = None
        self.setText("Agregar fila")
    def redo(self):
        self.new_row_id = self.tw.pandas_model.get_next_id()
        self.setText(f"Agregar fila (ID {self.new_row_id})")
        current_df = self.tw.pandas_model.dataframe()
        scene, char = "1", ""
        if 0 < self.df_row_insert_at <= len(current_df):
            prev_df_idx = self.df_row_insert_at - 1
            scene, char = str(current_df.at[prev_df_idx, 'SCENE']), str(current_df.at[prev_df_idx, 'PERSONAJE'])
        elif not current_df.empty and self.df_row_insert_at == len(current_df): # Append
            last_df_idx = len(current_df) - 1
            scene, char = str(current_df.at[last_df_idx, 'SCENE']), str(current_df.at[last_df_idx, 'PERSONAJE'])
        self.new_row_data = {'ID':self.new_row_id, 'SCENE':scene, 'IN':'00:00:00:00', 'OUT':'00:00:00:00', 'PERSONAJE':char, 'DIÁLOGO':''}
        self.tw.pandas_model.insert_row_data(self.df_row_insert_at, self.new_row_data)
        self.tw.table_view.selectRow(self.view_row_insert_at)
        idx_to_scroll = self.tw.pandas_model.index(self.view_row_insert_at, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
    def undo(self):
        if self.new_row_id == -1: return
        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is None: idx_to_remove = self.df_row_insert_at # Fallback
        if idx_to_remove is not None and 0 <= idx_to_remove < self.tw.pandas_model.rowCount():
            self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()

class RemoveRowsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices = sorted(df_indices_to_remove) # Índices del DataFrame en el modelo
        self.removed_data_list: List[pd.Series] = []
        self.setText(f"Eliminar {len(self.df_indices)} fila(s)")
    def redo(self):
        self.removed_data_list.clear()
        for df_idx in sorted(self.df_indices, reverse=True): # De mayor a menor
            removed_series = self.tw.pandas_model.remove_row_by_df_index(df_idx)
            if removed_series is not None: self.removed_data_list.insert(0, removed_series)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
    def undo(self):
        for original_df_idx, row_data_series in zip(self.df_indices, self.removed_data_list):
            self.tw.pandas_model.insert_row_data(original_df_idx, row_data_series.to_dict())
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()

class MoveRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_source_idx: int, df_target_idx: int):
        super().__init__(); self.tw = table_window
        self.df_source_idx, self.df_target_idx = df_source_idx, df_target_idx
        self.setText(f"Mover fila {df_source_idx} a {df_target_idx}") # Simplificado
    def _move(self, from_idx, to_idx):
        if self.tw.pandas_model.move_df_row(from_idx, to_idx):
            self.tw.table_view.selectRow(to_idx) # Seleccionar la fila en su nueva posición
            idx_to_scroll = self.tw.pandas_model.index(to_idx, 0)
            if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)
            self.tw.set_unsaved_changes(True)
    def undo(self): self._move(self.df_target_idx, self.df_source_idx)
    def redo(self): self._move(self.df_source_idx, self.df_target_idx)

class SplitInterventionCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_idx_split: int, before_txt: str, after_txt: str):
        super().__init__(); self.tw = table_window
        self.df_idx_split, self.before_txt, self.after_txt = df_idx_split, before_txt, after_txt
        self.original_dialog: Optional[str] = None; self.new_row_id = -1
        self.setText(f"Separar intervención en fila {df_idx_split}")
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if self.df_idx_split >= len(current_df): return
        if self.original_dialog is None: self.original_dialog = str(current_df.at[self.df_idx_split, 'DIÁLOGO'])
        self.new_row_id = self.tw.pandas_model.get_next_id()
        view_col_dialog = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialog is None: return
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx_split, view_col_dialog), self.before_txt)
        
        original_row_data = current_df.iloc[self.df_idx_split].copy().to_dict()
        original_row_data['ID'] = self.new_row_id
        original_row_data['DIÁLOGO'] = self.after_txt
        # Opcional: ajustar IN/OUT para la nueva fila
        # original_row_data['IN'] = current_df.at[self.df_idx_split, 'OUT']
        
        self.tw.pandas_model.insert_row_data(self.df_idx_split + 1, original_row_data)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
        self.tw.table_view.selectRow(self.df_idx_split)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)
    def undo(self):
        if self.original_dialog is None or self.new_row_id == -1: return
        view_col_dialog = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        if view_col_dialog is None: return
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx_split, view_col_dialog), self.original_dialog)
        idx_to_remove = self.tw.pandas_model.find_df_index_by_id(self.new_row_id)
        if idx_to_remove is not None: self.tw.pandas_model.remove_row_by_df_index(idx_to_remove)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
        self.tw.table_view.selectRow(self.df_idx_split)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx_split, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)

class MergeInterventionsCommand(QUndoCommand):
    def __init__(self, tw: TableWindow, df_idx1: int, merged_dlg: str, df_idx2_removed_orig: int, orig_out1: str):
        super().__init__(); self.tw = tw
        self.df_idx1, self.merged_dlg, self.df_idx2_rem_orig, self.orig_out1 = df_idx1, merged_dlg, df_idx2_removed_orig, orig_out1
        self.orig_dlg1: Optional[str] = None; self.data_df_idx2: Optional[pd.Series] = None
        self.setText(f"Juntar filas {df_idx1} y {df_idx1 + 1}")
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        df_idx_actual_second = self.df_idx1 + 1
        if self.df_idx1 >= len(current_df) or df_idx_actual_second >= len(current_df): return
        if self.orig_dlg1 is None: self.orig_dlg1 = str(current_df.at[self.df_idx1, 'DIÁLOGO'])
        if self.data_df_idx2 is None: self.data_df_idx2 = current_df.iloc[df_idx_actual_second].copy()
        
        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')
        if view_col_dlg is None or view_col_out is None: return

        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.merged_dlg)
        if 'OUT' in self.data_df_idx2:
             self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.data_df_idx2['OUT'])
        self.tw.pandas_model.remove_row_by_df_index(df_idx_actual_second)
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)
    def undo(self):
        if self.orig_dlg1 is None or self.data_df_idx2 is None: return
        view_col_dlg = self.tw.pandas_model.get_view_column_index('DIÁLOGO')
        view_col_out = self.tw.pandas_model.get_view_column_index('OUT')
        if view_col_dlg is None or view_col_out is None: return
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_dlg), self.orig_dlg1)
        self.tw.pandas_model.setData(self.tw.pandas_model.index(self.df_idx1, view_col_out), self.orig_out1)
        self.tw.pandas_model.insert_row_data(self.df_idx2_rem_orig, self.data_df_idx2.to_dict())
        self.tw.set_unsaved_changes(True); self.tw.update_character_completer()
        self.tw.table_view.selectRow(self.df_idx1)
        idx_to_scroll = self.tw.pandas_model.index(self.df_idx1, 0)
        if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)

class ChangeSceneCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_start_idx: int):
        super().__init__(); self.tw = table_window; self.df_start_idx = df_start_idx
        self.old_scenes_map: Dict[int, str] = {} # df_idx -> old_scene_str
        self.setText(f"Cambiar escena desde fila {df_start_idx}")
    def _apply_scenes(self, scene_map: Dict[int, str], select_row: Optional[int]):
        view_col_scene = self.tw.pandas_model.get_view_column_index('SCENE')
        if view_col_scene is None: return
        for df_idx, scene_val in scene_map.items():
            if df_idx < self.tw.pandas_model.rowCount():
                self.tw.pandas_model.setData(self.tw.pandas_model.index(df_idx, view_col_scene), scene_val)
        if select_row is not None and 0 <= select_row < self.tw.pandas_model.rowCount():
            self.tw.table_view.selectRow(select_row)
            idx_to_scroll = self.tw.pandas_model.index(select_row, 0)
            if idx_to_scroll.isValid(): self.tw.table_view.scrollTo(idx_to_scroll)
        self.tw.set_unsaved_changes(True)
    def redo(self):
        current_df = self.tw.pandas_model.dataframe()
        if self.df_start_idx >= len(current_df): return
        self.old_scenes_map.clear(); new_scenes_map: Dict[int, str] = {}
        scene_val_at_start = 0
        try:
            txt_at_start = str(current_df.at[self.df_start_idx, 'SCENE']).strip()
            if txt_at_start: scene_val_at_start = int(txt_at_start)
        except: scene_val_at_start = 0
        new_scene_str = str(scene_val_at_start + 1)
        for df_idx in range(self.df_start_idx, len(current_df)):
            self.old_scenes_map[df_idx] = str(current_df.at[df_idx, 'SCENE'])
            new_scenes_map[df_idx] = new_scene_str
        self._apply_scenes(new_scenes_map, self.df_start_idx)
    def undo(self):
        self._apply_scenes(self.old_scenes_map, self.df_start_idx)