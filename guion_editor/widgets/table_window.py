import json
import os
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize
from PyQt6.QtGui import QFont, QKeySequence, QColor, QIntValidator, QBrush, QAction, QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtGui import QShortcut, QUndoStack, QUndoCommand

from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.widgets.custom_table_widget import CustomTableWidget
from guion_editor.widgets.custom_text_edit import CustomTextEdit
from guion_editor.utils.guion_manager import GuionManager

VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.white)
INVALID_TIME_BG_COLOR = QColor(255, 200, 200)

class TableWindow(QWidget):
    in_out_signal = pyqtSignal(str, int)
    character_name_changed = pyqtSignal()

    COL_ID = 0
    COL_SCENE = 1
    COL_IN = 2
    COL_OUT = 3
    COL_CHARACTER = 4
    COL_DIALOGUE = 5

    TABLE_TO_DF_COL_MAP = {
        COL_ID: 'ID',
        COL_SCENE: 'SCENE',
        COL_IN: 'IN',
        COL_OUT: 'OUT',
        COL_CHARACTER: 'PERSONAJE',
        COL_DIALOGUE: 'DIÁLOGO'
    }

    class KeyPressFilter(QObject):
        def __init__(self, parent_window: 'TableWindow') -> None:
            super().__init__()
            self.table_window = parent_window

        def eventFilter(self, obj: QObject, event: QEvent) -> bool:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
                    self.table_window.video_player_widget.start_out_timer()
                    return True
            elif event.type() == QEvent.Type.KeyRelease:
                if event.key() == Qt.Key.Key_F6 and not event.isAutoRepeat():
                    self.table_window.video_player_widget.stop_out_timer()
                    return True
            return super().eventFilter(obj, event)

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None, guion_manager: Optional[GuionManager] = None):
        super().__init__()

        self.main_window = main_window
        
        self.video_player_widget = video_player_widget
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out)
            self.video_player_widget.out_released.connect(self.select_next_row_and_set_in)

        self.guion_manager = guion_manager if guion_manager else GuionManager()

        self.key_filter = self.KeyPressFilter(self)
        self.installEventFilter(self.key_filter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.dataframe = pd.DataFrame(columns=list(self.TABLE_TO_DF_COL_MAP.values()))
        self.unsaved_changes = False
        self.undo_stack = QUndoStack(self)
        self.has_scene_numbers = False
        self.current_script_name: Optional[str] = None
        self.current_script_path: Optional[str] = None
        self._tw_shortcuts: List[QShortcut] = []
        self.clipboard_text: str = ""

        self.reference_number = ""
        self.product_name = ""
        self.chapter_number = ""
        self.selected_type = ""

        self.setup_ui()
        # self.setup_shortcuts() # Descomentar si se usa
        self.clear_script_state()

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.setup_header_fields(layout)
        self.setup_buttons(layout)
        self.setup_table_widget(layout)
        self.load_stylesheet()

    """
    def setup_shortcuts(self) -> None:
        self._tw_shortcuts.clear() 
        shortcuts_map = {
            "Ctrl+Z": self.undo_stack.undo,
            "Ctrl+Y": self.undo_stack.redo,
            "Ctrl+B": self.copy_in_out_to_next,
            "Ctrl+C": self.copy_selected_time,
            "Ctrl+V": self.paste_time,
        }
        for key_str, slot_func in shortcuts_map.items():
            shortcut = QShortcut(QKeySequence(key_str), self)
            shortcut.activated.connect(slot_func)
            self._tw_shortcuts.append(shortcut)
    """

    def setup_header_fields(self, layout: QVBoxLayout) -> None:
        form_layout = QFormLayout()
        
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
        
        layout.addLayout(form_layout)

        self.reference_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.product_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.chapter_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.type_combo.currentIndexChanged.connect(lambda: self.set_unsaved_changes(True))

    def setup_buttons(self, layout: QVBoxLayout) -> None:
        buttons_layout = QHBoxLayout()
        actions_map = [
            ("Agregar Línea", self.add_new_row),
            ("Eliminar Fila", self.remove_row),
            ("Mover Arriba", self.move_row_up),
            ("Mover Abajo", self.move_row_down),
            ("Ajustar Diálogos", self.adjust_dialogs),
            ("Separar Intervención", self.split_intervention),
            ("Juntar Intervenciones", self.merge_interventions)
        ]
        for text, method in actions_map:
            button = QPushButton(text)
            button.clicked.connect(method)
            buttons_layout.addWidget(button)
        layout.addLayout(buttons_layout)

    def setup_table_widget(self, layout: QVBoxLayout) -> None:
        self.table_widget = CustomTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.SelectedClicked
        )
        layout.addWidget(self.table_widget)
        self.columns = ["ID", "SCENE", "IN", "OUT", "PERSONAJE", "DIÁLOGO"]
        self.table_widget.setColumnCount(len(self.columns))
        self.table_widget.setHorizontalHeaderLabels(self.columns)
        
        if "ID" in self.columns:
            self.table_widget.setColumnHidden(self.columns.index("ID"), True)
        
        self.table_widget.setItemDelegateForColumn(self.COL_IN, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(self.COL_OUT, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(self.COL_CHARACTER, CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget))
        
        self.table_widget.cellCtrlClicked.connect(self.handle_ctrl_click)
        self.table_widget.cellAltClicked.connect(self.handle_alt_click)
        self.table_widget.itemChanged.connect(self.on_item_changed)
        self.table_widget.horizontalHeader().setStretchLastSection(True)

    def load_stylesheet(self) -> None:
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            # Ruta corregida asumiendo estructura: project_root/guion_editor/widgets/ y project_root/guion_editor/styles/
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')

            if not os.path.exists(css_path):
                # Considerar una ruta alternativa si la estructura es diferente
                alt_css_path = os.path.join(current_file_dir, 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    return # No se pudo cargar el stylesheet
            
            with open(css_path, 'r', encoding='utf-8') as f:
                self.table_widget.setStyleSheet(f.read())
        except Exception as e:
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar stylesheet para la tabla: {str(e)}")

    def _populate_header_ui(self, header_data: Dict[str, Any]):
        self.reference_edit.setText(header_data.get("reference_number", ""))
        self.product_edit.setText(header_data.get("product_name", ""))
        self.chapter_edit.setText(header_data.get("chapter_number", ""))
        tipo = header_data.get("type", "Ficcion")
        if tipo in ["Ficcion", "Animacion", "Documental"]:
            self.type_combo.setCurrentText(tipo)
        else:
            self.type_combo.setCurrentText("Ficcion")

    def _get_header_data_from_ui(self) -> Dict[str, Any]:
        data = {
            "reference_number": self.reference_edit.text(),
            "product_name": self.product_edit.text(),
            "chapter_number": self.chapter_edit.text(),
            "type": self.type_combo.currentText()
        }
        return data

    def _post_load_script_actions(self, file_path: str, df: pd.DataFrame, header_data: Dict[str, Any], has_scenes: bool):
        self.dataframe = df
        self._populate_header_ui(header_data)
        self.has_scene_numbers = has_scenes
        
        self.populate_table()
        self.undo_stack.clear()

        self.current_script_name = os.path.basename(file_path)
        self.current_script_path = file_path
        self.update_window_title()
        self.set_unsaved_changes(False)

        if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
            self.main_window.add_to_recent_files(file_path)
        
        QMessageBox.information(self, "Éxito", f"Guion '{self.current_script_name}' cargado correctamente.")

    def open_docx_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Guion DOCX", "", "Documentos de Word (*.docx);;Todos los archivos (*.*)")
        if file_name:
            self.load_from_docx_path(file_name)

    def load_from_docx_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_docx(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e:
            self.handle_exception(e, f"Error al cargar DOCX: {file_path}")
            self.clear_script_state()

    def import_from_excel_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar Guion desde Excel", "", "Archivos Excel (*.xlsx);;Todos los archivos (*.*)")
        if path:
            self.load_from_excel_path(path)

    def load_from_excel_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_excel(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e:
            self.handle_exception(e, f"Error al cargar Excel: {file_path}")
            self.clear_script_state()

    def export_to_excel_dialog(self) -> bool:
        """Exporta los datos actuales a un archivo Excel, abriendo diálogo."""
        if self.dataframe.empty:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return False

        self._update_dataframe_from_table()
        header_data = self._get_header_data_from_ui()
        
        default_filename = "guion.xlsx"
        if header_data.get("product_name") and header_data.get("chapter_number"):
            default_filename = f"{header_data['product_name']}_{header_data['chapter_number']}.xlsx"
        elif header_data.get("product_name"):
            default_filename = f"{header_data['product_name']}.xlsx"
        
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Guion a Excel", default_filename, "Archivos Excel (*.xlsx);;Todos los archivos (*.*)")
        if path:
            try:
                self.guion_manager.save_to_excel(path, self.dataframe, header_data)
                QMessageBox.information(self, "Éxito", "Datos exportados correctamente a Excel.")
                self.current_script_name = os.path.basename(path)
                self.current_script_path = path
                self.set_unsaved_changes(False)
                self.update_window_title()
                if self.main_window:
                    self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al exportar a Excel")
                return False
        return False

    def load_from_json_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Cargar Guion desde JSON", "", "Archivos JSON (*.json);;Todos los archivos (*.*)")
        if path:
            self.load_from_json_path(path)

    def load_from_json_path(self, file_path: str):
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_json(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e:
            self.handle_exception(e, f"Error al cargar JSON: {file_path}")
            self.clear_script_state()

    def save_to_json_dialog(self) -> bool:
        """Guarda los datos actuales en un archivo JSON, abriendo diálogo."""
        if self.dataframe.empty:
            QMessageBox.information(self, "Guardar", "No hay datos para guardar.")
            return False

        self._update_dataframe_from_table()
        header_data = self._get_header_data_from_ui()

        default_filename = "guion.json"
        if header_data.get("product_name") and header_data.get("chapter_number"):
            default_filename = f"{header_data['product_name']}_{header_data['chapter_number']}.json"
        elif header_data.get("product_name"):
            default_filename = f"{header_data['product_name']}.json"

        path, _ = QFileDialog.getSaveFileName(self, "Guardar Guion como JSON", default_filename, "Archivos JSON (*.json);;Todos los archivos (*.*)")
        if path:
            try:
                self.guion_manager.save_to_json(path, self.dataframe, header_data)
                QMessageBox.information(self, "Éxito", "Datos guardados correctamente en JSON.")
                self.current_script_name = os.path.basename(path)
                self.current_script_path = path
                self.set_unsaved_changes(False)
                self.update_window_title()
                if self.main_window:
                    self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al guardar en JSON")
                return False
        return False

    def clear_script_state(self):
        """Resetea el estado del guion a vacío."""
        self.dataframe = pd.DataFrame(columns=list(self.TABLE_TO_DF_COL_MAP.values()))
        self._populate_header_ui({})
        self.has_scene_numbers = False
        self.populate_table()
        self.undo_stack.clear()
        self.current_script_name = None
        self.current_script_path = None
        self.update_window_title()
        self.set_unsaved_changes(False)

    def populate_table(self) -> None:
        try:
            self.table_widget.blockSignals(True)
            self.table_widget.clearContents()
            
            if self.dataframe.empty:
                self.table_widget.setRowCount(0)
                self.table_widget.blockSignals(False)
                return

            self.table_widget.setRowCount(self.dataframe.shape[0])

            for i in range(self.dataframe.shape[0]):
                for col_index, df_col_name in self.TABLE_TO_DF_COL_MAP.items():
                    table_col_name = self.columns[col_index]

                    if df_col_name not in self.dataframe.columns:
                        item_text = ""
                        if table_col_name == "DIÁLOGO":
                            widget = self.create_text_edit(item_text, i, col_index)
                            self.table_widget.setCellWidget(i, col_index, widget)
                        else:
                            item = self.create_table_item(item_text, col_index)
                            self.table_widget.setItem(i, col_index, item)
                        continue

                    item_value = self.dataframe.at[i, df_col_name]
                    item_text = str(item_value if pd.notna(item_value) else "")

                    if table_col_name == "DIÁLOGO":
                        dialog_text = item_text
                        widget = self.create_text_edit(dialog_text, i, col_index)
                        self.table_widget.setCellWidget(i, col_index, widget)
                    else:
                        item = self.create_table_item(item_text, col_index)
                        self.table_widget.setItem(i, col_index, item)
                self.adjust_row_height(i)
                self.validate_in_out_time(i)

            if self.table_widget.columnCount() > 0:
                 self.table_widget.horizontalHeader().setStretchLastSection(True)

        except Exception as e:
            self.handle_exception(e, "Error al llenar la tabla")
        finally:
            self.table_widget.blockSignals(False)

    def create_text_edit(self, text: str, row: int, column: int) -> CustomTextEdit:
        text_edit = CustomTextEdit()
        text_edit.setPlainText(text)
        text_edit.editingFinished.connect(self.on_editing_finished_text_edit)
        return text_edit

    def create_table_item(self, text: str, column: int) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        return item

    def adjust_row_height(self, row: int) -> None:
        try:
            widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
            if widget and isinstance(widget, QTextEdit):
                doc = widget.document()
                total_height = doc.size().height() + widget.contentsMargins().top() + widget.contentsMargins().bottom() + 10
                self.table_widget.setRowHeight(row, int(max(total_height, widget.fontMetrics().height() + 10)))
        except Exception as e:
            self.handle_exception(e, f"Error al ajustar la altura de la fila {row}: {e}")

    def adjust_all_row_heights(self) -> None:
        for row in range(self.table_widget.rowCount()):
            self.adjust_row_height(row)

    def on_item_changed(self, item: QTableWidgetItem) -> None:
        """Maneja el evento cuando cambia el contenido de una celda (NO QTextEdit)."""
        try:
            row, column = item.row(), item.column()
            df_col_name = self.get_dataframe_column_name(column)
            if not df_col_name or row >= len(self.dataframe):
                return

            new_text = item.text()
            old_text = str(self.dataframe.at[row, df_col_name])

            if df_col_name == 'SCENE':
                try:
                    if new_text.strip(): int(new_text)
                except ValueError:
                    QMessageBox.warning(self, "Error de Tipo", f"El valor '{new_text}' no es un número válido para 'SCENE'.")
                    item.setText(old_text)
                    return
            
            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
                if column == self.COL_SCENE:
                    self.has_scene_numbers = True
                if column in [self.COL_IN, self.COL_OUT]:
                    self.validate_in_out_time(row)
        except Exception as e:
            self.handle_exception(e, f"Error al actualizar celda en la tabla (itemChanged): {e}")

    def on_editing_finished_text_edit(self) -> None:
        """Maneja el evento cuando se finaliza la edición de un CustomTextEdit (diálogo)."""
        try:
            text_edit_widget = self.sender()
            if not isinstance(text_edit_widget, CustomTextEdit):
                return

            found_pos = None
            for r_idx in range(self.table_widget.rowCount()):
                if self.table_widget.cellWidget(r_idx, self.COL_DIALOGUE) == text_edit_widget:
                    found_pos = (r_idx, self.COL_DIALOGUE)
                    break
            
            if not found_pos:
                return

            row, column = found_pos
            df_col_name = self.get_dataframe_column_name(column)
            if not df_col_name or row >= len(self.dataframe):
                return

            new_text = text_edit_widget.toPlainText()
            old_text = str(self.dataframe.at[row, df_col_name])

            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
                self.adjust_row_height(row)
        except Exception as e:
            self.handle_exception(e, f"Error al finalizar la edición del texto del diálogo: {e}")

    def _update_dataframe_from_table(self) -> None:
        """Actualiza self.dataframe con los datos de la QTableWidget. Crucial antes de guardar."""
        try:
            if self.dataframe.empty and self.table_widget.rowCount() == 0:
                return

            temp_data = []
            for row_idx in range(self.table_widget.rowCount()):
                row_dict = {}
                try:
                    id_val = int(self.table_widget.item(row_idx, self.COL_ID).text())
                    row_dict['ID'] = id_val
                except (ValueError, AttributeError):
                    pass

                for col_idx_table, df_col_name in self.TABLE_TO_DF_COL_MAP.items():
                    if col_idx_table == self.COL_DIALOGUE:
                        widget = self.table_widget.cellWidget(row_idx, self.COL_DIALOGUE)
                        row_dict[df_col_name] = widget.toPlainText() if widget else ""
                    else:
                        item = self.table_widget.item(row_idx, col_idx_table)
                        row_dict[df_col_name] = item.text() if item else ""
                temp_data.append(row_dict)
            
            if temp_data:
                new_df = pd.DataFrame(temp_data)
                if 'ID' in new_df.columns:
                    new_df['ID'] = pd.to_numeric(new_df['ID'], errors='coerce').fillna(-1).astype(int)
                if 'SCENE' in new_df.columns:
                    new_df['SCENE'] = new_df['SCENE'].astype(str)
                self.dataframe = new_df
            else:
                self.dataframe = pd.DataFrame(columns=list(self.TABLE_TO_DF_COL_MAP.values()))

        except Exception as e:
            self.handle_exception(e, f"Error crítico al actualizar DataFrame desde la tabla: {e}")

    def copy_selected_time(self) -> None:
        try:
            current_item = self.table_widget.currentItem()
            if current_item and (self.table_widget.currentColumn() == self.COL_IN or self.table_widget.currentColumn() == self.COL_OUT):
                self.clipboard_text = current_item.text()
        except Exception as e:
            self.handle_exception(e, "Error al copiar el tiempo")
    
    def paste_time(self) -> None:
        try:
            if not self.clipboard_text: return
            current_row = self.table_widget.currentRow()
            current_col = self.table_widget.currentColumn()
            if current_row >= 0 and (current_col == self.COL_IN or current_col == self.COL_OUT):
                current_item = self.table_widget.item(current_row, current_col)
                if current_item:
                    old_value = current_item.text()
                    if old_value != self.clipboard_text:
                        current_item.setText(self.clipboard_text)
        except Exception as e:
            self.handle_exception(e, "Error al pegar el tiempo")

    def adjust_dialogs(self) -> None:
        try:
            self._update_dataframe_from_table()
            self.undo_stack.beginMacro("Ajustar Diálogos")
            changed_any = False
            for i in range(len(self.dataframe)):
                dialog_text_original = str(self.dataframe.at[i, 'DIÁLOGO'])
                adjusted_text = ajustar_dialogo(dialog_text_original)
                
                if dialog_text_original != adjusted_text:
                    command = EditCommand(self, i, self.COL_DIALOGUE, dialog_text_original, adjusted_text)
                    self.undo_stack.push(command)
                    changed_any = True
            self.undo_stack.endMacro()
            if changed_any:
                self.set_unsaved_changes(True)
                QMessageBox.information(self, "Éxito", "Diálogos ajustados correctamente.")
            else:
                QMessageBox.information(self, "Información", "No hubo diálogos que necesitaran ajuste.")
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al ajustar diálogos")

    def copy_in_out_to_next(self) -> None:
        try:
            selected_row_idx = self.table_widget.currentRow()
            if selected_row_idx == -1 or selected_row_idx >= len(self.dataframe) - 1:
                QMessageBox.warning(self, "Copiar IN/OUT", "Seleccione una fila válida que no sea la última.")
                return

            self._update_dataframe_from_table()

            in_time = str(self.dataframe.at[selected_row_idx, 'IN'])
            out_time = str(self.dataframe.at[selected_row_idx, 'OUT'])
            next_row_idx = selected_row_idx + 1

            self.undo_stack.beginMacro("Copiar IN/OUT a Siguiente")
            
            old_in_next = str(self.dataframe.at[next_row_idx, 'IN'])
            if in_time != old_in_next:
                cmd_in = EditCommand(self, next_row_idx, self.COL_IN, old_in_next, in_time)
                self.undo_stack.push(cmd_in)

            old_out_next = str(self.dataframe.at[next_row_idx, 'OUT'])
            if out_time != old_out_next:
                cmd_out = EditCommand(self, next_row_idx, self.COL_OUT, old_out_next, out_time)
                self.undo_stack.push(cmd_out)
            
            self.undo_stack.endMacro()
            
            if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Copiar IN/OUT"):
                 self.set_unsaved_changes(True)
                 QMessageBox.information(self, "Copiar IN/OUT", "Tiempos IN y OUT copiados a la siguiente intervención.")
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al copiar IN/OUT")

    def add_new_row(self) -> None:
        try:
            selected_row = self.table_widget.currentRow()
            insert_at_row_idx = selected_row + 1 if selected_row != -1 else self.table_widget.rowCount()
            
            command = AddRowCommand(self, insert_at_row_idx)
            self.undo_stack.push(command)
            self.set_unsaved_changes(True)
        except Exception as e:
            self.handle_exception(e, "Error al agregar una nueva fila")

    def remove_row(self) -> None:
        try:
            selected_indexes = self.table_widget.selectionModel().selectedRows()
            if not selected_indexes:
                QMessageBox.warning(self, "Eliminar Filas", "Por favor, selecciona al menos una fila para eliminar.")
                return

            rows_to_remove_view_indices = sorted([index.row() for index in selected_indexes], reverse=True)
            
            confirm = QMessageBox.question(self, "Confirmar Eliminación", "¿Estás seguro?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                self._update_dataframe_from_table()
                ids_to_remove = []
                valid_rows_df_indices = []

                for row_view_idx in rows_to_remove_view_indices:
                    id_item = self.table_widget.item(row_view_idx, self.COL_ID)
                    if id_item:
                        try:
                            row_id = int(id_item.text())
                            df_idx = self.find_dataframe_index_by_id(row_id)
                            if df_idx is not None:
                                ids_to_remove.append(row_id)
                                valid_rows_df_indices.append(df_idx)
                        except ValueError:
                             pass # ID no numérico
                    else:
                        pass # Sin ID
                if ids_to_remove:
                    command = RemoveRowsCommand(self, sorted(valid_rows_df_indices))
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
                elif rows_to_remove_view_indices:
                    QMessageBox.information(self, "Información", "No se eliminaron filas del modelo de datos (posiblemente filas nuevas sin guardar o sin ID).")
        except Exception as e:
            self.handle_exception(e, "Error al eliminar las filas")

    def move_row_up(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx > 0:
                self._update_dataframe_from_table()

                id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not id_item: return
                
                current_row_id = int(id_item.text())
                df_idx_source = self.find_dataframe_index_by_id(current_row_id)

                if df_idx_source is not None and df_idx_source > 0:
                    command = MoveRowCommand(self, df_idx_source, df_idx_source - 1)
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia arriba")

    def move_row_down(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx < self.table_widget.rowCount() - 1:
                self._update_dataframe_from_table()

                id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not id_item: return
                
                current_row_id = int(id_item.text())
                df_idx_source = self.find_dataframe_index_by_id(current_row_id)

                if df_idx_source is not None and df_idx_source < len(self.dataframe) - 1:
                    command = MoveRowCommand(self, df_idx_source, df_idx_source + 1)
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia abajo")

    def split_intervention(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx == -1:
                QMessageBox.warning(self, "Separar", "Selecciona una fila.")
                return

            self._update_dataframe_from_table()

            dialog_widget = self.table_widget.cellWidget(selected_row_view_idx, self.COL_DIALOGUE)
            if not isinstance(dialog_widget, QTextEdit): return

            id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            if not id_item: return
            current_row_id = int(id_item.text())
            df_idx = self.find_dataframe_index_by_id(current_row_id)
            if df_idx is None: return

            text = dialog_widget.toPlainText()
            cursor_pos = dialog_widget.textCursor().position()

            if cursor_pos == 0 or cursor_pos >= len(text):
                QMessageBox.information(self, "Separar", "Coloca el cursor en el punto de división (no al inicio o fin).")
                return

            before_text = text[:cursor_pos].strip()
            after_text = text[cursor_pos:].strip()

            if not after_text:
                 QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención después del cursor.")
                 return

            command = SplitInterventionCommand(self, df_idx, before_text, after_text)
            self.undo_stack.push(command)
            self.set_unsaved_changes(True)
        except Exception as e:
            self.handle_exception(e, "Error al separar intervención")

    def merge_interventions(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx == -1 or selected_row_view_idx >= self.table_widget.rowCount() - 1:
                QMessageBox.warning(self, "Juntar", "Selecciona una fila que no sea la última.")
                return

            self._update_dataframe_from_table()

            id_item_curr = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            id_item_next = self.table_widget.item(selected_row_view_idx + 1, self.COL_ID)
            if not id_item_curr or not id_item_next: return

            curr_row_id = int(id_item_curr.text())
            next_row_id = int(id_item_next.text())

            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            df_idx_next = self.find_dataframe_index_by_id(next_row_id)

            if df_idx_curr is None or df_idx_next is None: return
            if df_idx_next != df_idx_curr + 1:
                QMessageBox.critical(self, "Error Interno", "Las filas seleccionadas para juntar no son consecutivas en el modelo de datos.")
                return

            char_curr = str(self.dataframe.at[df_idx_curr, 'PERSONAJE'])
            char_next = str(self.dataframe.at[df_idx_next, 'PERSONAJE'])

            if char_curr != char_next:
                QMessageBox.warning(self, "Juntar", "Las intervenciones deben ser del mismo personaje.")
                return

            dialog_curr = str(self.dataframe.at[df_idx_curr, 'DIÁLOGO']).strip()
            dialog_next = str(self.dataframe.at[df_idx_next, 'DIÁLOGO']).strip()
            
            merged_dialog = f"{dialog_curr} {dialog_next}".strip()

            command = MergeInterventionsCommand(self, df_idx_curr, merged_dialog, df_idx_next)
            self.undo_stack.push(command)
            self.set_unsaved_changes(True)
            QMessageBox.information(self, "Juntar", "Intervenciones juntadas.")
        except Exception as e:
            self.handle_exception(e, "Error al juntar intervenciones")

    def convert_time_code_to_milliseconds(self, time_code: str) -> int:
        try:
            parts = time_code.split(':')
            if len(parts) != 4: raise ValueError("Formato TC inválido")
            h, m, s, f = map(int, parts)
            return (h * 3600 + m * 60 + s) * 1000 + int((f / 25) * 1000) # Asume 25 FPS
        except ValueError:
            return 0
        except Exception as e:
            self.handle_exception(e, f"Error convirtiendo '{time_code}' a ms")
            return 0

    def convert_milliseconds_to_time_code(self, ms: int) -> str:
        try:
            if ms < 0: ms = 0
            MS_PER_HOUR = 3600000
            MS_PER_MINUTE = 60000
            MS_PER_SECOND = 1000
            h, rem_h = divmod(ms, MS_PER_HOUR)
            m, rem_m = divmod(rem_h, MS_PER_MINUTE)
            s, rem_s_ms = divmod(rem_m, MS_PER_SECOND)
            f = int(rem_s_ms / (1000 / 25))
            return f"{h:02}:{m:02}:{s:02}:{f:02}"
        except Exception:
            return "00:00:00:00"

    def update_in_out(self, action: str, position_ms: int) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx == -1 :
                return

            self._update_dataframe_from_table()

            id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            if not id_item: return
            current_row_id = int(id_item.text())
            df_idx = self.find_dataframe_index_by_id(current_row_id)
            if df_idx is None or df_idx >= len(self.dataframe): return

            time_code_str = self.convert_milliseconds_to_time_code(position_ms)
            col_to_update = -1
            old_value = ""

            if action.upper() == "IN":
                col_to_update = self.COL_IN
                old_value = str(self.dataframe.at[df_idx, 'IN'])
            elif action.upper() == "OUT":
                col_to_update = self.COL_OUT
                old_value = str(self.dataframe.at[df_idx, 'OUT'])
            
            if col_to_update != -1 and time_code_str != old_value:
                command = EditCommand(self, df_idx, col_to_update, old_value, time_code_str)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
        except Exception as e:
            self.handle_exception(e, "Error en update_in_out")

    def select_next_row_and_set_in(self) -> None:
        try:
            current_row_view_idx = self.table_widget.currentRow()
            if current_row_view_idx == -1 or current_row_view_idx >= self.table_widget.rowCount() - 1:
                return

            self._update_dataframe_from_table()

            id_item_curr = self.table_widget.item(current_row_view_idx, self.COL_ID)
            if not id_item_curr: return
            curr_row_id = int(id_item_curr.text())
            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            if df_idx_curr is None: return

            current_out_time_str = str(self.dataframe.at[df_idx_curr, 'OUT'])
            next_row_view_idx = current_row_view_idx + 1
            
            id_item_next = self.table_widget.item(next_row_view_idx, self.COL_ID)
            if not id_item_next: return
            next_row_id = int(id_item_next.text())
            df_idx_next = self.find_dataframe_index_by_id(next_row_id)
            if df_idx_next is None: return

            self.table_widget.selectRow(next_row_view_idx)
            
            old_in_next = str(self.dataframe.at[df_idx_next, 'IN'])
            if current_out_time_str != old_in_next:
                command = EditCommand(self, df_idx_next, self.COL_IN, old_in_next, current_out_time_str)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
            
            self.table_widget.scrollToItem(self.table_widget.item(next_row_view_idx, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
        except Exception as e:
            self.handle_exception(e, "Error al seleccionar la siguiente fila y marcar IN")

    def change_scene(self) -> None:
        selected_row_view_idx = self.table_widget.currentRow()
        if selected_row_view_idx == -1:
            QMessageBox.warning(self, "Cambio de Escena", "Selecciona una intervención.")
            return
        
        self._update_dataframe_from_table()

        id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
        if not id_item: return
        current_row_id = int(id_item.text())
        df_idx = self.find_dataframe_index_by_id(current_row_id)
        if df_idx is None: return

        command = ChangeSceneCommand(self, df_idx)
        self.undo_stack.push(command)
        self.set_unsaved_changes(True)

    def validate_in_out_time(self, row_view_idx: int) -> bool:
        """Valida IN/OUT para una fila de la VISTA de tabla."""
        try:
            in_item = self.table_widget.item(row_view_idx, self.COL_IN)
            out_item = self.table_widget.item(row_view_idx, self.COL_OUT)
            if not in_item or not out_item: return True

            in_time_str = in_item.text()
            out_time_str = out_item.text()

            in_ms = self.convert_time_code_to_milliseconds(in_time_str)
            out_ms = self.convert_time_code_to_milliseconds(out_time_str)
            is_valid = out_ms >= in_ms

            bg_color = VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR
            in_item.setBackground(bg_color)
            out_item.setBackground(bg_color)
            return is_valid
        except ValueError:
            if self.table_widget.item(row_view_idx, self.COL_IN): self.table_widget.item(row_view_idx, self.COL_IN).setBackground(INVALID_TIME_BG_COLOR)
            if self.table_widget.item(row_view_idx, self.COL_OUT): self.table_widget.item(row_view_idx, self.COL_OUT).setBackground(INVALID_TIME_BG_COLOR)
            return False
        except Exception:
            return True # Asumir válido en error inesperado

    def handle_ctrl_click(self, row_view_idx: int) -> None:
        try:
            self._update_dataframe_from_table()
            id_item = self.table_widget.item(row_view_idx, self.COL_ID)
            if not id_item: return
            current_row_id = int(id_item.text())
            df_idx = self.find_dataframe_index_by_id(current_row_id)
            if df_idx is None or df_idx >= len(self.dataframe): return

            in_time_code = str(self.dataframe.at[df_idx, 'IN'])
            ms = self.convert_time_code_to_milliseconds(in_time_code)
            self.in_out_signal.emit("IN", ms)
        except Exception as e:
            self.handle_exception(e, "Error en Ctrl+Click (marcar IN)")

    def handle_alt_click(self, row_view_idx: int) -> None:
        try:
            self._update_dataframe_from_table()
            id_item = self.table_widget.item(row_view_idx, self.COL_ID)
            if not id_item: return
            current_row_id = int(id_item.text())
            df_idx = self.find_dataframe_index_by_id(current_row_id)
            if df_idx is None or df_idx >= len(self.dataframe): return

            out_time_code = str(self.dataframe.at[df_idx, 'OUT'])
            ms = self.convert_time_code_to_milliseconds(out_time_code)
            self.in_out_signal.emit("OUT", ms)
        except Exception as e:
            self.handle_exception(e, "Error en Alt+Click (marcar OUT)")

    def get_character_names(self) -> List[str]:
        if self.dataframe.empty or 'PERSONAJE' not in self.dataframe.columns:
            return []
        return sorted(list(set(str(name) for name in self.dataframe['PERSONAJE'].unique() if pd.notna(name))))

    def update_character_completer(self) -> None:
        delegate = CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget)
        self.table_widget.setItemDelegateForColumn(self.COL_CHARACTER, delegate)

    def update_character_name(self, old_name: str, new_name: str) -> None:
        """Actualiza un nombre de personaje en el DataFrame y en la tabla."""
        self._update_dataframe_from_table()
        self.dataframe.loc[self.dataframe['PERSONAJE'] == old_name, 'PERSONAJE'] = new_name
        for row_view_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row_view_idx, self.COL_CHARACTER)
            if item and item.text() == old_name:
                item.setText(new_name)
        self.set_unsaved_changes(True)
        self.update_character_completer()
        self.character_name_changed.emit()

    def find_and_replace(self, find_text: str, replace_text: str,
                         search_in_character: bool = True,
                         search_in_dialogue: bool = True) -> None:
        try:
            self._update_dataframe_from_table()
            self.undo_stack.beginMacro("Buscar y Reemplazar")
            changed_count = 0
            for df_idx in range(len(self.dataframe)):
                if search_in_character:
                    char_text = str(self.dataframe.at[df_idx, 'PERSONAJE'])
                    if find_text.lower() in char_text.lower():
                        new_char_text = char_text.replace(find_text, replace_text)
                        if char_text != new_char_text:
                            cmd = EditCommand(self, df_idx, self.COL_CHARACTER, char_text, new_char_text)
                            self.undo_stack.push(cmd)
                            changed_count +=1
                if search_in_dialogue:
                    dialog_text = str(self.dataframe.at[df_idx, 'DIÁLOGO'])
                    if find_text.lower() in dialog_text.lower():
                        new_dialog_text = dialog_text.replace(find_text, replace_text)
                        if dialog_text != new_dialog_text:
                            cmd = EditCommand(self, df_idx, self.COL_DIALOGUE, dialog_text, new_dialog_text)
                            self.undo_stack.push(cmd)
                            changed_count += 1
            self.undo_stack.endMacro()
            if changed_count > 0:
                self.set_unsaved_changes(True)
                QMessageBox.information(self, "Buscar y Reemplazar", f"{changed_count} reemplazos realizados.")
            else:
                QMessageBox.information(self, "Buscar y Reemplazar", "No se encontraron coincidencias.")
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error en buscar y reemplazar")

    def update_window_title(self) -> None:
        prefix = "*" if self.unsaved_changes else ""
        script_display_name = self.current_script_name if self.current_script_name else "Sin Título"
        if self.main_window:
            self.main_window.setWindowTitle(f"{prefix}Editor de Guion - {script_display_name}")

    def set_unsaved_changes(self, changed: bool):
        if self.unsaved_changes != changed:
            self.unsaved_changes = changed
            self.update_window_title()

    def renumerar_escenas(self) -> None:
        """Asigna '1' a todas las escenas si no se detectaron números de escena durante la carga."""
        try:
            if not self.has_scene_numbers and not self.dataframe.empty:
                self._update_dataframe_from_table()
                self.undo_stack.beginMacro("Renumerar Escenas a 1")
                for df_idx in range(len(self.dataframe)):
                    old_scene = str(self.dataframe.at[df_idx, 'SCENE'])
                    if old_scene != "1":
                        cmd = EditCommand(self, df_idx, self.COL_SCENE, old_scene, "1")
                        self.undo_stack.push(cmd)
                self.undo_stack.endMacro()
                if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Renumerar Escenas"):
                    self.set_unsaved_changes(True)
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al renumerar escenas")

    def get_next_id(self) -> int:
        """Obtiene el siguiente ID único para una nueva fila del DataFrame."""
        if not self.dataframe.empty and 'ID' in self.dataframe.columns and not self.dataframe['ID'].empty:
            numeric_ids = pd.to_numeric(self.dataframe['ID'], errors='coerce').dropna()
            if not numeric_ids.empty:
                return int(numeric_ids.max()) + 1
        return 0

    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]:
        """Encuentra el índice de fila en self.dataframe que corresponde a un ID dado."""
        if 'ID' not in self.dataframe.columns or self.dataframe.empty:
            return None
        df_ids_numeric = pd.to_numeric(self.dataframe['ID'], errors='coerce')
        matches = self.dataframe.index[df_ids_numeric == id_value].tolist()
        return matches[0] if matches else None

    def find_table_row_by_id(self, id_value: int) -> Optional[int]:
        """Encuentra la fila en la QTableWidget que corresponde a un ID dado."""
        for r_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(r_idx, self.COL_ID)
            if item:
                try:
                    if int(item.text()) == id_value:
                        return r_idx
                except ValueError:
                    continue
        return None

    def get_dataframe_column_name(self, table_col_index: int) -> Optional[str]:
        return self.TABLE_TO_DF_COL_MAP.get(table_col_index)

    def handle_exception(self, exception: Exception, message: str) -> None:
        QMessageBox.critical(self, "Error", f"{message}:\n{str(exception)}")

    def apply_font_size_to_dialogs(self, font_size: int) -> None:
        for row in range(self.table_widget.rowCount()):
            widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
            if isinstance(widget, QTextEdit):
                current_font = widget.font()
                current_font.setPointSize(font_size)
                widget.setFont(current_font)
                self.adjust_row_height(row)


class EditCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_row_index: int, column_index_in_table: int,
                 old_value: Any, new_value: Any) -> None:
        super().__init__()
        self.tw = table_window
        self.df_row_idx = df_row_index
        self.col_idx_table = column_index_in_table
        self.old_value = old_value
        self.new_value = new_value
        
        col_name_in_df = self.tw.get_dataframe_column_name(self.col_idx_table)
        row_id_for_msg = df_row_index
        if 'ID' in self.tw.dataframe.columns and df_row_index < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_row_index, 'ID']
        self.setText(f"Editar {col_name_in_df} en fila ID {row_id_for_msg}")

    def _apply_value_to_dataframe_and_table(self, value_to_apply: Any):
        df_col_name = self.tw.get_dataframe_column_name(self.col_idx_table)
        if not df_col_name: return

        if df_col_name == 'SCENE':
            try:
                if str(value_to_apply).strip(): int(str(value_to_apply))
                self.tw.dataframe.at[self.df_row_idx, df_col_name] = str(value_to_apply)
            except ValueError:
                QMessageBox.warning(self.tw, "Error", f"Valor inválido '{value_to_apply}' para Escena.")
                return
        elif df_col_name == 'ID':
             self.tw.dataframe.at[self.df_row_idx, df_col_name] = int(value_to_apply)
        else:
            self.tw.dataframe.at[self.df_row_idx, df_col_name] = value_to_apply

        row_id = self.tw.dataframe.at[self.df_row_idx, 'ID']
        table_row_idx = self.tw.find_table_row_by_id(int(row_id))

        if table_row_idx is not None:
            if self.col_idx_table == self.tw.COL_DIALOGUE:
                widget = self.tw.table_widget.cellWidget(table_row_idx, self.col_idx_table)
                if isinstance(widget, QTextEdit):
                    widget.blockSignals(True)
                    widget.setPlainText(str(value_to_apply))
                    widget.blockSignals(False)
                    self.tw.adjust_row_height(table_row_idx)
            else:
                item = self.tw.table_widget.item(table_row_idx, self.col_idx_table)
                if item:
                    item.setText(str(value_to_apply))
            
            if self.col_idx_table in [self.tw.COL_IN, self.tw.COL_OUT]:
                self.tw.validate_in_out_time(table_row_idx)
        # else: No loguear error aquí, ya que es un flujo de limpieza

    def undo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.old_value)
        self.tw.set_unsaved_changes(True)

    def redo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.new_value)
        self.tw.set_unsaved_changes(True)


class AddRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, view_row_to_insert_at: int):
        super().__init__()
        self.tw = table_window
        self.view_row_to_insert_at = view_row_to_insert_at
        self.new_row_id = self.tw.get_next_id()
        self.new_row_data_for_df = {
            'ID': self.new_row_id,
            'SCENE': "1", 'IN': '00:00:00:00', 'OUT': '00:00:00:00',
            'PERSONAJE': 'Nuevo Personaje', 'DIÁLOGO': 'Nuevo diálogo...'
        }
        self.df_index_where_inserted: Optional[int] = None
        self.setText(f"Agregar fila (ID {self.new_row_id})")

    def redo(self) -> None:
        df = self.tw.dataframe
        if self.view_row_to_insert_at >= self.tw.table_widget.rowCount():
            self.df_index_where_inserted = len(df)
            if not df.empty:
                last_df_idx = len(df) - 1
                self.new_row_data_for_df['SCENE'] = str(df.at[last_df_idx, 'SCENE'])
                self.new_row_data_for_df['PERSONAJE'] = str(df.at[last_df_idx, 'PERSONAJE'])
        else:
            id_item_at_view_target = self.tw.table_widget.item(self.view_row_to_insert_at, self.tw.COL_ID)
            if id_item_at_view_target:
                target_id = int(id_item_at_view_target.text())
                self.df_index_where_inserted = self.tw.find_dataframe_index_by_id(target_id)
                if self.df_index_where_inserted is None:
                    self.df_index_where_inserted = len(df)
                if self.df_index_where_inserted > 0:
                    prev_df_idx = self.df_index_where_inserted -1
                    self.new_row_data_for_df['SCENE'] = str(df.at[prev_df_idx, 'SCENE'])
                    self.new_row_data_for_df['PERSONAJE'] = str(df.at[prev_df_idx, 'PERSONAJE'])
            else:
                self.df_index_where_inserted = len(df)

        new_df_row_series = pd.Series(self.new_row_data_for_df)
        df_part1 = df.iloc[:self.df_index_where_inserted]
        df_part2 = df.iloc[self.df_index_where_inserted:]
        self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([new_df_row_series]), df_part2], ignore_index=True)

        self.tw.table_widget.insertRow(self.view_row_to_insert_at)
        for col_idx_table, df_col_name in self.tw.TABLE_TO_DF_COL_MAP.items():
            value = self.new_row_data_for_df.get(df_col_name, '')
            if col_idx_table == self.tw.COL_DIALOGUE:
                widget = self.tw.create_text_edit(str(value), self.view_row_to_insert_at, col_idx_table)
                self.tw.table_widget.setCellWidget(self.view_row_to_insert_at, col_idx_table, widget)
            else:
                item = self.tw.create_table_item(str(value), col_idx_table)
                self.tw.table_widget.setItem(self.view_row_to_insert_at, col_idx_table, item)
        
        self.tw.adjust_row_height(self.view_row_to_insert_at)
        self.tw.table_widget.selectRow(self.view_row_to_insert_at)
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        if self.df_index_where_inserted is not None:
            self.tw.dataframe.drop(index=self.df_index_where_inserted, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True)

            table_row_to_remove = self.tw.find_table_row_by_id(self.new_row_id)
            if table_row_to_remove is not None:
                self.tw.table_widget.removeRow(table_row_to_remove)
            else:
                 if self.view_row_to_insert_at < self.tw.table_widget.rowCount():
                    self.tw.table_widget.removeRow(self.view_row_to_insert_at)
            
            self.df_index_where_inserted = None
            self.tw.set_unsaved_changes(True)


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_rows_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices_removed = sorted(df_rows_indices_to_remove)
        self.removed_data_map: Dict[int, pd.Series] = {}
        self.setText(f"Eliminar {len(self.df_indices_removed)} fila(s)")

    def redo(self) -> None:
        self.removed_data_map.clear()
        df_indices_desc = sorted(self.df_indices_removed, reverse=True)

        for df_idx in df_indices_desc:
            if df_idx < len(self.tw.dataframe):
                self.removed_data_map[df_idx] = self.tw.dataframe.iloc[df_idx].copy()
                row_id_to_remove = int(self.tw.dataframe.at[df_idx, 'ID'])
                table_row_idx = self.tw.find_table_row_by_id(row_id_to_remove)
                if table_row_idx is not None:
                    self.tw.table_widget.removeRow(table_row_idx)
                self.tw.dataframe.drop(index=df_idx, inplace=True)
        
        self.tw.dataframe.reset_index(drop=True, inplace=True)
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        for original_df_idx in self.df_indices_removed:
            row_data_series = self.removed_data_map.get(original_df_idx)
            if row_data_series is not None:
                df_part1 = self.tw.dataframe.iloc[:original_df_idx]
                df_part2 = self.tw.dataframe.iloc[original_df_idx:]
                self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([row_data_series]), df_part2], ignore_index=True)
        self.tw.populate_table()
        self.tw.set_unsaved_changes(True)


class MoveRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_source_idx: int, df_target_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_source_idx = df_source_idx
        self.df_target_idx = df_target_idx
        
        row_id_for_msg = df_source_idx
        if 'ID' in self.tw.dataframe.columns and df_source_idx < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_source_idx, 'ID']
        self.setText(f"Mover fila ID {row_id_for_msg} de {df_source_idx} a {df_target_idx}")

    def _perform_move(self, from_df_idx: int, to_df_idx: int):
        row_to_move = self.tw.dataframe.iloc[from_df_idx].copy()
        temp_df = self.tw.dataframe.drop(index=from_df_idx).reset_index(drop=True)
        
        part1 = temp_df.iloc[:to_df_idx]
        part2 = temp_df.iloc[to_df_idx:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([row_to_move]), part2], ignore_index=True)

        self.tw.populate_table()
        
        moved_row_id = int(row_to_move['ID'])
        new_table_idx = self.tw.find_table_row_by_id(moved_row_id)
        if new_table_idx is not None:
            self.tw.table_widget.selectRow(new_table_idx)
        
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        self._perform_move(self.df_target_idx, self.df_source_idx)

    def redo(self) -> None:
        self._perform_move(self.df_source_idx, self.df_target_idx)


class SplitInterventionCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_row_idx_to_split: int, before_text: str, after_text: str):
        super().__init__()
        self.tw = table_window
        self.df_idx_split = df_row_idx_to_split
        self.before_text = before_text
        self.after_text = after_text
        self.original_dialog = ""
        self.new_row_id_for_second_part = self.tw.get_next_id()
        self.second_part_data_for_df: Optional[Dict] = None

        row_id_for_msg = df_row_idx_to_split
        if 'ID' in self.tw.dataframe.columns and df_row_idx_to_split < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_row_idx_to_split, 'ID']
        self.setText(f"Separar intervención en fila ID {row_id_for_msg}")

    def redo(self) -> None:
        if not self.original_dialog:
             self.original_dialog = str(self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'])
        self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.before_text

        if self.second_part_data_for_df is None:
            original_row_data = self.tw.dataframe.iloc[self.df_idx_split].copy()
            self.second_part_data_for_df = original_row_data.to_dict()
            self.second_part_data_for_df['ID'] = self.new_row_id_for_second_part
            self.second_part_data_for_df['DIÁLOGO'] = self.after_text

        df_idx_insert_new_part_at = self.df_idx_split + 1
        new_series = pd.Series(self.second_part_data_for_df)
        part1 = self.tw.dataframe.iloc[:df_idx_insert_new_part_at]
        part2 = self.tw.dataframe.iloc[df_idx_insert_new_part_at:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([new_series]), part2], ignore_index=True)
        
        self.tw.populate_table()
        
        original_part_id = int(self.tw.dataframe.at[self.df_idx_split, 'ID'])
        table_idx_original = self.tw.find_table_row_by_id(original_part_id)
        if table_idx_original is not None:
            self.tw.table_widget.selectRow(table_idx_original)
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.original_dialog
        df_idx_of_second_part = self.tw.find_dataframe_index_by_id(self.new_row_id_for_second_part)
        if df_idx_of_second_part is not None:
            self.tw.dataframe.drop(index=df_idx_of_second_part, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True)
        
        self.tw.populate_table()
        original_part_id = int(self.tw.dataframe.at[self.df_idx_split, 'ID'])
        table_idx_original = self.tw.find_table_row_by_id(original_part_id)
        if table_idx_original is not None:
            self.tw.table_widget.selectRow(table_idx_original)
        self.tw.set_unsaved_changes(True)


class MergeInterventionsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_idx_first_row: int, merged_dialog: str, df_idx_second_row: int):
        super().__init__()
        self.tw = table_window
        self.df_idx_first = df_idx_first_row
        self.df_idx_second = df_idx_second_row
        self.merged_dialog = merged_dialog
        self.original_dialog_first: Optional[str] = None
        self.data_of_second_row: Optional[pd.Series] = None

        row_id_first = df_idx_first_row
        if 'ID' in self.tw.dataframe.columns and df_idx_first_row < len(self.tw.dataframe):
            row_id_first = self.tw.dataframe.at[df_idx_first_row, 'ID']
        self.setText(f"Juntar intervenciones (ID {row_id_first} con siguiente)")

    def redo(self) -> None:
        if self.original_dialog_first is None:
            self.original_dialog_first = str(self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'])
        if self.data_of_second_row is None:
            self.data_of_second_row = self.tw.dataframe.iloc[self.df_idx_second].copy()

        self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.merged_dialog
        self.tw.dataframe.drop(index=self.df_idx_second, inplace=True)
        self.tw.dataframe.reset_index(drop=True, inplace=True)
        
        self.tw.populate_table()
        merged_row_id = int(self.tw.dataframe.at[self.df_idx_first, 'ID'])
        table_idx_merged = self.tw.find_table_row_by_id(merged_row_id)
        if table_idx_merged is not None:
            self.tw.table_widget.selectRow(table_idx_merged)
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        if self.original_dialog_first is None or self.data_of_second_row is None:
            return # Error state, no data to undo

        self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.original_dialog_first
        insert_at_idx_for_second_row = self.df_idx_first + 1
        part1 = self.tw.dataframe.iloc[:insert_at_idx_for_second_row]
        part2 = self.tw.dataframe.iloc[insert_at_idx_for_second_row:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([self.data_of_second_row]), part2], ignore_index=True)
        
        self.tw.populate_table()
        first_row_id = int(self.tw.dataframe.at[self.df_idx_first, 'ID'])
        table_idx_first = self.tw.find_table_row_by_id(first_row_id)
        if table_idx_first is not None:
            self.tw.table_widget.selectRow(table_idx_first)
        self.tw.set_unsaved_changes(True)


class ChangeSceneCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_start_row_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_start_idx = df_start_row_idx
        self.old_scene_numbers_map: Dict[int, str] = {}
        self.new_scene_numbers_map: Dict[int, str] = {}

        row_id_for_msg = df_start_row_idx
        if 'ID' in self.tw.dataframe.columns and df_start_row_idx < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_start_row_idx, 'ID']
        self.setText(f"Cambiar escena desde fila ID {row_id_for_msg}")

    def _apply_scene_changes(self, scene_map: Dict[int, str], highlight_first: bool = False):
        first_row_id_changed = -1
        for df_idx, scene_str_val in scene_map.items():
            if df_idx < len(self.tw.dataframe):
                self.tw.dataframe.at[df_idx, 'SCENE'] = scene_str_val
                if first_row_id_changed == -1:
                    first_row_id_changed = int(self.tw.dataframe.at[df_idx, 'ID'])
        self.tw.populate_table()
        if highlight_first and first_row_id_changed != -1:
            table_idx_first = self.tw.find_table_row_by_id(first_row_id_changed)
            if table_idx_first is not None:
                self.tw.table_widget.selectRow(table_idx_first)
                for col in range(self.tw.table_widget.columnCount()):
                    cell_item = self.tw.table_widget.item(table_idx_first, col)
                    if cell_item:
                        cell_item.setBackground(QColor("#FFD700")) # Amarillo
        self.tw.set_unsaved_changes(True)

    def redo(self) -> None:
        self.old_scene_numbers_map.clear()
        self.new_scene_numbers_map.clear()
        current_scene_val = 0
        try:
            scene_text_at_start = str(self.tw.dataframe.at[self.df_start_idx, 'SCENE'])
            if scene_text_at_start.strip():
                current_scene_val = int(scene_text_at_start)
        except (ValueError, IndexError):
            current_scene_val = 0

        for df_idx in range(self.df_start_idx, len(self.tw.dataframe)):
            self.old_scene_numbers_map[df_idx] = str(self.tw.dataframe.at[df_idx, 'SCENE'])
            try:
                old_scene_num_val = int(self.old_scene_numbers_map[df_idx])
                self.new_scene_numbers_map[df_idx] = str(old_scene_num_val + 1)
            except ValueError:
                self.new_scene_numbers_map[df_idx] = "1" # Fallback
        self._apply_scene_changes(self.new_scene_numbers_map, highlight_first=True)

    def undo(self) -> None:
        self._apply_scene_changes(self.old_scene_numbers_map, highlight_first=False)