import json
import os
import logging
from typing import Any, List, Dict, Optional, Tuple

import pandas as pd

# --- CAMBIOS PyQt6 ---
from PyQt6.QtCore import pyqtSignal, QObject, QEvent, Qt, QSize
from PyQt6.QtGui import QFont, QKeySequence, QColor, QIntValidator, QBrush, QAction, QFontMetrics
from PyQt6.QtWidgets import (
    QWidget, QTextEdit, QFileDialog, QAbstractItemView,
    QMessageBox, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QLabel, QFormLayout, QTableWidgetItem,
    QHeaderView # Para setStretchLastSection
)
from PyQt6.QtGui import QShortcut, QUndoStack, QUndoCommand # QShortcut está en QtGui

# Tus imports (asegúrate que estén actualizados a PyQt6 si usan Qt)
from guion_editor.delegates.custom_delegates import TimeCodeDelegate, CharacterDelegate
from guion_editor.utils.dialog_utils import ajustar_dialogo
from guion_editor.widgets.custom_table_widget import CustomTableWidget # Asumir que se migrará
from guion_editor.widgets.custom_text_edit import CustomTextEdit # Asumir que se migrará
from guion_editor.utils.guion_manager import GuionManager

logger_tw = logging.getLogger(__name__)

VALID_TIME_BG_COLOR = QColor(Qt.GlobalColor.white)
INVALID_TIME_BG_COLOR = QColor(255, 200, 200) # RGB sigue válido

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
            return super().eventFilter(obj, event) # Importante llamar al base

    def __init__(self, video_player_widget: Any, main_window: Optional[QWidget] = None, guion_manager: Optional[GuionManager] = None):
        logger_tw.info("TableWindow: Entrando a __init__")
        super().__init__()
        logger_tw.info("TableWindow: super().__init__() completado")

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
        self._tw_shortcuts: List[QShortcut] = [] # Para mantener referencias a shortcuts
        self.clipboard_text: str = ""

        self.reference_number = "" # Estos parecen ser datos, no widgets
        self.product_name = ""
        self.chapter_number = ""
        self.selected_type = ""

        logger_tw.info("TableWindow: Llamando a setup_ui...")
        self.setup_ui()
        logger_tw.info("TableWindow: setup_ui() completado.")
        
        """ logger_tw.info("TableWindow: Llamando a setup_shortcuts...")
        self.setup_shortcuts()
        logger_tw.info("TableWindow: setup_shortcuts() completado.") """
        
        self.clear_script_state()
        logger_tw.info("TableWindow: __init__ completado.")


    def setup_ui(self) -> None:
        logger_tw.info("TableWindow: Entrando a setup_ui")
        layout = QVBoxLayout(self)
        
        logger_tw.info("TableWindow: Configurando campos de cabecera...")
        self.setup_header_fields(layout)
        logger_tw.info("TableWindow: Campos de cabecera configurados.")

        logger_tw.info("TableWindow: Configurando botones...")
        self.setup_buttons(layout)
        logger_tw.info("TableWindow: Botones configurados.")

        logger_tw.info("TableWindow: Configurando table_widget...")
        self.setup_table_widget(layout)
        logger_tw.info("TableWindow: table_widget configurado.")

        logger_tw.info("TableWindow: Cargando stylesheet...")
        self.load_stylesheet()
        logger_tw.info("TableWindow: Stylesheet cargado.")
        logger_tw.info("TableWindow: setup_ui completado")


    """ def setup_shortcuts(self) -> None:
        logger_tw.info("TableWindow: Entrando a setup_shortcuts")
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
        logger_tw.info("TableWindow: setup_shortcuts completado")
 """
    def setup_header_fields(self, layout: QVBoxLayout) -> None:
        logger_tw.info("TableWindow: Entrando a setup_header_fields")
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
        logger_tw.info("TableWindow: setup_header_fields completado")


    def setup_buttons(self, layout: QVBoxLayout) -> None:
        logger_tw.info("TableWindow: Entrando a setup_buttons")
        buttons_layout = QHBoxLayout()
        actions_map = [ # Renombrado para evitar conflicto
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
        logger_tw.info("TableWindow: setup_buttons completado")

    def setup_table_widget(self, layout: QVBoxLayout) -> None:
        logger_tw.info("TableWindow: Entrando a setup_table_widget")
        self.table_widget = CustomTableWidget()
        logger_tw.info("TableWindow: CustomTableWidget instanciado.")
        
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
        
        # Asumiendo que los delegates se migrarán y son compatibles con PyQt6
        self.table_widget.setItemDelegateForColumn(self.COL_IN, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(self.COL_OUT, TimeCodeDelegate(self.table_widget))
        self.table_widget.setItemDelegateForColumn(self.COL_CHARACTER, CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget))
        
        self.table_widget.cellCtrlClicked.connect(self.handle_ctrl_click)
        self.table_widget.cellAltClicked.connect(self.handle_alt_click)
        self.table_widget.itemChanged.connect(self.on_item_changed)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
        logger_tw.info("TableWindow: setup_table_widget completado")

    def load_stylesheet(self) -> None:
        try:
            logger_tw.info("TableWindow: Entrando a load_stylesheet")
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            # Ruta corregida asumiendo estructura: project_root/guion_editor/widgets/ y project_root/guion_editor/styles/
            css_path = os.path.join(current_file_dir, '..', 'styles', 'table_styles.css')

            if not os.path.exists(css_path):
                logger_tw.warning(f"Stylesheet de tabla no encontrado en: {css_path}")
                # Considerar una ruta alternativa si la estructura es diferente
                # por ejemplo, si 'styles' está al mismo nivel que 'widgets'
                alt_css_path = os.path.join(current_file_dir, 'styles', 'table_styles.css')
                if os.path.exists(alt_css_path):
                    css_path = alt_css_path
                else:
                    logger_tw.error(f"Stylesheet de tabla tampoco encontrado en ruta alternativa: {alt_css_path}")
                    return
            
            logger_tw.info(f"Cargando stylesheet de tabla desde: {css_path}")
            with open(css_path, 'r', encoding='utf-8') as f:
                self.table_widget.setStyleSheet(f.read())
            logger_tw.info("TableWindow: Stylesheet de tabla cargado.")
        except Exception as e:
            logger_tw.error(f"Error al cargar stylesheet para la tabla: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Error de Estilos", f"Error al cargar stylesheet para la tabla: {str(e)}")


    def _populate_header_ui(self, header_data: Dict[str, Any]):
        logger_tw.debug(f"Poblando UI de cabecera con: {header_data}")
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
        logger_tw.debug(f"Obteniendo datos de UI de cabecera: {data}")
        return data

    def _post_load_script_actions(self, file_path: str, df: pd.DataFrame, header_data: Dict[str, Any], has_scenes: bool):
        logger_tw.info(f"Acciones post-carga para: {file_path}")
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
        logger_tw.info("Abriendo diálogo para cargar DOCX...")
        file_name, _ = QFileDialog.getOpenFileName(self, "Abrir Guion DOCX", "", "Documentos de Word (*.docx);;Todos los archivos (*.*)")
        if file_name:
            logger_tw.info(f"Archivo DOCX seleccionado: {file_name}")
            self.load_from_docx_path(file_name)

    def load_from_docx_path(self, file_path: str):
        logger_tw.info(f"Cargando DOCX desde: {file_path}")
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_docx(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e:
            self.handle_exception(e, f"Error al cargar DOCX: {file_path}")
            self.clear_script_state()


    def import_from_excel_dialog(self) -> None:
        logger_tw.info("Abriendo diálogo para importar Excel...")
        path, _ = QFileDialog.getOpenFileName(self, "Importar Guion desde Excel", "", "Archivos Excel (*.xlsx);;Todos los archivos (*.*)")
        if path:
            logger_tw.info(f"Archivo Excel para importar seleccionado: {path}")
            self.load_from_excel_path(path)

    def load_from_excel_path(self, file_path: str):
        logger_tw.info(f"Importando Excel desde: {file_path}")
        try:
            df, header_data, has_scenes = self.guion_manager.load_from_excel(file_path)
            self._post_load_script_actions(file_path, df, header_data, has_scenes)
        except Exception as e:
            self.handle_exception(e, f"Error al cargar Excel: {file_path}")
            self.clear_script_state()


    def export_to_excel_dialog(self) -> bool: # Retorna True si se guardó, False si no
        """Exporta los datos actuales a un archivo Excel, abriendo diálogo."""
        if self.dataframe.empty:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return False

        self._update_dataframe_from_table() # Sincronizar DF con la tabla antes de guardar
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
                if self.main_window: # Añadir a recientes también al guardar como
                    self.main_window.add_to_recent_files(path)
                return True
            except Exception as e:
                self.handle_exception(e, "Error al exportar a Excel")
                return False
        return False # Diálogo cancelado


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

    def save_to_json_dialog(self) -> bool: # Retorna True si se guardó, False si no
        """Guarda los datos actuales en un archivo JSON, abriendo diálogo."""
        if self.dataframe.empty:
            QMessageBox.information(self, "Guardar", "No hay datos para guardar.")
            return False

        self._update_dataframe_from_table() # Sincronizar DF con la tabla
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
        return False # Diálogo cancelado

    def clear_script_state(self):
        """Resetea el estado del guion a vacío."""
        self.dataframe = pd.DataFrame(columns=list(self.TABLE_TO_DF_COL_MAP.values()))
        self._populate_header_ui({}) # Limpia campos de cabecera
        self.has_scene_numbers = False
        self.populate_table() # Limpia la tabla
        self.undo_stack.clear()
        self.current_script_name = None
        self.current_script_path = None
        self.update_window_title()
        self.set_unsaved_changes(False)


    # --- Fin de métodos de carga/guardado refactorizados ---

    def populate_table(self) -> None:
        try:
            self.table_widget.blockSignals(True)
            self.table_widget.clearContents() # Usar clearContents en lugar de clear para mantener headers
            
            if self.dataframe.empty:
                self.table_widget.setRowCount(0) # Asegurar que la tabla esté vacía
                # QMessageBox.information(self, "Información", "El guion está vacío.") # Evitar pop-up constante
                logger_tw.info("Populate table: DataFrame está vacío.")
                self.table_widget.blockSignals(False)
                return

            self.table_widget.setRowCount(self.dataframe.shape[0])
            # No es necesario re-setear headers si se usa clearContents()
            # self.table_widget.setColumnCount(len(self.columns))
            # self.table_widget.setHorizontalHeaderLabels(self.columns)
            # self.table_widget.setColumnHidden(self.columns.index("ID"), True)

            for i in range(self.dataframe.shape[0]):
                for col_index, df_col_name in self.TABLE_TO_DF_COL_MAP.items(): # Usar el mapeo
                    table_col_name = self.columns[col_index] # Nombre de columna en la tabla UI

                    # Asegurarse que la columna del DF existe antes de acceder
                    if df_col_name not in self.dataframe.columns:
                        # logger_tw.warning(f"Columna DataFrame '{df_col_name}' no encontrada al poblar la tabla. Saltando.")
                        # Crear item vacío si la columna no existe en el df para esta fila
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


                    if table_col_name == "DIÁLOGO": # Comparar con nombre de columna UI
                        dialog_text = item_text
                        widget = self.create_text_edit(dialog_text, i, col_index) # col_index es correcto
                        self.table_widget.setCellWidget(i, col_index, widget)
                    else:
                        item = self.create_table_item(item_text, col_index)
                        self.table_widget.setItem(i, col_index, item)
                self.adjust_row_height(i)
                self.validate_in_out_time(i) # Validar al poblar

            # self.table_widget.resizeColumnsToContents()
            # Intentar ajustar la última sección si la tabla no está vacía
            if self.table_widget.columnCount() > 0: # Solo si hay columnas
                 self.table_widget.horizontalHeader().setStretchLastSection(True)

        except Exception as e:
            self.handle_exception(e, "Error al llenar la tabla")
        finally:
            self.table_widget.blockSignals(False)


    def create_text_edit(self, text: str, row: int, column: int) -> CustomTextEdit:
        text_edit = CustomTextEdit()
        # text_edit.setStyleSheet("font-size: 16px;") # Considerar aplicar desde main.css o configuración
        text_edit.setPlainText(text)
        text_edit.editingFinished.connect(self.on_editing_finished_text_edit) # Renombrado para claridad
        return text_edit

    def create_table_item(self, text: str, column: int) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        return item

    def adjust_row_height(self, row: int) -> None:
        try:
            widget = self.table_widget.cellWidget(row, self.COL_DIALOGUE)
            if widget and isinstance(widget, QTextEdit): # Asegurarse que es un QTextEdit
                doc = widget.document()
                # Heurística para calcular altura, puede necesitar ajustes
                # Basado en el número de líneas de texto y un factor de altura por línea
                # num_lines = doc.blockCount()
                # line_height_approx = widget.fontMetrics().height() + 2 # +2 para un poco de padding
                # total_height = num_lines * line_height_approx + 10 # +10 para márgenes generales
                
                # Usar size().height() es más preciso si el contenido ya está renderizado
                total_height = doc.size().height() + widget.contentsMargins().top() + widget.contentsMargins().bottom() + 10
                self.table_widget.setRowHeight(row, int(max(total_height, widget.fontMetrics().height() + 10))) # Mínimo una línea
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
            if not df_col_name or row >= len(self.dataframe): # Chequeo de límites
                return

            new_text = item.text()
            old_text = str(self.dataframe.at[row, df_col_name]) # Convertir a str para comparación

            if df_col_name == 'SCENE':
                try:
                    # Aunque lo guardemos como string, validamos que pueda ser int si no está vacío
                    if new_text.strip(): int(new_text)
                except ValueError:
                    QMessageBox.warning(self, "Error de Tipo", f"El valor '{new_text}' no es un número válido para 'SCENE'.")
                    item.setText(old_text) # Revertir
                    return
            
            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True) # Marcar cambios
                if column == self.COL_SCENE:
                    self.has_scene_numbers = True
                if column in [self.COL_IN, self.COL_OUT]:
                    self.validate_in_out_time(row)
        except Exception as e:
            self.handle_exception(e, f"Error al actualizar celda en la tabla (itemChanged): {e}")


    def on_editing_finished_text_edit(self) -> None: # Renombrado
        """Maneja el evento cuando se finaliza la edición de un CustomTextEdit (diálogo)."""
        try:
            text_edit_widget = self.sender()
            if not isinstance(text_edit_widget, CustomTextEdit):
                return

            # Encontrar la fila y columna del widget
            found_pos = None
            for r_idx in range(self.table_widget.rowCount()):
                if self.table_widget.cellWidget(r_idx, self.COL_DIALOGUE) == text_edit_widget:
                    found_pos = (r_idx, self.COL_DIALOGUE)
                    break
            
            if not found_pos:
                return

            row, column = found_pos
            df_col_name = self.get_dataframe_column_name(column)
            if not df_col_name or row >= len(self.dataframe): # Chequeo de límites
                return

            new_text = text_edit_widget.toPlainText()
            old_text = str(self.dataframe.at[row, df_col_name]) # Convertir a str

            if new_text != old_text:
                command = EditCommand(self, row, column, old_text, new_text)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True) # Marcar cambios
                self.adjust_row_height(row) # Reajustar altura si el diálogo cambió
        except Exception as e:
            self.handle_exception(e, f"Error al finalizar la edición del texto del diálogo: {e}")


    def _update_dataframe_from_table(self) -> None:
        """Actualiza self.dataframe con los datos de la QTableWidget. Crucial antes de guardar."""
        try:
            if self.dataframe.empty and self.table_widget.rowCount() == 0:
                return

            # Si el dataframe tiene una estructura diferente a la tabla (ej. tras borrar todo y añadir filas)
            # es mejor reconstruirlo o tener cuidado. Por ahora, asumimos que coinciden en filas.
            # O, mejor, iteramos por las filas de la tabla y actualizamos/creamos en el DF por ID.

            temp_data = []
            for row_idx in range(self.table_widget.rowCount()):
                row_dict = {}
                valid_id = False
                try:
                    id_val = int(self.table_widget.item(row_idx, self.COL_ID).text())
                    row_dict['ID'] = id_val
                    valid_id = True
                except (ValueError, AttributeError):
                    # Si no hay ID válido, podríamos generar uno o saltar la fila para la actualización del DF
                    # Esto puede pasar si se añaden filas sin IDs correctos (aunque AddRowCommand debería manejarlo)
                    logger_tw.warning(f"Fila {row_idx} sin ID válido en la tabla al actualizar DataFrame.")
                    # Asignar un ID temporal negativo para marcarlo, o generar uno nuevo si es una fila nueva sin ID
                    # Esto depende de cómo se manejen las filas nuevas que aún no están en el DF.
                    # Por ahora, si no hay ID, no podemos mapear directamente a una fila existente del DF.
                    # Lo más seguro es construir un nuevo DF a partir de la tabla.
                    pass # Se manejará al construir el nuevo DF

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
                # Asegurar que ID sea int si existe
                if 'ID' in new_df.columns:
                    new_df['ID'] = pd.to_numeric(new_df['ID'], errors='coerce').fillna(-1).astype(int)
                # Asegurar que SCENE sea string
                if 'SCENE' in new_df.columns:
                    new_df['SCENE'] = new_df['SCENE'].astype(str)

                self.dataframe = new_df
            else: # Si la tabla está vacía, el dataframe también debería estarlo
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
                    if old_value != self.clipboard_text: # Solo si el valor cambia
                        # Aquí, en lugar de EditCommand directo que opera sobre el DF,
                        # simplemente seteamos el texto del item. EditCommand se creará
                        # desde on_item_changed.
                        current_item.setText(self.clipboard_text)
                        # on_item_changed se disparará y creará el EditCommand y marcará unsaved_changes
                        # self.validate_in_out_time(current_row) # on_item_changed lo hará
        except Exception as e:
            self.handle_exception(e, "Error al pegar el tiempo")

    def adjust_dialogs(self) -> None:
        try:
            self._update_dataframe_from_table() # Asegurar que el DF esté al día con la UI
            self.undo_stack.beginMacro("Ajustar Diálogos")
            changed_any = False
            for i in range(len(self.dataframe)): # Iterar sobre el DF
                dialog_text_original = str(self.dataframe.at[i, 'DIÁLOGO'])
                adjusted_text = ajustar_dialogo(dialog_text_original)
                
                if dialog_text_original != adjusted_text:
                    # Crear comando para el cambio en el DF y la tabla
                    # EditCommand actualizará tanto el DF como el item/widget de la tabla
                    command = EditCommand(self, i, self.COL_DIALOGUE, dialog_text_original, adjusted_text)
                    self.undo_stack.push(command)
                    changed_any = True
                    # self.adjust_row_height(i) # EditCommand ya llama a _apply_value que ajusta altura para diálogos

            self.undo_stack.endMacro()
            if changed_any:
                self.set_unsaved_changes(True)
                QMessageBox.information(self, "Éxito", "Diálogos ajustados correctamente.")
            else:
                QMessageBox.information(self, "Información", "No hubo diálogos que necesitaran ajuste.")

        except Exception as e:
            self.undo_stack.endMacro() # Asegurar que el macro se cierre en caso de error
            self.handle_exception(e, "Error al ajustar diálogos")


    def copy_in_out_to_next(self) -> None:
        try:
            selected_row_idx = self.table_widget.currentRow()
            if selected_row_idx == -1 or selected_row_idx >= len(self.dataframe) - 1:
                QMessageBox.warning(self, "Copiar IN/OUT", "Seleccione una fila válida que no sea la última.")
                return

            self._update_dataframe_from_table() # Sincronizar

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
            
            if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Copiar IN/OUT"): # Heurística para ver si se apiló algo
                 self.set_unsaved_changes(True)
                 # EditCommand se encarga de validate_in_out_time para la fila next_row_idx
                 QMessageBox.information(self, "Copiar IN/OUT", "Tiempos IN y OUT copiados a la siguiente intervención.")
            
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al copiar IN/OUT")


    def add_new_row(self) -> None:
        try:
            selected_row = self.table_widget.currentRow()
            # La fila donde se insertará en la VISTA de tabla
            # AddRowCommand se encargará de la lógica de inserción en el DF también
            insert_at_row_idx = selected_row + 1 if selected_row != -1 else self.table_widget.rowCount()
            
            command = AddRowCommand(self, insert_at_row_idx) # Pasar el índice de la VISTA de tabla
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

            # Obtener los índices de las filas de la VISTA de tabla
            rows_to_remove_view_indices = sorted([index.row() for index in selected_indexes], reverse=True)
            
            confirm = QMessageBox.question(self, "Confirmar Eliminación", "¿Estás seguro?",
                                           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                # RemoveRowsCommand necesita los índices de las filas del DataFrame
                # Esto es complicado si el DF y la tabla no están perfectamente sincronizados por ID
                # Por simplicidad, RemoveRowsCommand podría operar sobre los índices de la vista,
                # y luego internamente mapear a IDs del DF o reconstruir el DF.
                # Vamos a pasarle los IDs de las filas seleccionadas en la tabla
                
                self._update_dataframe_from_table() # Asegurar que el DF esté al día

                ids_to_remove = []
                valid_rows_df_indices = []

                for row_view_idx in rows_to_remove_view_indices:
                    id_item = self.table_widget.item(row_view_idx, self.COL_ID)
                    if id_item:
                        try:
                            row_id = int(id_item.text())
                            df_idx = self.find_dataframe_index_by_id(row_id) # Busca en self.dataframe
                            if df_idx is not None:
                                ids_to_remove.append(row_id)
                                valid_rows_df_indices.append(df_idx) # Guardamos índices del DF
                            else:
                                logger_tw.warning(f"ID {row_id} de la tabla no encontrado en DataFrame al intentar eliminar.")
                        except ValueError:
                             logger_tw.warning(f"ID no numérico '{id_item.text()}' en tabla al intentar eliminar.")
                    else: # Si no hay item ID, es una fila "fantasma" o nueva no guardada en DF
                        # Simplemente la eliminamos de la tabla visualmente si no tiene ID
                        # Pero RemoveRowsCommand opera sobre el DF.
                        # Esto indica una posible desincronización o un caso de uso no completamente cubierto.
                        # Por ahora, solo procesamos filas con ID válido en el DF.
                        logger_tw.warning(f"Fila {row_view_idx} sin ID item en tabla al intentar eliminar.")


                if ids_to_remove:
                    # Pasar los índices del DataFrame ordenados ascendentemente
                    command = RemoveRowsCommand(self, sorted(valid_rows_df_indices))
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
                elif rows_to_remove_view_indices: # Si había filas seleccionadas pero ninguna con ID en DF
                    # Podríamos simplemente borrar de la tabla si son filas "nuevas" no persistidas
                    # Pero esto no sería "deshacible" por RemoveRowsCommand tal como está.
                    # Por ahora, si no hay IDs válidos en el DF, no hacemos nada con el comando.
                    # Si el usuario seleccionó filas y no se borró nada, mostrar un mensaje.
                    QMessageBox.information(self, "Información", "No se eliminaron filas del modelo de datos (posiblemente filas nuevas sin guardar o sin ID).")


        except Exception as e:
            self.handle_exception(e, "Error al eliminar las filas")


    def move_row_up(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx > 0: # No se puede mover la primera fila hacia arriba
                self._update_dataframe_from_table() # Sincronizar DF

                # MoveRowCommand opera sobre índices del DataFrame
                # Necesitamos mapear el selected_row_view_idx al índice del DF
                id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not id_item: return
                
                current_row_id = int(id_item.text())
                df_idx_source = self.find_dataframe_index_by_id(current_row_id)

                if df_idx_source is not None and df_idx_source > 0:
                    # El target es el índice anterior en el DF
                    command = MoveRowCommand(self, df_idx_source, df_idx_source - 1)
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
                    # La selección en la tabla se actualizará en el redo del comando
                else:
                    logger_tw.warning("No se pudo mover la fila hacia arriba, ID no encontrado en DF o ya es la primera.")

        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia arriba")


    def move_row_down(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx < self.table_widget.rowCount() - 1: # No se puede mover la última
                self._update_dataframe_from_table() # Sincronizar DF

                id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
                if not id_item: return
                
                current_row_id = int(id_item.text())
                df_idx_source = self.find_dataframe_index_by_id(current_row_id)

                if df_idx_source is not None and df_idx_source < len(self.dataframe) - 1:
                     # El target es el índice siguiente en el DF
                    command = MoveRowCommand(self, df_idx_source, df_idx_source + 1)
                    self.undo_stack.push(command)
                    self.set_unsaved_changes(True)
                else:
                    logger_tw.warning("No se pudo mover la fila hacia abajo, ID no encontrado en DF o ya es la última.")
        except Exception as e:
            self.handle_exception(e, "Error al mover la fila hacia abajo")


    def split_intervention(self) -> None:
        try:
            selected_row_view_idx = self.table_widget.currentRow()
            if selected_row_view_idx == -1:
                QMessageBox.warning(self, "Separar", "Selecciona una fila.")
                return

            self._update_dataframe_from_table() # Sincronizar DF

            dialog_widget = self.table_widget.cellWidget(selected_row_view_idx, self.COL_DIALOGUE)
            if not isinstance(dialog_widget, QTextEdit): return

            # Mapear a índice del DF
            id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            if not id_item: return
            current_row_id = int(id_item.text())
            df_idx = self.find_dataframe_index_by_id(current_row_id)
            if df_idx is None: return

            text = dialog_widget.toPlainText() # Tomar texto de la UI
            cursor_pos = dialog_widget.textCursor().position()

            if cursor_pos == 0 or cursor_pos >= len(text):
                QMessageBox.information(self, "Separar", "Coloca el cursor en el punto de división (no al inicio o fin).")
                return

            before_text = text[:cursor_pos].strip()
            after_text = text[cursor_pos:].strip()

            if not after_text: # No tiene sentido separar si no hay texto después
                 QMessageBox.information(self, "Separar", "No hay texto para la nueva intervención después del cursor.")
                 return


            # SplitInterventionCommand opera sobre el índice del DF
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

            self._update_dataframe_from_table() # Sincronizar DF

            # Mapear a índices del DF
            id_item_curr = self.table_widget.item(selected_row_view_idx, self.COL_ID)
            id_item_next = self.table_widget.item(selected_row_view_idx + 1, self.COL_ID)
            if not id_item_curr or not id_item_next: return

            curr_row_id = int(id_item_curr.text())
            next_row_id = int(id_item_next.text())

            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            df_idx_next = self.find_dataframe_index_by_id(next_row_id)

            if df_idx_curr is None or df_idx_next is None: return
            if df_idx_next != df_idx_curr + 1: # Asegurar que son adyacentes en el DF
                logger_tw.error("Las filas a juntar no son adyacentes en el DataFrame.")
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

            # MergeInterventionsCommand opera sobre el índice del DF de la primera fila
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
        except ValueError: # Si la conversión falla (ej. TC vacío o malformado)
            # logger_tw.warning(f"Timecode inválido '{time_code}' al convertir a ms. Devolviendo 0.")
            return 0 # Devolver 0 o manejar de otra forma
        except Exception as e: # Otros errores inesperados
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
                # QMessageBox.warning(self, "Error", "No hay fila seleccionada.") # Puede ser molesto
                return

            self._update_dataframe_from_table() # Sincronizar por si acaso

            # Mapear a índice del DF
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
                # EditCommand se encarga de la validación visual
        except Exception as e:
            self.handle_exception(e, "Error en update_in_out")


    def select_next_row_and_set_in(self) -> None:
        try:
            current_row_view_idx = self.table_widget.currentRow()
            if current_row_view_idx == -1 or current_row_view_idx >= self.table_widget.rowCount() - 1:
                return # No hay siguiente fila o ninguna seleccionada

            self._update_dataframe_from_table() # Sincronizar

            # Mapear a índice del DF para la fila actual
            id_item_curr = self.table_widget.item(current_row_view_idx, self.COL_ID)
            if not id_item_curr: return
            curr_row_id = int(id_item_curr.text())
            df_idx_curr = self.find_dataframe_index_by_id(curr_row_id)
            if df_idx_curr is None: return


            current_out_time_str = str(self.dataframe.at[df_idx_curr, 'OUT'])
            # current_out_ms = self.convert_time_code_to_milliseconds(current_out_time_str) # No es necesario convertir y reconvertir

            next_row_view_idx = current_row_view_idx + 1
            
            # Mapear a índice del DF para la fila siguiente
            id_item_next = self.table_widget.item(next_row_view_idx, self.COL_ID)
            if not id_item_next: return
            next_row_id = int(id_item_next.text())
            df_idx_next = self.find_dataframe_index_by_id(next_row_id)
            if df_idx_next is None: return


            self.table_widget.selectRow(next_row_view_idx) # Seleccionar en la UI
            
            old_in_next = str(self.dataframe.at[df_idx_next, 'IN'])
            if current_out_time_str != old_in_next:
                command = EditCommand(self, df_idx_next, self.COL_IN, old_in_next, current_out_time_str)
                self.undo_stack.push(command)
                self.set_unsaved_changes(True)
            
            self.table_widget.scrollToItem(self.table_widget.item(next_row_view_idx, 0), QAbstractItemView.ScrollHint.PositionAtCenter)
            # self.adjust_row_height(next_row_view_idx) # EditCommand lo hace si es necesario
        except Exception as e:
            self.handle_exception(e, "Error al seleccionar la siguiente fila y marcar IN")


    def change_scene(self) -> None:
        selected_row_view_idx = self.table_widget.currentRow()
        if selected_row_view_idx == -1:
            QMessageBox.warning(self, "Cambio de Escena", "Selecciona una intervención.")
            return
        
        self._update_dataframe_from_table()

        # Mapear a índice del DF
        id_item = self.table_widget.item(selected_row_view_idx, self.COL_ID)
        if not id_item: return
        current_row_id = int(id_item.text())
        df_idx = self.find_dataframe_index_by_id(current_row_id)
        if df_idx is None: return

        command = ChangeSceneCommand(self, df_idx) # Pasar índice del DF
        self.undo_stack.push(command)
        self.set_unsaved_changes(True)


    def validate_in_out_time(self, row_view_idx: int) -> bool:
        """Valida IN/OUT para una fila de la VISTA de tabla."""
        try:
            in_item = self.table_widget.item(row_view_idx, self.COL_IN)
            out_item = self.table_widget.item(row_view_idx, self.COL_OUT)
            if not in_item or not out_item: return True # No se puede validar

            in_time_str = in_item.text()
            out_time_str = out_item.text()

            in_ms = self.convert_time_code_to_milliseconds(in_time_str)
            out_ms = self.convert_time_code_to_milliseconds(out_time_str)
            is_valid = out_ms >= in_ms

            # Aplicar color de fondo
            # Asumimos que el tema oscuro se maneja por CSS global.
            # Aquí solo alternamos entre color normal y error.
            bg_color = VALID_TIME_BG_COLOR if is_valid else INVALID_TIME_BG_COLOR
            in_item.setBackground(bg_color)
            out_item.setBackground(bg_color)
            return is_valid
        except ValueError: # Error al convertir timecode
            if self.table_widget.item(row_view_idx, self.COL_IN): self.table_widget.item(row_view_idx, self.COL_IN).setBackground(INVALID_TIME_BG_COLOR)
            if self.table_widget.item(row_view_idx, self.COL_OUT): self.table_widget.item(row_view_idx, self.COL_OUT).setBackground(INVALID_TIME_BG_COLOR)
            return False
        except Exception as e:
            logger_tw.error(f"Error validando IN/OUT para fila (vista) {row_view_idx}: {e}")
            return True # Asumir válido en error inesperado para no bloquear


    def handle_ctrl_click(self, row_view_idx: int) -> None:
        try:
            self._update_dataframe_from_table() # Sincronizar
            # Mapear a índice del DF
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
            self._update_dataframe_from_table() # Sincronizar
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
        # El delegado se actualiza solo, obteniendo los nombres con get_character_names
        # Pero forzamos una re-creación si es necesario por alguna razón.
        # Esto podría ser excesivo. Generalmente el completer del delegate se actualiza solo.
        delegate = CharacterDelegate(get_names_callback=self.get_character_names, parent=self.table_widget)
        self.table_widget.setItemDelegateForColumn(self.COL_CHARACTER, delegate)


    def update_character_name(self, old_name: str, new_name: str) -> None:
        """Actualiza un nombre de personaje en el DataFrame y en la tabla."""
        self._update_dataframe_from_table() # Sincronizar DF
        
        # Actualizar DataFrame
        # Usar .loc para evitar SettingWithCopyWarning
        self.dataframe.loc[self.dataframe['PERSONAJE'] == old_name, 'PERSONAJE'] = new_name
        
        # Actualizar la tabla (QTableWidget)
        # Esto es redundante si populate_table() se llama después, pero puede ser útil
        # para una actualización visual inmediata sin repoblar todo.
        for row_view_idx in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row_view_idx, self.COL_CHARACTER)
            if item and item.text() == old_name:
                item.setText(new_name)
        
        self.set_unsaved_changes(True)
        self.update_character_completer() # Para actualizar sugerencias en CharacterDelegate
        self.character_name_changed.emit() # Para que CastWindow se actualice


    def find_and_replace(self, find_text: str, replace_text: str,
                         search_in_character: bool = True,
                         search_in_dialogue: bool = True) -> None:
        try:
            self._update_dataframe_from_table() # Sincronizar DF
            self.undo_stack.beginMacro("Buscar y Reemplazar")
            changed_count = 0

            for df_idx in range(len(self.dataframe)):
                if search_in_character:
                    char_text = str(self.dataframe.at[df_idx, 'PERSONAJE'])
                    if find_text.lower() in char_text.lower(): # Búsqueda insensible a mayúsculas
                        new_char_text = char_text.replace(find_text, replace_text) # Reemplazo sensible
                        if char_text != new_char_text:
                            cmd = EditCommand(self, df_idx, self.COL_CHARACTER, char_text, new_char_text)
                            self.undo_stack.push(cmd)
                            changed_count +=1
                
                if search_in_dialogue:
                    dialog_text = str(self.dataframe.at[df_idx, 'DIÁLOGO'])
                    if find_text.lower() in dialog_text.lower(): # Búsqueda insensible
                        new_dialog_text = dialog_text.replace(find_text, replace_text) # Reemplazo sensible
                        if dialog_text != new_dialog_text:
                            cmd = EditCommand(self, df_idx, self.COL_DIALOGUE, dialog_text, new_dialog_text)
                            self.undo_stack.push(cmd)
                            changed_count += 1
            
            self.undo_stack.endMacro()
            if changed_count > 0:
                self.set_unsaved_changes(True)
                # La tabla se actualizará a través de los EditCommands
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


    def renumerar_escenas(self) -> None: # Parece no usarse, revisar
        """Asigna '1' a todas las escenas si no se detectaron números de escena durante la carga."""
        # Esta lógica ahora está más integrada en GuionManager._verify_and_prepare_df
        # y el flag self.has_scene_numbers
        try:
            if not self.has_scene_numbers and not self.dataframe.empty:
                logger_tw.info("Renumerando escenas a '1' (porque has_scene_numbers es False).")
                self._update_dataframe_from_table() # Sincronizar

                self.undo_stack.beginMacro("Renumerar Escenas a 1")
                for df_idx in range(len(self.dataframe)):
                    old_scene = str(self.dataframe.at[df_idx, 'SCENE'])
                    if old_scene != "1":
                        cmd = EditCommand(self, df_idx, self.COL_SCENE, old_scene, "1")
                        self.undo_stack.push(cmd)
                self.undo_stack.endMacro()
                
                if self.undo_stack.count() > 0 and self.undo_stack.command(self.undo_stack.count()-1).text().startswith("Renumerar Escenas"):
                    self.set_unsaved_changes(True)
            else:
                logger_tw.info("No se renumeran escenas (has_scene_numbers es True o DataFrame vacío).")
        except Exception as e:
            self.undo_stack.endMacro()
            self.handle_exception(e, "Error al renumerar escenas")


    def get_next_id(self) -> int:
        """Obtiene el siguiente ID único para una nueva fila del DataFrame."""
        if not self.dataframe.empty and 'ID' in self.dataframe.columns and not self.dataframe['ID'].empty:
            # Asegurarse de que los IDs sean numéricos antes de max()
            numeric_ids = pd.to_numeric(self.dataframe['ID'], errors='coerce').dropna()
            if not numeric_ids.empty:
                return int(numeric_ids.max()) + 1
        return 0 # Si el DF está vacío, o la columna ID está vacía o no es numérica


    def find_dataframe_index_by_id(self, id_value: int) -> Optional[int]:
        """Encuentra el índice de fila en self.dataframe que corresponde a un ID dado."""
        if 'ID' not in self.dataframe.columns or self.dataframe.empty:
            return None
        # Convertir la columna ID del DataFrame a numérico para la comparación
        # ya que id_value es int.
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
                    continue # Si el texto del ID no es un número
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
                self.adjust_row_height(row) # Reajustar altura después de cambiar fuente


# ==============================================================================
# Clases de Comandos para Undo/Redo (Adaptadas para operar sobre el DataFrame)
# Y para actualizar la tabla visualmente.
# Los comandos ahora operan sobre el DataFrame usando índices del DataFrame.
# La actualización de la tabla (QTableWidget) se hace como un efecto secundario.
# ==============================================================================

class EditCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_row_index: int, column_index_in_table: int,
                 old_value: Any, new_value: Any) -> None:
        super().__init__()
        self.tw = table_window
        self.df_row_idx = df_row_index # Índice de fila en el DataFrame
        self.col_idx_table = column_index_in_table # Índice de columna en la QTableWidget
        self.old_value = old_value
        self.new_value = new_value
        
        # Para el texto del comando en el stack de undo
        col_name_in_df = self.tw.get_dataframe_column_name(self.col_idx_table)
        # Intentar obtener el ID de la fila para un mensaje más descriptivo
        row_id_for_msg = df_row_index
        if 'ID' in self.tw.dataframe.columns and df_row_index < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_row_index, 'ID']

        self.setText(f"Editar {col_name_in_df} en fila ID {row_id_for_msg}")


    def _apply_value_to_dataframe_and_table(self, value_to_apply: Any):
        df_col_name = self.tw.get_dataframe_column_name(self.col_idx_table)
        if not df_col_name: return

        # 1. Actualizar DataFrame
        # Validar tipo para SCENE antes de asignarlo al DF
        if df_col_name == 'SCENE':
            try:
                if str(value_to_apply).strip(): int(str(value_to_apply)) # Prueba de conversión
                self.tw.dataframe.at[self.df_row_idx, df_col_name] = str(value_to_apply)
            except ValueError: # Si no es un número válido, no cambiar el DF
                QMessageBox.warning(self.tw, "Error", f"Valor inválido '{value_to_apply}' para Escena.")
                # No se actualiza el DF, y la tabla tampoco debería cambiar para este valor.
                # Esto es un poco problemático para undo/redo si el valor original era válido.
                # Idealmente, la validación ocurre antes de crear el comando.
                # Por ahora, si falla la conversión, no hacemos el cambio.
                return
        elif df_col_name == 'ID':
             self.tw.dataframe.at[self.df_row_idx, df_col_name] = int(value_to_apply)
        else:
            self.tw.dataframe.at[self.df_row_idx, df_col_name] = value_to_apply

        # 2. Actualizar QTableWidget
        # Encontrar la fila en la tabla que corresponde a este df_row_idx
        # Esto asume que el DF y la tabla están sincronizados por ID y orden.
        # Es más robusto buscar por ID.
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
            
            # Validar IN/OUT si aplica
            if self.col_idx_table in [self.tw.COL_IN, self.tw.COL_OUT]:
                self.tw.validate_in_out_time(table_row_idx)
        else:
            logger_tw.error(f"EditCommand: No se encontró la fila de tabla para ID {row_id} (DF índice {self.df_row_idx})")


    def undo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.old_value)
        self.tw.set_unsaved_changes(True) # Deshacer también es un cambio

    def redo(self) -> None:
        self._apply_value_to_dataframe_and_table(self.new_value)
        self.tw.set_unsaved_changes(True)


class AddRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, view_row_to_insert_at: int):
        super().__init__()
        self.tw = table_window
        self.view_row_to_insert_at = view_row_to_insert_at # Donde insertar en la QTableWidget

        self.new_row_id = self.tw.get_next_id()
        
        # Datos por defecto para la nueva fila del DataFrame
        self.new_row_data_for_df = {
            'ID': self.new_row_id,
            'SCENE': "1", 'IN': '00:00:00:00', 'OUT': '00:00:00:00',
            'PERSONAJE': 'Nuevo Personaje', 'DIÁLOGO': 'Nuevo diálogo...'
        }
        self.df_index_where_inserted: Optional[int] = None

        # Si se inserta después de una fila existente, copiar algunos de sus datos
        # Esto se basa en la fila *anterior en el DataFrame* una vez que se determine el punto de inserción
        # Lo haremos en redo()

        self.setText(f"Agregar fila (ID {self.new_row_id})")

    def redo(self) -> None:
        # Determinar dónde insertar en el DataFrame
        # Si view_row_to_insert_at es el final de la tabla, insertar al final del DF
        # Si no, encontrar el ID de la fila en view_row_to_insert_at y buscar su índice en el DF
        
        df = self.tw.dataframe
        
        if self.view_row_to_insert_at >= self.tw.table_widget.rowCount(): # Insertar al final
            self.df_index_where_inserted = len(df)
            if not df.empty: # Copiar datos de la última fila del DF si existe
                last_df_idx = len(df) - 1
                self.new_row_data_for_df['SCENE'] = str(df.at[last_df_idx, 'SCENE'])
                self.new_row_data_for_df['PERSONAJE'] = str(df.at[last_df_idx, 'PERSONAJE'])
                # Podríamos copiar IN/OUT también si es deseable
        else: # Insertar en medio o al principio de la tabla
            # El ID de la fila de la tabla en view_row_to_insert_at
            id_item_at_view_target = self.tw.table_widget.item(self.view_row_to_insert_at, self.tw.COL_ID)
            if id_item_at_view_target:
                target_id = int(id_item_at_view_target.text())
                self.df_index_where_inserted = self.tw.find_dataframe_index_by_id(target_id)
                if self.df_index_where_inserted is None: # No debería pasar si la tabla está sincronizada
                    logger_tw.error("AddRowCommand: ID de destino en tabla no encontrado en DF. Insertando al final del DF.")
                    self.df_index_where_inserted = len(df)
                
                # Copiar datos de la fila *anterior* en el DF si existe
                if self.df_index_where_inserted > 0:
                    prev_df_idx = self.df_index_where_inserted -1
                    self.new_row_data_for_df['SCENE'] = str(df.at[prev_df_idx, 'SCENE'])
                    self.new_row_data_for_df['PERSONAJE'] = str(df.at[prev_df_idx, 'PERSONAJE'])

            else: # No hay ID en la fila de la tabla (¿fila nueva aún no en DF?) -> insertar al final del DF
                self.df_index_where_inserted = len(df)
                # (código para copiar de la última fila del DF si aplica, como arriba)


        # 1. Insertar en DataFrame
        new_df_row_series = pd.Series(self.new_row_data_for_df)
        # Dividir el df y concatenar. Esto es más seguro para inserción.
        df_part1 = df.iloc[:self.df_index_where_inserted]
        df_part2 = df.iloc[self.df_index_where_inserted:]
        self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([new_df_row_series]), df_part2], ignore_index=True)

        # 2. Insertar en QTableWidget (en la posición de vista)
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
            # 1. Eliminar del DataFrame
            self.tw.dataframe.drop(index=self.df_index_where_inserted, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True) # Re-indexar

            # 2. Eliminar de QTableWidget (de la posición de vista original)
            # Si otras operaciones han cambiado la tabla, view_row_to_insert_at podría no ser el correcto.
            # Es más seguro encontrar la fila por ID y eliminarla.
            table_row_to_remove = self.tw.find_table_row_by_id(self.new_row_id)
            if table_row_to_remove is not None:
                self.tw.table_widget.removeRow(table_row_to_remove)
            else: # Fallback si no se encuentra por ID (debería encontrarse)
                 if self.view_row_to_insert_at < self.tw.table_widget.rowCount():
                    self.tw.table_widget.removeRow(self.view_row_to_insert_at)
            
            self.df_index_where_inserted = None # Resetear para el próximo redo
            self.tw.set_unsaved_changes(True)


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_rows_indices_to_remove: List[int]):
        super().__init__()
        self.tw = table_window
        # df_rows_indices_to_remove debe ser una lista de índices del DataFrame, ordenados ascendentemente
        self.df_indices_removed = sorted(df_rows_indices_to_remove)
        self.removed_data_map: Dict[int, pd.Series] = {} # Guardar {df_idx_original: row_data}
        self.setText(f"Eliminar {len(self.df_indices_removed)} fila(s)")

    def redo(self) -> None:
        # Guardar los datos antes de eliminar del DF (ordenado desc para que los índices no cambien)
        self.removed_data_map.clear()
        df_indices_desc = sorted(self.df_indices_removed, reverse=True)

        for df_idx in df_indices_desc:
            if df_idx < len(self.tw.dataframe):
                self.removed_data_map[df_idx] = self.tw.dataframe.iloc[df_idx].copy()
                
                # Eliminar de QTableWidget primero (por ID)
                row_id_to_remove = int(self.tw.dataframe.at[df_idx, 'ID'])
                table_row_idx = self.tw.find_table_row_by_id(row_id_to_remove)
                if table_row_idx is not None:
                    self.tw.table_widget.removeRow(table_row_idx)
                
                # Luego eliminar del DataFrame
                self.tw.dataframe.drop(index=df_idx, inplace=True)
            else:
                logger_tw.warning(f"RemoveRowsCommand redo: Índice DF {df_idx} fuera de rango.")
        
        self.tw.dataframe.reset_index(drop=True, inplace=True)
        self.tw.set_unsaved_changes(True)


    def undo(self) -> None:
        # Reinsertar en orden original de los df_indices (ascendente)
        # Esto es complejo porque al reinsertar, los índices del DF cambian.
        # Es mejor reconstruir el DF si es posible, o insertar en orden de df_idx.

        # Reinsertar en el DataFrame y en la tabla
        # Iterar sobre los df_indices originales guardados (que eran ascendentes)
        for original_df_idx in self.df_indices_removed: # Estos son los índices ANTES de borrar
            row_data_series = self.removed_data_map.get(original_df_idx)
            if row_data_series is not None:
                # 1. Reinsertar en DataFrame en su posición original_df_idx
                df_part1 = self.tw.dataframe.iloc[:original_df_idx]
                df_part2 = self.tw.dataframe.iloc[original_df_idx:]
                self.tw.dataframe = pd.concat([df_part1, pd.DataFrame([row_data_series]), df_part2], ignore_index=True)

                # 2. Reinsertar en QTableWidget
                # La posición en la tabla es más complicada. Intentar insertar en original_df_idx
                # o buscar la posición correcta basada en los IDs de las filas adyacentes si es posible.
                # Por simplicidad, intentaremos insertar en la tabla en el mismo índice que en el DF.
                # Esto puede no ser perfecto si la tabla fue reordenada visualmente.
                # Mejor: repoblar la tabla desde el DF después de todas las inserciones de undo.
                # O, encontrar la fila de tabla por ID de la fila ANTERIOR en el DF e insertar después.

                # Por ahora, vamos a repoblar la tabla al final del undo si hay múltiples inserciones.
                # Si es una sola, podemos intentar ser más precisos.
                # Para este comando, después de reinsertar todas las filas en el DF,
                # es más seguro repoblar la tabla.
                pass # La repoblación se hará al final

        # Después de reinsertar todos los datos en el DF, repoblar la tabla es lo más seguro.
        self.tw.populate_table() # Esto asegura que la tabla refleje el DF
        self.tw.set_unsaved_changes(True)


class MoveRowCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_source_idx: int, df_target_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_source_idx = df_source_idx # Índice del DataFrame de la fila a mover
        self.df_target_idx = df_target_idx # Índice del DataFrame de destino
        
        # Texto del comando (mejorar con ID)
        row_id_for_msg = df_source_idx
        if 'ID' in self.tw.dataframe.columns and df_source_idx < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_source_idx, 'ID']
        self.setText(f"Mover fila ID {row_id_for_msg} de {df_source_idx} a {df_target_idx}")

    def _perform_move(self, from_df_idx: int, to_df_idx: int):
        # 1. Mover en el DataFrame
        row_to_move = self.tw.dataframe.iloc[from_df_idx].copy()
        temp_df = self.tw.dataframe.drop(index=from_df_idx).reset_index(drop=True)
        
        # Insertar la fila en la nueva posición
        part1 = temp_df.iloc[:to_df_idx]
        part2 = temp_df.iloc[to_df_idx:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([row_to_move]), part2], ignore_index=True)

        # 2. Actualizar la QTableWidget (repoblando es lo más seguro)
        self.tw.populate_table()
        
        # Intentar seleccionar la fila movida en la tabla
        moved_row_id = int(row_to_move['ID'])
        new_table_idx = self.tw.find_table_row_by_id(moved_row_id)
        if new_table_idx is not None:
            self.tw.table_widget.selectRow(new_table_idx)
        
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        # Para deshacer, el target original se convierte en source, y source original en target
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
        
        self.original_dialog = "" # Se guardará en redo la primera vez
        self.new_row_id_for_second_part = self.tw.get_next_id()
        self.second_part_data_for_df: Optional[Dict] = None

        row_id_for_msg = df_row_idx_to_split
        if 'ID' in self.tw.dataframe.columns and df_row_idx_to_split < len(self.tw.dataframe):
            row_id_for_msg = self.tw.dataframe.at[df_row_idx_to_split, 'ID']
        self.setText(f"Separar intervención en fila ID {row_id_for_msg}")


    def redo(self) -> None:
        # 1. Guardar el diálogo original de la fila que se divide (solo la primera vez que se hace redo)
        if not self.original_dialog: # Solo si no se ha guardado ya
             self.original_dialog = str(self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'])

        # 2. Modificar la fila original en el DataFrame
        self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.before_text

        # 3. Crear datos para la nueva fila (segunda parte de la intervención)
        if self.second_part_data_for_df is None: # Crear solo la primera vez
            original_row_data = self.tw.dataframe.iloc[self.df_idx_split].copy()
            self.second_part_data_for_df = original_row_data.to_dict()
            self.second_part_data_for_df['ID'] = self.new_row_id_for_second_part
            self.second_part_data_for_df['DIÁLOGO'] = self.after_text
            # Podríamos querer resetear IN/OUT para la nueva parte, o copiarlo. Por ahora, copia.

        # 4. Insertar la nueva fila en el DataFrame (justo después de la original)
        df_idx_insert_new_part_at = self.df_idx_split + 1
        new_series = pd.Series(self.second_part_data_for_df)

        part1 = self.tw.dataframe.iloc[:df_idx_insert_new_part_at]
        part2 = self.tw.dataframe.iloc[df_idx_insert_new_part_at:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([new_series]), part2], ignore_index=True)
        
        # 5. Actualizar QTableWidget (repoblando es lo más seguro)
        self.tw.populate_table()
        
        # Intentar seleccionar la primera parte de la intervención dividida
        original_part_id = int(self.tw.dataframe.at[self.df_idx_split, 'ID'])
        table_idx_original = self.tw.find_table_row_by_id(original_part_id)
        if table_idx_original is not None:
            self.tw.table_widget.selectRow(table_idx_original)

        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        # 1. Restaurar el diálogo original en la primera parte
        self.tw.dataframe.at[self.df_idx_split, 'DIÁLOGO'] = self.original_dialog
        
        # 2. Eliminar la segunda parte (la nueva fila) del DataFrame
        # Necesitamos encontrar su índice actual en el DF por su ID
        df_idx_of_second_part = self.tw.find_dataframe_index_by_id(self.new_row_id_for_second_part)
        if df_idx_of_second_part is not None:
            self.tw.dataframe.drop(index=df_idx_of_second_part, inplace=True)
            self.tw.dataframe.reset_index(drop=True, inplace=True)
        
        # 3. Actualizar QTableWidget
        self.tw.populate_table()

        # Intentar seleccionar la fila restaurada
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
        self.df_idx_second = df_idx_second_row # Este es el índice de la fila que se eliminará
        self.merged_dialog = merged_dialog
        
        self.original_dialog_first: Optional[str] = None
        self.data_of_second_row: Optional[pd.Series] = None # Para restaurar en undo

        row_id_first = df_idx_first_row
        if 'ID' in self.tw.dataframe.columns and df_idx_first_row < len(self.tw.dataframe):
            row_id_first = self.tw.dataframe.at[df_idx_first_row, 'ID']
        self.setText(f"Juntar intervenciones (ID {row_id_first} con siguiente)")

    def redo(self) -> None:
        # 1. Guardar datos originales (solo la primera vez)
        if self.original_dialog_first is None:
            self.original_dialog_first = str(self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'])
        if self.data_of_second_row is None:
            self.data_of_second_row = self.tw.dataframe.iloc[self.df_idx_second].copy()

        # 2. Actualizar diálogo de la primera fila en el DataFrame
        self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.merged_dialog
        
        # 3. Eliminar la segunda fila del DataFrame
        # El índice df_idx_second es el correcto ya que el DF aún no se ha modificado en esta operación de redo
        self.tw.dataframe.drop(index=self.df_idx_second, inplace=True)
        self.tw.dataframe.reset_index(drop=True, inplace=True)
        
        # 4. Actualizar QTableWidget
        self.tw.populate_table()

        # Seleccionar la fila fusionada
        merged_row_id = int(self.tw.dataframe.at[self.df_idx_first, 'ID']) # El índice df_idx_first sigue siendo válido para la primera fila
        table_idx_merged = self.tw.find_table_row_by_id(merged_row_id)
        if table_idx_merged is not None:
            self.tw.table_widget.selectRow(table_idx_merged)
            
        self.tw.set_unsaved_changes(True)

    def undo(self) -> None:
        if self.original_dialog_first is None or self.data_of_second_row is None:
            logger_tw.error("Merge undo: Faltan datos originales.")
            return

        # 1. Restaurar diálogo de la primera fila
        self.tw.dataframe.at[self.df_idx_first, 'DIÁLOGO'] = self.original_dialog_first
        
        # 2. Reinsertar la segunda fila en el DataFrame en su posición original (df_idx_second)
        # El df_idx_second era el índice de la segunda fila *antes* de que se borrara.
        # El df_idx_first sigue refiriéndose a la primera fila.
        # Entonces, la segunda fila debe insertarse en la posición que ocuparía después de df_idx_first.
        # Si el df_idx_second era df_idx_first + 1, entonces la inserción debe ser en df_idx_first + 1
        
        insert_at_idx_for_second_row = self.df_idx_first + 1 # Asumiendo que eran adyacentes

        part1 = self.tw.dataframe.iloc[:insert_at_idx_for_second_row]
        part2 = self.tw.dataframe.iloc[insert_at_idx_for_second_row:]
        self.tw.dataframe = pd.concat([part1, pd.DataFrame([self.data_of_second_row]), part2], ignore_index=True)
        
        # 3. Actualizar QTableWidget
        self.tw.populate_table()

        # Seleccionar la primera fila (antes de la fusión)
        first_row_id = int(self.tw.dataframe.at[self.df_idx_first, 'ID'])
        table_idx_first = self.tw.find_table_row_by_id(first_row_id)
        if table_idx_first is not None:
            self.tw.table_widget.selectRow(table_idx_first)
            
        self.tw.set_unsaved_changes(True)


class ChangeSceneCommand(QUndoCommand):
    def __init__(self, table_window: TableWindow, df_start_row_idx: int):
        super().__init__()
        self.tw = table_window
        self.df_start_idx = df_start_row_idx # Índice del DF desde donde cambiar
        
        self.old_scene_numbers_map: Dict[int, str] = {} # {df_idx: old_scene_str}
        self.new_scene_numbers_map: Dict[int, str] = {} # {df_idx: new_scene_str}

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
            else: # El DF se acortó, no se puede aplicar
                logger_tw.warning(f"ChangeScene: df_idx {df_idx} fuera de rango al aplicar cambios.")

        # Actualizar tabla (repoblar es más seguro)
        self.tw.populate_table()

        # Resaltar la primera fila afectada si es redo
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
        try: # Obtener el valor numérico de la escena de la fila de inicio
            scene_text_at_start = str(self.tw.dataframe.at[self.df_start_idx, 'SCENE'])
            if scene_text_at_start.strip():
                current_scene_val = int(scene_text_at_start)
        except (ValueError, IndexError):
            logger_tw.warning(f"ChangeScene redo: No se pudo obtener valor numérico de escena en df_idx {self.df_start_idx}. Usando 0.")
            current_scene_val = 0 # O manejar como error

        new_start_scene_val = current_scene_val + 1

        for df_idx in range(self.df_start_idx, len(self.tw.dataframe)):
            self.old_scene_numbers_map[df_idx] = str(self.tw.dataframe.at[df_idx, 'SCENE'])
            self.new_scene_numbers_map[df_idx] = str(new_start_scene_val) # Todas las siguientes tendrán este nuevo valor
            # O si la lógica es incrementar cada una:
            # old_scene_num = int(self.tw.dataframe.at[df_idx, 'SCENE'])
            # self.new_scene_numbers_map[df_idx] = str(old_scene_num + 1)
            # La lógica original de MainWindow.increment_scenes_from_row incrementaba
            # Pero el comando se llama "ChangeSceneCommand", usualmente implica un nuevo número para un bloque.
            # Voy a asumir que todas las escenas desde df_start_idx se convierten en new_start_scene_val.
            # Si es incrementar cada una, la lógica de new_start_scene_val y su uso debe cambiar.
            # Por el nombre "change_scene" en main.py, que llama a TableWindow.change_scene(),
            # y este crea ChangeSceneCommand, parece que se espera un "salto" de escena.
            # El código original de increment_scenes_from_row no se usaba.
            # Y ChangeSceneCommand en su versión anterior hacía scene + 1 para *todas* las posteriores.
            # Esto es ambiguo. Voy a seguir la lógica del comando anterior: cada escena posterior se incrementa.
            
            try:
                old_scene_num_val = int(self.old_scene_numbers_map[df_idx])
                self.new_scene_numbers_map[df_idx] = str(old_scene_num_val + 1)
            except ValueError:
                # Si la escena antigua no era un número, ¿qué hacer? Por ahora, ponerle "1"
                self.new_scene_numbers_map[df_idx] = "1"


        self._apply_scene_changes(self.new_scene_numbers_map, highlight_first=True)


    def undo(self) -> None:
        self._apply_scene_changes(self.old_scene_numbers_map, highlight_first=False)