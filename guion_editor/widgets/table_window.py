# guion_editor/widgets/table_window.py

import json
import os
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize
from PyQt6.QtGui import QFont, QKeySequence, QColor, QIntValidator, QBrush, QAction, QFontMetrics, QIcon
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QTableWidgetItem,
    QHeaderView
)
from PyQt6.QtGui import QShortcut, QUndoStack, QUndoCommand
# QSize ya está importado desde PyQt6.QtCore, no es necesario desde PyQt6.QtGui de nuevo

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

    # KeyPressFilter DEBE estar indentada aquí, DENTRO de TableWindow
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

        self.video_player_widget = video_player_widget
        if self.video_player_widget:
            self.video_player_widget.in_out_signal.connect(self.update_in_out)
            self.video_player_widget.out_released.connect(self.select_next_row_and_set_in)

        self.guion_manager = guion_manager if guion_manager else GuionManager()

        # CORRECTA INSTANCIACIÓN de la clase anidada
        self.key_filter = TableWindow.KeyPressFilter(self)

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
        self.setup_table_widget(main_layout)
        self.load_stylesheet()

        self.header_details_widget.setVisible(True)
        self.toggle_header_visibility()
        self.toggle_header_visibility()

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

        self.reference_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.product_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.chapter_edit.textChanged.connect(lambda: self.set_unsaved_changes(True))
        self.type_combo.currentIndexChanged.connect(lambda: self.set_unsaved_changes(True))

    def toggle_header_visibility(self) -> None:
        if self.header_details_widget.isVisible():
            self.header_details_widget.setVisible(False)
            self.toggle_header_button.setText(" Mostrar Detalles del Guion")
            if self.get_icon:
                self.toggle_header_button.setIcon(self.icon_expand_more)
        else:
            self.header_details_widget.setVisible(True)
            self.toggle_header_button.setText(" Ocultar Detalles del Guion")
            if self.get_icon:
                self.toggle_header_button.setIcon(self.icon_expand_less)

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
                 button.setToolTip(text.strip() if text.strip() else method.__name__.replace("_", " ").title()) # Mejor tooltip para solo icono
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
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')

            if not os.path.exists(css_path):
                alt_css_path = os.path.join(current_file_dir, 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    print(f"Advertencia: Stylesheet de tabla no encontrado en {css_path} ni {alt_css_path}")
                    return

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

        path, _ = QFileDialog.getSaveFileName(self, "Exportar Guion como Excel", default_filename, "Archivos Excel (*.xlsx);;Todos los archivos (*.*)")
        if path:
            try:
                self.guion_manager.save_to_excel(path, self.dataframe, header_data)
                QMessageBox.information(self, "Éxito", "Datos guardados correctamente en Excel.")
                self.current_script_name = os.path.basename(path)
                self.current_script_path = path
                self.set_unsaved_changes(False)
                self.update_window_title()
                if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
                    self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al guardar en Excel")
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
                if self.main_window and hasattr(self.main_window, 'add_to_recent_files'):
                    self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al guardar en JSON")
                return False
        return False

    def clear_script_state(self):
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
        try:
            row, column = item.row(), item.column()
            df_col_name = self.get_dataframe_column_name(column)
            if not df_col_name or row >= len(self.dataframe): # Check row < len(df)
                return

            new_text = item.text()
            # Ensure dataframe is not empty and row is within bounds before accessing .at
            if self.dataframe.empty or row >= len(self.dataframe):
                old_text = "" # Or handle as an error/unexpected state
            else:
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
            if self.dataframe.empty or row >= len(self.dataframe):
                old_text = ""
            else:
                old_text = str(self.dataframe.at[row, df_col_name])


            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
                self.adjust_row_height(row)
        except Exception as e:
            self.handle_exception(e, f"Error al finalizar la edición del texto del diálogo: {e}")

    def _update_dataframe_from_table(self) -> None:
        try:
            if self.dataframe.empty and self.table_widget.rowCount() == 0:
                 # Asegurarse de que el dataframe sea un DataFrame vacío con las columnas correctas si es None
                if self.dataframe is None or not isinstance(self.dataframe, pd.DataFrame):
                    self.dataframe = pd.DataFrame(columns=list(self.TABLE_TO_DF_COL_MAP.values()))
                return

            temp_data = []
            for row_idx in range(self.table_widget.rowCount()):
                row_dict = {}
                id_item = self.table_widget.item(row_idx, self.COL_ID)
                if id_item and id_item.text():
                    try:
                        row_dict['ID'] = int(id_item.text())
                    except ValueError:
                        row_dict['ID'] = None
                else:
                    row_dict['ID'] = None

                for col_idx_table, df_col_name in self.TABLE_TO_DF_COL_MAP.items():
                    if col_idx_table == self.COL_ID:
                        continue

                    if col_idx_table == self.COL_DIALOGUE:
                        widget = self.table_widget.cellWidget(row_idx, self.COL_DIALOGUE)
                        row_dict[df_col_name] = widget.toPlainText() if widget else ""
                    else:
                        item = self.table_widget.item(row_idx, col_idx_table)
                        row_dict[df_col_name] = item.text() if item else ""
                temp_data.append(row_dict)

            if temp_data:
                new_df = pd.DataFrame(temp_data)

                # ---- INICIO DE LA CORRECCIÓN ----
                # Asegurar que todas las columnas esperadas existan en new_df, añadiéndolas con valores por defecto si no
                for df_col_name_expected in self.TABLE_TO_DF_COL_MAP.values():
                    if df_col_name_expected not in new_df.columns:
                        if df_col_name_expected == 'ID':
                            # Si 'ID' no está, se creará como None y se rellenará más abajo
                            new_df[df_col_name_expected] = pd.Series([None] * len(new_df), dtype=object)
                        elif df_col_name_expected in ['IN', 'OUT']:
                            new_df[df_col_name_expected] = "00:00:00:00"
                        else:
                            new_df[df_col_name_expected] = ""

                # Procesamiento robusto de la columna 'ID'
                if 'ID' in new_df.columns:
                    numeric_ids = pd.to_numeric(new_df['ID'], errors='coerce')

                    nan_id_mask = numeric_ids.isna()
                    num_nan_ids = nan_id_mask.sum()

                    if num_nan_ids > 0:
                        max_existing_valid_id = -1
                        valid_numeric_ids_in_new_df = numeric_ids[~nan_id_mask]
                        if not valid_numeric_ids_in_new_df.empty:
                            max_existing_valid_id = valid_numeric_ids_in_new_df.max()

                        start_new_id = int(max_existing_valid_id) + 1

                        new_ids_for_nan_values = pd.Series(
                            range(start_new_id, start_new_id + num_nan_ids),
                            index=numeric_ids[nan_id_mask].index, # Alinea con las filas NaN en numeric_ids
                            dtype='Int64'
                        )
                        numeric_ids.loc[nan_id_mask] = new_ids_for_nan_values

                    new_df['ID'] = numeric_ids.astype(int)
                else:
                    new_df['ID'] = range(len(new_df))
                # ---- FIN DE LA CORRECCIÓN ----

                if 'SCENE' in new_df.columns:
                    new_df['SCENE'] = new_df['SCENE'].astype(str)

                # Reordenar columnas al orden esperado
                ordered_columns = [col for col in self.TABLE_TO_DF_COL_MAP.values() if col in new_df.columns]
                extra_cols = [col for col in new_df.columns if col not in ordered_columns]
                self.dataframe = new_df[ordered_columns + extra_cols]

            else: # Si temp_data está vacío (la tabla no tenía filas)
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
                        current_item.setText(self.clipboard_text) # This will trigger on_item_changed
        except Exception as e:
            self.handle_exception(e, "Error al pegar el tiempo")

    def adjust_dialogs(self) -> None:
        try:
            self._update_dataframe_from_table()
            if self.dataframe.empty : return # No action if dataframe is empty
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
            self.undo_stack.endMacro() # Ensure macro ends even on error
            self.handle_exception(e, "Error al ajustar diálogos")

    def copy_in_out_to_next(self) -> None:
        try:
            selected_row_idx = self.table_widget.currentRow()
            if selected_row_idx == -1 :
                QMessageBox.warning(self, "Copiar IN/OUT", "Seleccione una fila primero.")
                return

            self._update_dataframe_from_table() # Ensure DF is up-to-date

            if selected_row_idx >= len(self.dataframe) - 1:
                QMessageBox.warning(self, "Copiar IN/OUT", "No se puede copiar a la siguiente fila si la fila seleccionada es la última.")
                return


            in_time = str(self.dataframe.at[selected_row_idx, 'IN'])
            out_time = str(self.dataframe.at[selected_row_idx, 'OUT'])
            next_row_df_idx = selected_row_idx + 1 # Assuming view index matches df index after _update_dataframe_from_table

            self.undo_stack.beginMacro("Copiar IN/OUT a Siguiente")

            old_in_next = str(self.dataframe.at[next_row_df_idx, 'IN'])
            if in_time != old_in_next:
                cmd_in = EditCommand(self, next_row_df_idx, self.COL_IN, old_in_next, in_time)
                self.undo_stack.push(cmd_in)

            old_out_next = str(self.dataframe.at[next_row_df_idx, 'OUT'])
            if out_time != old_out_next:
                cmd_out = EditCommand(self, next_row_df_idx, self.COL_OUT, old_out_next, out_time)
                self.undo_stack.push(cmd_out)

            self.undo_stack.endMacro()

            # Check if any commands were actually pushed
            if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Copiar IN/OUT"):
                 self.set_unsaved_changes(True)
                 QMessageBox.information(self, "Copiar IN/OUT", "Tiempos IN y OUT copiados a la siguiente intervención.")
        except IndexError:
            self.undo_stack.endMacro()
            QMessageBox.warning(self, "Error", "Error de índice al copiar IN/OUT. Asegúrese de que la tabla y los datos estén sincronizados.")
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al copiar IN/OUT")

    def add_new_row(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            self._update_dataframe_from_table() # Call before determining insert_at_row_idx based on df

            if selected_row_view_idx != -1 and not self.dataframe.empty and selected_row_view_idx < len(self.dataframe):
                df_insert_idx = selected_row_view_idx + 1
            else:
                df_insert_idx = len(self.dataframe)

            view_insert_idx = selected_row_view_idx + 1 if selected_row_view_idx != -1 else self.table_widget.rowCount()

            command = AddRowCommand(self, view_insert_idx, df_insert_idx)
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

            confirm = QMessageBox.question(self, "Confirmar Eliminación", "¿Estás seguro de que deseas eliminar las filas seleccionadas?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                self._update_dataframe_from_table() # CRUCIAL: Sync DF before finding IDs

                df_indices_to_remove = []
                for row_view_idx in rows_to_remove_view_indices:
                    id_item = self.table_widget.item(row_view_idx, self.COL_ID)
                    if id_item and id_item.text():
                        try:
                            row_id = int(id_item.text())
                            df_idx = self.find_dataframe_index_by_id(row_id)
                            if df_idx is not None:
                                df_indices_to_remove.append(df_idx)
                            else:
                                print(f"Advertencia: No se encontró el ID {row_id} en el DataFrame para la fila de vista {row_view_idx}.")
                        except ValueError:
                             print(f"Advertencia: ID no numérico '{id_item.text()}' en la fila de vista {row_view_idx}.")
                    else:
                        print(f"Advertencia: No se pudo obtener el ID para la fila de vista {row_view_idx}.")

                if df_indices_to_remove:
                    command = RemoveRowsCommand(self, sorted(list(set(df_indices_to_remove)), reverse=False)) # Use set to avoid duplicates
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
                else:
                    QMessageBox.information(self, "Información", "No se seleccionaron filas válidas del modelo de datos para eliminar (posiblemente filas nuevas sin ID o error de sincronización).")
        except Exception as e:
            self.handle_exception(e, "Error al eliminar las filas")


    def move_row_up(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx > 0:
                self._update_dataframe_from_table() # Sync before move

                id_item_source = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not (id_item_source and id_item_source.text()): return

                current_row_id = int(id_item_source.text())
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
            if selected_row_view_idx != -1 and selected_row_view_idx < self.table_widget.rowCount() - 1 :
                self._update_dataframe_from_table() # Sync before move

                id_item_source = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not (id_item_source and id_item_source.text()): return

                current_row_id = int(id_item_source.text())
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

            self._update_dataframe_from_table() # Sync DF

            dialog_widget = self.table_widget.cellWidget(selected_row_view_idx, self.COL_DIALOGUE)
            if not isinstance(dialog_widget, QTextEdit): return

            id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            if not (id_item and id_item.text()): return

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

            if not after_text: # Only split if there's text for the new intervention
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

            self._update_dataframe_from_table() # Sync DF

            id_item_curr = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            id_item_next = self.table_widget.item(selected_row_view_idx + 1, self.COL_ID)
            if not (id_item_curr and id_item_curr.text()) or not (id_item_next and id_item_next.text()): return

            curr_row_id = int(id_item_curr.text())
            next_row_id = int(id_item_next.text())

            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            df_idx_next = self.find_dataframe_index_by_id(next_row_id)

            if df_idx_curr is None or df_idx_next is None: return
            if df_idx_next != df_idx_curr + 1: # Check for consecutiveness in DF
                QMessageBox.critical(self, "Error Interno", "Las filas seleccionadas para juntar no son consecutivas en el modelo de datos.")
                return

            char_curr = str(self.dataframe.at[df_idx_curr, 'PERSONAJE'])
            char_next = str(self.dataframe.at[df_idx_next, 'PERSONAJE'])

            if char_curr != char_next:
                QMessageBox.warning(self, "Juntar", "Las intervenciones deben ser del mismo personaje.")
                return

            dialog_curr = str(self.dataframe.at[df_idx_curr, 'DIÁLOGO']).strip()
            dialog_next = str(self.dataframe.at[df_idx_next, 'DIÁLOGO']).strip()

            merged_dialog = f"{dialog_curr} {dialog_next}".strip() if dialog_curr and dialog_next else (dialog_curr or dialog_next)

            original_out_first = str(self.dataframe.at[df_idx_curr, 'OUT']) # Store OUT of the first row before modification

            command = MergeInterventionsCommand(self, df_idx_curr, merged_dialog, df_idx_next, original_out_first)
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
            return (h * 3600 + m * 60 + s) * 1000 + int(round((f / 25.0) * 1000.0)) # Asume 25 FPS, use float for precision
        except ValueError:
            return 0 # Return 0 for invalid format to avoid crashes
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
            f = int(round(rem_s_ms / (1000.0 / 25.0))) # Use float for precision
            if f >= 25: f = 24 # Cap frames at max for 25fps
            return f"{int(h):02}:{int(m):02}:{int(s):02}:{int(f):02}"
        except Exception:
            return "00:00:00:00" # Fallback

    def update_in_out(self, action: str, position_ms: int) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx == -1 :
                return

            self._update_dataframe_from_table() # Sync DF

            id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            if not (id_item and id_item.text()): return # Ensure ID exists

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

            self._update_dataframe_from_table() # Sync DF

            id_item_curr = self.table_widget.item(current_row_view_idx, self.COL_ID)
            if not (id_item_curr and id_item_curr.text()): return
            curr_row_id = int(id_item_curr.text())
            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            if df_idx_curr is None: return

            current_out_time_str = str(self.dataframe.at[df_idx_curr, 'OUT'])
            next_row_view_idx = current_row_view_idx + 1

            id_item_next = self.table_widget.item(next_row_view_idx, self.COL_ID)
            if not (id_item_next and id_item_next.text()): return
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

        self._update_dataframe_from_table() # Sync DF

        id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
        if not (id_item and id_item.text()): return
        current_row_id = int(id_item.text())
        df_idx = self.find_dataframe_index_by_id(current_row_id)
        if df_idx is None: return

        command = ChangeSceneCommand(self, df_idx)
        self.undo_stack.push(command)
        self.set_unsaved_changes(True)

    def validate_in_out_time(self, row_view_idx: int) -> bool:
        try:
            in_item = self.table_widget.item(row_view_idx, self.COL_IN)
            out_item = self.table_widget.item(row_view_idx, self.COL_OUT)
            if not in_item or not out_item: return True # Or False if strict

            in_time_str = in_item.text()
            out_time_str = out_item.text()

            in_ms = self.convert_time_code_to_milliseconds(in_time_str)
            out_ms = self.convert_time_code_to_milliseconds(out_time_str)
            is_valid = out_ms >= in_ms

            bg_color = VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR
            in_item.setBackground(QBrush(bg_color)) # Use QBrush for setBackground
            out_item.setBackground(QBrush(bg_color))
            return is_valid
        except ValueError: # From convert_time_code_to_milliseconds if format is bad
            if self.table_widget.item(row_view_idx, self.COL_IN): self.table_widget.item(row_view_idx, self.COL_IN).setBackground(QBrush(INVALID_TIME_BG_COLOR))
            if self.table_widget.item(row_view_idx, self.COL_OUT): self.table_widget.item(row_view_idx, self.COL_OUT).setBackground(QBrush(INVALID_TIME_BG_COLOR))
            return False
        except Exception: # Other unexpected errors
            return True

    def handle_ctrl_click(self, row_view_idx: int) -> None:
        try:
            self._update_dataframe_from_table() # Sync DF
            id_item = self.table_widget.item(row_view_idx, self.COL_ID)
            if not (id_item and id_item.text()): return
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
            self._update_dataframe_from_table() # Sync DF
            id_item = self.table_widget.item(row_view_idx, self.COL_ID)
            if not (id_item and id_item.text()): return
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
        # Ensure names are strings and handle potential NaN values gracefully
        return sorted(list(set(str(name) for name in self.dataframe['PERSONAJE'].unique() if pd.notna(name) and str(name).strip())))


    def update_character_completer(self) -> None:
        # Recreate delegate to update completer list
        delegate = CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget)
        self.table_widget.setItemDelegateForColumn(self.COL_CHARACTER, delegate)

    def update_character_name(self, old_name: str, new_name: str) -> None:
        self._update_dataframe_from_table() # Sync DF
        # Ensure new_name is not empty
        if not new_name.strip():
            QMessageBox.warning(self, "Nombre Inválido", "El nombre del personaje no puede estar vacío.")
            return

        self.dataframe.loc[self.dataframe['PERSONAJE'] == old_name, 'PERSONAJE'] = new_name
        # Update table view directly for immediate visual feedback
        for row_view_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row_view_idx, self.COL_CHARACTER)
            if item and item.text() == old_name:
                item.setText(new_name)
        self.set_unsaved_changes(True)
        self.update_character_completer() # Update completer list
        self.character_name_changed.emit() # Notify other parts if necessary

    def find_and_replace(self, find_text: str, replace_text: str,
                         search_in_character: bool = True,
                         search_in_dialogue: bool = True) -> None:
        try:
            self._update_dataframe_from_table() # Sync DF
            if self.dataframe.empty: return

            self.undo_stack.beginMacro("Buscar y Reemplazar")
            changed_count = 0
            for df_idx in range(len(self.dataframe)):
                if search_in_character:
                    char_text = str(self.dataframe.at[df_idx, 'PERSONAJE'])
                    if find_text.lower() in char_text.lower():
                        new_char_text = char_text.replace(find_text, replace_text) # Case-sensitive
                        if char_text != new_char_text:
                            cmd = EditCommand(self, df_idx, self.COL_CHARACTER, char_text, new_char_text)
                            self.undo_stack.push(cmd)
                            changed_count +=1
                if search_in_dialogue:
                    dialog_text = str(self.dataframe.at[df_idx, 'DIÁLOGO'])
                    if find_text.lower() in dialog_text.lower():
                        new_dialog_text = dialog_text.replace(find_text, replace_text) # Case-sensitive
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
            self.undo_stack.endMacro() # Ensure macro ends
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
        try:
            if not self.has_scene_numbers and not self.dataframe.empty:
                self._update_dataframe_from_table() # Sync
                self.undo_stack.beginMacro("Renumerar Escenas a 1")
                changed_any = False
                for df_idx in range(len(self.dataframe)):
                    old_scene = str(self.dataframe.at[df_idx, 'SCENE'])
                    if old_scene != "1":
                        cmd = EditCommand(self, df_idx, self.COL_SCENE, old_scene, "1")
                        self.undo_stack.push(cmd)
                        changed_any = True
                self.undo_stack.endMacro()
                if changed_any: # Only set unsaved if changes were made
                    self.set_unsaved_changes(True)
                    self.has_scene_numbers = True # Now scenes are explicitly "1"
        except Exception as e:
            self.undo_stack.endMacro() # Ensure macro ends
            self.handle_exception(e, "Error al renumerar escenas")

    def get_next_id(self) -> int:
        if not self.dataframe.empty and 'ID' in self.dataframe.columns and not self.dataframe['ID'].dropna().empty: # Ensure ID column is not all NaN
            numeric_ids = pd.to_numeric(self.dataframe['ID'], errors='coerce').dropna()
            if not numeric_ids.empty:
                return int(numeric_ids.max()) + 1
        return 0

    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]:
        if 'ID' not in self.dataframe.columns or self.dataframe.empty:
            return None
        # Ensure 'ID' column is numeric for comparison, handle potential errors
        df_ids_numeric = pd.to_numeric(self.dataframe['ID'], errors='coerce')
        matches = self.dataframe.index[df_ids_numeric == id_value].tolist()
        return matches[0] if matches else None

    def find_table_row_by_id(self, id_value: int) -> Optional[int]:
        for r_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(r_idx, self.COL_ID)
            if item and item.text(): # Check item and text exist
                try:
                    if int(item.text()) == id_value:
                        return r_idx
                except ValueError: # If text is not a valid integer
                    continue
        return None

    def get_dataframe_column_name(self, table_col_index: int) -> Optional[str]:
        return self.TABLE_TO_DF_COL_MAP.get(table_col_index)

    def handle_exception(self, exception: Exception, message: str) -> None:
        # Consider logging the full traceback here for better debugging
        import traceback
        print(f"ERROR: {message}\n{str(exception)}")
        traceback.print_exc()
        QMessageBox.critical(self, "Error", f"{message}:\n{str(exception)}")

    def apply_font_size_to_dialogs(self, font_size: int) -> None:
        for row in range(self.table_widget.rowCount()):
            widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
            if isinstance(widget, QTextEdit):
                current_font = widget.font()
                current_font.setPointSize(font_size)
                widget.setFont(current_font)
                self.adjust_row_height(row) # Adjust height after font change


# --- QUndoCommand Subclasses ---

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
        row_id_for_msg = self.df_row_idx # Default to df index if ID is not available
        # Check if DataFrame and 'ID' column exist and df_row_idx is valid
        if not self.tw.dataframe.empty and \
           'ID' in self.tw.dataframe.columns and \
           self.df_row_idx < len(self.tw.dataframe) and \
           pd.notna(self.tw.dataframe.at[self.df_row_idx, 'ID']):
            try:
                row_id_for_msg = int(self.tw.dataframe.at[self.df_row_idx, 'ID'])
            except ValueError:
                pass # Keep df_row_idx if ID is not int
        self.setText(f"Editar {col_name_in_df} en fila ID {row_id_for_msg}")


    def _apply_value_to_dataframe_and_table(self, value_to_apply: Any):
        df_col_name = self.tw.get_dataframe_column_name(self.col_idx_table)
        if not df_col_name: return

        # Ensure df_row_idx is within current DataFrame bounds
        if self.df_row_idx >= len(self.tw.dataframe):
            print(f"Error en EditCommand: df_row_idx {self.df_row_idx} fuera de los límites del DataFrame (longitud {len(self.tw.dataframe)})")
            return

        # Update DataFrame
        if df_col_name == 'SCENE':
            try:
                str_val = str(value_to_apply).strip()
                if str_val: int(str_val)
                self.tw.dataframe.at[self.df_row_idx, df_col_name] = str_val
            except ValueError:
                return
        elif df_col_name == 'ID':
             try:
                 self.tw.dataframe.at[self.df_row_idx, df_col_name] = int(value_to_apply)
             except ValueError: return
        else:
            self.tw.dataframe.at[self.df_row_idx, df_col_name] = value_to_apply

        if 'ID' not in self.tw.dataframe.columns or pd.isna(self.tw.dataframe.at[self.df_row_idx, 'ID']):
            return

        try:
            row_id = int(self.tw.dataframe.at[self.df_row_idx, 'ID'])
        except ValueError:
            return

        table_row_idx = self.tw.find_table_row_by_id(row_id)

        if table_row_idx is not None:
            self.tw.table_widget.blockSignals(True)
            if self.col_idx_table == self.tw.COL_DIALOGUE:
                widget = self.tw.table_widget.cellWidget(table_row_idx, self.col_idx_table)
                if isinstance(widget, QTextEdit):
                    widget.setPlainText(str(value_to_apply))
                    self.tw.adjust_row_height(table_row_idx)
            else:
                item = self.tw.table_widget.item(table_row_idx, self.col_idx_table)
                if item:
                    item.setText(str(value_to_apply))
                else:
                    new_item = self.tw.create_table_item(str(value_to_apply), self.col_idx_table)
                    self.tw.table_widget.setItem(table_row_idx, self.col_idx_table, new_item)

            if self.col_idx_table in [self.tw.COL_IN, self.tw.COL_OUT]:
                self.tw.validate_in_out_time(table_row_idx)
            self.tw.table_widget.blockSignals(False)
        else:
            pass


    def undo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.old_value)
        self.tw.set_unsaved_changes(True)

    def redo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.new_value)
        self.tw.set_unsaved_changes(True)


class AddRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, view_row_to_insert_at: int, df_row_to_insert_at: int):
        super().__init__()
        self.tw = table_window
        self.view_row_to_insert_at = view_row_to_insert_at
        self.df_row_to_insert_at = df_row_to_insert_at
        self.new_row_id = -1
        self.new_row_data_for_df: Optional[Dict] = None
        self.setText(f"Agregar fila")

    def redo(self) -> None:
        self.new_row_id = self.tw.get_next_id()
        self.setText(f"Agregar fila (ID {self.new_row_id})")

        self.new_row_data_for_df = {
            'ID': self.new_row_id,
            'SCENE': "1", 'IN': '00:00:00:00', 'OUT': '00:00:00:00',
            'PERSONAJE': '', 'DIÁLOGO': ''
        }

        df = self.tw.dataframe
        if self.df_row_to_insert_at > 0 and self.df_row_to_insert_at <= len(df):
            prev_df_idx = self.df_row_to_insert_at - 1
            if prev_df_idx < len(df):
                self.new_row_data_for_df['SCENE'] = str(df.at[prev_df_idx, 'SCENE'])
                self.new_row_data_for_df['PERSONAJE'] = str(df.at[prev_df_idx, 'PERSONAJE'])
        elif not df.empty and self.df_row_to_insert_at == len(df): # Appending
            last_df_idx = len(df) - 1
            self.new_row_data_for_df['SCENE'] = str(df.at[last_df_idx, 'SCENE'])
            self.new_row_data_for_df['PERSONAJE'] = str(df.at[last_df_idx, 'PERSONAJE'])


        new_df_row_series = pd.Series(self.new_row_data_for_df)

        if self.df_row_to_insert_at >= len(df): # Append
            self.tw.dataframe = pd.concat([df, pd.DataFrame([new_df_row_series])], ignore_index=True)
        else: # Insert
            df_part1 = df.iloc[:self.df_row_to_insert_at]
            df_part2 = df.iloc[self.df_row_to_insert_at:]
            self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([new_df_row_series]), df_part2], ignore_index=True)

        self.tw.table_widget.blockSignals(True)
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
        self.tw.table_widget.blockSignals(False)
        self.tw.table_widget.selectRow(self.view_row_to_insert_at)
        self.tw.table_widget.scrollToItem(self.tw.table_widget.item(self.view_row_to_insert_at, 0))
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()


    def undo(self) -> None:
        if self.new_row_id == -1: return

        df_idx_to_remove = self.tw.find_dataframe_index_by_id(self.new_row_id)
        if df_idx_to_remove is not None:
            self.tw.dataframe.drop(index=df_idx_to_remove, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True)
        else:
            if self.df_row_to_insert_at < len(self.tw.dataframe):
                 self.tw.dataframe.drop(index=self.df_row_to_insert_at, inplace=True)
                 self.tw.dataframe.reset_index(drop=True, inplace=True)

        table_row_to_remove = self.tw.find_table_row_by_id(self.new_row_id)
        if table_row_to_remove is not None:
            self.tw.table_widget.removeRow(table_row_to_remove)
        elif self.view_row_to_insert_at < self.tw.table_widget.rowCount(): # Fallback
            self.tw.table_widget.removeRow(self.view_row_to_insert_at)

        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_rows_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        self.df_indices_removed = sorted(df_rows_indices_to_remove)
        self.removed_data_map: Dict[int, pd.Series] = {} # Maps original df_idx to row data
        self.setText(f"Eliminar {len(self.df_indices_removed)} fila(s)")

    def redo(self) -> None:
        self.removed_data_map.clear()
        df_indices_desc = sorted(self.df_indices_removed, reverse=True)

        for df_idx in df_indices_desc:
            if df_idx < len(self.tw.dataframe):
                self.removed_data_map[df_idx] = self.tw.dataframe.iloc[df_idx].copy()
                self.tw.dataframe.drop(index=df_idx, inplace=True)

        self.tw.dataframe.reset_index(drop=True, inplace=True)
        self.tw.populate_table()
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()

    def undo(self) -> None:
        for original_df_idx in self.df_indices_removed:
            row_data_series = self.removed_data_map.get(original_df_idx)
            if row_data_series is not None:
                df_part1 = self.tw.dataframe.iloc[:original_df_idx]
                df_part2 = self.tw.dataframe.iloc[original_df_idx:]
                self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([row_data_series]), df_part2], ignore_index=True)

        self.tw.populate_table()
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()


class MoveRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_source_idx: int, df_target_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_source_idx = df_source_idx
        self.df_target_idx = df_target_idx

        row_id_for_msg = df_source_idx
        if not self.tw.dataframe.empty and 'ID' in self.tw.dataframe.columns and df_source_idx < len(self.tw.dataframe) and pd.notna(self.tw.dataframe.at[df_source_idx, 'ID']):
            try:
                row_id_for_msg = int(self.tw.dataframe.at[df_source_idx, 'ID'])
            except ValueError: pass
        self.setText(f"Mover fila ID {row_id_for_msg} de {df_source_idx} a {df_target_idx}")

    def _perform_move(self, from_df_idx: int, to_df_idx: int):
        if from_df_idx >= len(self.tw.dataframe) or to_df_idx > len(self.tw.dataframe): # Adjusted target check
            # Handle cases where indices might be out of bounds, e.g., after other operations
            # This might happen if the command is redone after the DataFrame structure changed significantly.
            # A full repopulate might be needed if the state is too divergent.
            print(f"Advertencia en MoveRowCommand: Índices ({from_df_idx}, {to_df_idx}) fuera de rango para DataFrame de longitud {len(self.tw.dataframe)}.")
            self.tw.populate_table() # Fallback to refresh
            return

        rows_list = self.tw.dataframe.to_dict(orient='records')
        if not (0 <= from_df_idx < len(rows_list)):
            print(f"Advertencia en MoveRowCommand: from_df_idx {from_df_idx} inválido para lista de {len(rows_list)} filas.")
            self.tw.populate_table()
            return

        moved_row_data = rows_list.pop(from_df_idx)

        # Ensure to_df_idx is valid for insertion
        if not (0 <= to_df_idx <= len(rows_list)): # Can insert at len(rows_list) to append
            print(f"Advertencia en MoveRowCommand: to_df_idx {to_df_idx} inválido para lista de {len(rows_list)} filas (después de pop).")
            # As a fallback, append if to_df_idx is too large, or prepend if too small (or error out)
            if to_df_idx > len(rows_list):
                to_df_idx = len(rows_list)
            elif to_df_idx < 0:
                to_df_idx = 0
        
        rows_list.insert(to_df_idx, moved_row_data)
        self.tw.dataframe = pd.DataFrame(rows_list)

        self.tw.populate_table()

        moved_row_id_val = moved_row_data.get('ID') # Use moved_row_data which is a dict
        if pd.notna(moved_row_id_val):
            try:
                moved_row_id = int(moved_row_id_val)
                new_table_idx = self.tw.find_table_row_by_id(moved_row_id)
                if new_table_idx is not None:
                    self.tw.table_widget.selectRow(new_table_idx)
                    self.tw.table_widget.scrollToItem(self.tw.table_widget.item(new_table_idx, 0))
            except ValueError: pass

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
        self.original_dialog_at_split_idx: Optional[str] = None
        self.new_row_id_for_second_part = -1
        self.second_part_data_for_df: Optional[Dict] = None

        row_id_for_msg = df_row_idx_to_split
        if not self.tw.dataframe.empty and 'ID' in self.tw.dataframe.columns and df_row_idx_to_split < len(self.tw.dataframe) and pd.notna(self.tw.dataframe.at[df_row_idx_to_split, 'ID']):
            try:
                row_id_for_msg = int(self.tw.dataframe.at[df_row_idx_to_split, 'ID'])
            except ValueError: pass
        self.setText(f"Separar intervención en fila ID {row_id_for_msg}")


    def redo(self) -> None:
        if self.df_idx_split >= len(self.tw.dataframe): return

        if self.original_dialog_at_split_idx is None:
             self.original_dialog_at_split_idx = str(self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'])

        self.new_row_id_for_second_part = self.tw.get_next_id()

        self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.before_text

        if self.second_part_data_for_df is None:
            original_row_data_series = self.tw.dataframe.iloc[self.df_idx_split].copy()
            self.second_part_data_for_df = original_row_data_series.to_dict()
            self.second_part_data_for_df['ID'] = self.new_row_id_for_second_part
            self.second_part_data_for_df['DIÁLOGO'] = self.after_text
            # Consider IN/OUT for the new part. Default: copies from original.
            # Example: set IN of new part to OUT of original part, if desired.
            # self.second_part_data_for_df['IN'] = self.tw.dataframe.at[self.df_idx_split, 'OUT']

        df_idx_insert_new_part_at = self.df_idx_split + 1
        new_series_to_insert = pd.Series(self.second_part_data_for_df)

        df_part1 = self.tw.dataframe.iloc[:df_idx_insert_new_part_at]
        df_part2 = self.tw.dataframe.iloc[df_idx_insert_new_part_at:]
        self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([new_series_to_insert]), df_part2], ignore_index=True)

        self.tw.populate_table()

        original_part_id_val = self.tw.dataframe.at[self.df_idx_split, 'ID']
        if pd.notna(original_part_id_val):
            try:
                original_part_id = int(original_part_id_val)
                table_idx_original = self.tw.find_table_row_by_id(original_part_id)
                if table_idx_original is not None:
                    self.tw.table_widget.selectRow(table_idx_original)
                    self.tw.table_widget.scrollToItem(self.tw.table_widget.item(table_idx_original,0))
            except ValueError: pass
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()

    def undo(self) -> None:
        if self.original_dialog_at_split_idx is None or self.new_row_id_for_second_part == -1:
            return

        if self.df_idx_split < len(self.tw.dataframe):
            self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.original_dialog_at_split_idx

        df_idx_of_second_part = self.tw.find_dataframe_index_by_id(self.new_row_id_for_second_part)
        if df_idx_of_second_part is not None:
            self.tw.dataframe.drop(index=df_idx_of_second_part, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True)

        self.tw.populate_table()

        original_part_id_val = self.tw.dataframe.at[self.df_idx_split, 'ID']
        if pd.notna(original_part_id_val):
            try:
                original_part_id = int(original_part_id_val)
                table_idx_original = self.tw.find_table_row_by_id(original_part_id)
                if table_idx_original is not None:
                    self.tw.table_widget.selectRow(table_idx_original)
                    self.tw.table_widget.scrollToItem(self.tw.table_widget.item(table_idx_original,0))
            except ValueError: pass
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()


class MergeInterventionsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_idx_first_row: int, merged_dialog: str, df_idx_second_row_to_remove: int, original_out_time_first_row: str):
        super().__init__()
        self.tw = table_window
        self.df_idx_first = df_idx_first_row
        self.df_idx_second_removed = df_idx_second_row_to_remove
        self.merged_dialog = merged_dialog
        self.original_dialog_first: Optional[str] = None
        self.original_out_time_first: str = original_out_time_first_row # Store original OUT time
        self.data_of_second_row_removed: Optional[pd.Series] = None

        row_id_first = df_idx_first_row
        if not self.tw.dataframe.empty and 'ID' in self.tw.dataframe.columns and df_idx_first_row < len(self.tw.dataframe) and pd.notna(self.tw.dataframe.at[df_idx_first_row, 'ID']):
            try:
                row_id_first = int(self.tw.dataframe.at[df_idx_first_row, 'ID'])
            except ValueError: pass
        self.setText(f"Juntar intervenciones (ID {row_id_first} con siguiente)")

    def redo(self) -> None:
        if self.df_idx_first >= len(self.tw.dataframe) or self.df_idx_second_removed >= len(self.tw.dataframe):
             return

        if self.original_dialog_first is None:
            self.original_dialog_first = str(self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'])
        if self.data_of_second_row_removed is None:
            self.data_of_second_row_removed = self.tw.dataframe.iloc[self.df_idx_second_removed].copy()

        self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.merged_dialog
        if 'OUT' in self.data_of_second_row_removed: # Ensure 'OUT' exists in the removed row data
            self.tw.dataframe.at[self.df_idx_first, 'OUT'] = self.data_of_second_row_removed['OUT']

        self.tw.dataframe.drop(index=self.df_idx_second_removed, inplace=True)
        self.tw.dataframe.reset_index(drop=True, inplace=True)

        self.tw.populate_table()

        merged_row_id_val = None
        if self.df_idx_first < len(self.tw.dataframe):
             merged_row_id_val = self.tw.dataframe.at[self.df_idx_first, 'ID']

        if pd.notna(merged_row_id_val):
            try:
                merged_row_id = int(merged_row_id_val)
                table_idx_merged = self.tw.find_table_row_by_id(merged_row_id)
                if table_idx_merged is not None:
                    self.tw.table_widget.selectRow(table_idx_merged)
                    self.tw.table_widget.scrollToItem(self.tw.table_widget.item(table_idx_merged,0))
            except ValueError: pass
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()

    def undo(self) -> None:
        if self.original_dialog_first is None or self.data_of_second_row_removed is None:
            return

        if self.df_idx_first < len(self.tw.dataframe):
            self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.original_dialog_first
            self.tw.dataframe.at[self.df_idx_first, 'OUT'] = self.original_out_time_first # Restore original OUT time


        df_part1 = self.tw.dataframe.iloc[:self.df_idx_second_removed]
        df_part2 = self.tw.dataframe.iloc[self.df_idx_second_removed:]
        self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([self.data_of_second_row_removed]), df_part2], ignore_index=True)

        self.tw.populate_table()

        first_row_id_val = None
        if self.df_idx_first < len(self.tw.dataframe):
            first_row_id_val = self.tw.dataframe.at[self.df_idx_first, 'ID']

        if pd.notna(first_row_id_val):
            try:
                first_row_id = int(first_row_id_val)
                table_idx_first = self.tw.find_table_row_by_id(first_row_id)
                if table_idx_first is not None:
                    self.tw.table_widget.selectRow(table_idx_first)
                    self.tw.table_widget.scrollToItem(self.tw.table_widget.item(table_idx_first,0))
            except ValueError: pass
        self.tw.set_unsaved_changes(True)
        self.tw.update_character_completer()


class ChangeSceneCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_start_row_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_start_idx = df_start_row_idx
        self.old_scene_numbers_map: Dict[int, str] = {}

        row_id_for_msg = df_start_row_idx
        if not self.tw.dataframe.empty and 'ID' in self.tw.dataframe.columns and df_start_row_idx < len(self.tw.dataframe) and pd.notna(self.tw.dataframe.at[df_start_row_idx, 'ID']):
            try:
                row_id_for_msg = int(self.tw.dataframe.at[df_start_row_idx, 'ID'])
            except ValueError: pass
        self.setText(f"Cambiar escena desde fila ID {row_id_for_msg}")

    def _apply_scene_changes(self, scene_map_to_apply: Dict[int, str], select_row_with_id: Optional[int] = None):
        for df_idx, scene_str_val in scene_map_to_apply.items():
            if df_idx < len(self.tw.dataframe):
                self.tw.dataframe.at[df_idx, 'SCENE'] = scene_str_val

        self.tw.populate_table()

        if select_row_with_id is not None:
            table_idx_to_select = self.tw.find_table_row_by_id(select_row_with_id)
            if table_idx_to_select is not None:
                self.tw.table_widget.selectRow(table_idx_to_select)
                self.tw.table_widget.scrollToItem(self.tw.table_widget.item(table_idx_to_select, 0))

        self.tw.set_unsaved_changes(True)
        if not self.tw.dataframe.empty and 'SCENE' in self.tw.dataframe.columns:
            unique_scenes = set(str(s).strip() for s in self.tw.dataframe['SCENE'].unique() if pd.notna(s))
            if len(unique_scenes) > 1 or (len(unique_scenes) == 1 and "1" not in unique_scenes and "" not in unique_scenes) :
                self.tw.has_scene_numbers = True
            else:
                self.tw.has_scene_numbers = False


    def redo(self) -> None:
        if self.df_start_idx >= len(self.tw.dataframe): return

        self.old_scene_numbers_map.clear()
        new_scene_changes_map: Dict[int, str] = {}

        current_scene_val_at_start = 0
        try:
            scene_text_at_start = str(self.tw.dataframe.at[self.df_start_idx, 'SCENE']).strip()
            if scene_text_at_start:
                current_scene_val_at_start = int(scene_text_at_start)
        except (ValueError, IndexError):
            current_scene_val_at_start = 0

        new_scene_to_set_from_start = str(current_scene_val_at_start + 1)

        id_of_first_changed_row = None
        if self.df_start_idx < len(self.tw.dataframe) and 'ID' in self.tw.dataframe.columns and pd.notna(self.tw.dataframe.at[self.df_start_idx, 'ID']):
            try:
                id_of_first_changed_row = int(self.tw.dataframe.at[self.df_start_idx, 'ID'])
            except ValueError: pass


        for df_idx in range(self.df_start_idx, len(self.tw.dataframe)):
            self.old_scene_numbers_map[df_idx] = str(self.tw.dataframe.at[df_idx, 'SCENE'])
            new_scene_changes_map[df_idx] = new_scene_to_set_from_start

        self._apply_scene_changes(new_scene_changes_map, select_row_with_id=id_of_first_changed_row)


    def undo(self) -> None:
        id_of_first_restored_row = None
        if self.df_start_idx < len(self.tw.dataframe) and 'ID' in self.tw.dataframe.columns and pd.notna(self.tw.dataframe.at[self.df_start_idx, 'ID']):
            try:
                id_of_first_restored_row = int(self.tw.dataframe.at[self.df_start_idx, 'ID'])
            except ValueError: pass

        self._apply_scene_changes(self.old_scene_numbers_map, select_row_with_id=id_of_first_restored_row)