# guion_editor/widgets/cast_window.py
from functools import partial
import pandas as pd
import re  # Importamos regex para la limpieza profunda

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox,
    QHeaderView, QPushButton, QHBoxLayout, QInputDialog, QAbstractItemView,
    QLineEdit, QFileDialog, QMenu, QLabel, QStyleOptionViewItem
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QSize, QSettings
from PyQt6.QtGui import QIcon, QColor, QAction, QFont

from guion_editor.delegates.custom_delegates import CharacterDelegate, RepartoDelegate
from guion_editor.widgets.split_character_dialog import SplitCharacterDialog
from .. import constants as C

# --- DELEGADOS LOCALES (Mantenemos esto para evitar elide visual) ---
class CastCharacterDelegate(CharacterDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = Qt.TextElideMode.ElideNone
        super().paint(painter, opt, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width() + 25, size.height())

class CastRepartoDelegate(RepartoDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.textElideMode = Qt.TextElideMode.ElideNone
        super().paint(painter, opt, index)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width() + 25, size.height())
# ------------------------------------------------------------

class CastWindow(QWidget):
    # Definimos los índices de las columnas de esta tabla específica
    COL_ID = 0
    COL_PERSONAJE = 1
    COL_REPARTO = 2
    COL_INTERVENCIONES = 3
    HEADER_LABELS = ["ID", "Personaje", "Reparto", "Intervenciones"]

    def __init__(self, pandas_table_model: QAbstractItemModel, parent_main_window=None, parent=None):
        super().__init__(parent)
        self.pandas_model = pandas_table_model
        self.parent_main_window = parent_main_window
        self.reparto_data = {}
        
        self.current_sort_column = self.COL_INTERVENCIONES
        self.current_sort_order = Qt.SortOrder.DescendingOrder
        
        self._first_show = True
        self._settings_loaded = False

        self.init_window()
        self.setup_ui()
        
        self.pandas_model.dataChanged.connect(self.refresh_table_data)
        self.pandas_model.layoutChanged.connect(self.refresh_table_data)
        self.pandas_model.modelReset.connect(self.refresh_table_data)
        self.table_widget.itemSelectionChanged.connect(self.update_button_states)
        
        # Cargar configuración guardada al iniciar
        self._load_settings()

    def init_window(self):
        self.setWindowTitle("Reparto Completo")
        self.setGeometry(200, 200, 1000, 600) 
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Tool)

    # --- NUEVA FUNCIÓN DE LIMPIEZA DE DATOS ---
    def clean_text_data(self, text):
        """
        Limpia saltos de línea, tabulaciones y espacios múltiples que vienen de PDFs.
        Convierte 'NOMBRE\nAPELLIDO' en 'NOMBRE APELLIDO'.
        """
        if not isinstance(text, str):
            text = str(text)
        if not text:
            return ""
        
        # 1. Reemplazar saltos de línea y tabs por espacio
        text = text.replace('\n', ' ').replace('\r', '').replace('\t', ' ')
        
        # 2. Eliminar espacios múltiples (ej: "  ") y espacios al inicio/final
        # " ".join(text.split()) es la forma más rápida y segura en Python para esto
        return " ".join(text.split())

    def on_item_changed(self, item: QTableWidgetItem):
        row, col = item.row(), item.column()
        character_item = self.table_widget.item(row, self.COL_PERSONAJE)
        if not character_item: return

        original_char_name = character_item.data(Qt.ItemDataRole.UserRole)
        # Usamos la función de limpieza también aquí al editar
        new_value = self.clean_text_data(item.text())

        if col == self.COL_PERSONAJE:
            if not new_value:
                QMessageBox.warning(self, "Nombre no válido", "El nombre del personaje no puede estar vacío.")
                self.table_widget.blockSignals(True)
                item.setText(original_char_name)
                self.table_widget.blockSignals(False)
                return

            if new_value != original_char_name:
                try:
                    self.pandas_model.layoutChanged.disconnect(self.refresh_table_data)
                    self.parent_main_window.tableWindow.update_multiple_character_names([original_char_name], new_value)
                    if original_char_name in self.reparto_data:
                        self.reparto_data[new_value] = self.reparto_data.pop(original_char_name)
                finally:
                    self.pandas_model.layoutChanged.connect(self.refresh_table_data)
                self.refresh_table_data()

        elif col == self.COL_REPARTO:
            if self.reparto_data.get(original_char_name) != new_value:
                self.reparto_data[original_char_name] = new_value
                item.setData(Qt.ItemDataRole.UserRole, new_value)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filtrar:"))
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Buscar personaje...")
        self.filter_edit.textChanged.connect(self.populate_table)
        filter_layout.addWidget(self.filter_edit)
        layout.addLayout(filter_layout)
        self.table_widget = self.create_table_widget()
        layout.addWidget(self.table_widget)
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(5, 5, 5, 5)
        self.char_count_label = QLabel("Personajes: 0")
        self.intervention_count_label = QLabel("Intervenciones Totales: 0")
        stats_layout.addStretch()
        stats_layout.addWidget(self.char_count_label)
        stats_layout.addSpacing(20)
        stats_layout.addWidget(self.intervention_count_label)
        layout.addLayout(stats_layout)
        bottom_button_layout = QHBoxLayout()
        icon_size = QSize(16, 16)
        get_icon = self.parent_main_window.get_icon_func_for_dialogs() if self.parent_main_window and hasattr(self.parent_main_window, 'get_icon_func_for_dialogs') else None
        self.split_button = QPushButton(" Separar Personaje")
        if get_icon: self.split_button.setIcon(get_icon("split_intervention_icon.svg")); self.split_button.setIconSize(icon_size)
        self.split_button.setToolTip("Separa un personaje compuesto (ej. 'KIMA / AMIK') en dos entradas.")
        self.split_button.clicked.connect(self.split_selected_character)
        self.split_button.setEnabled(False)
        self.merge_button = QPushButton(" Unificar Personajes")
        if get_icon: self.merge_button.setIcon(get_icon("merge_intervention_icon.svg")); self.merge_button.setIconSize(icon_size)
        self.merge_button.setToolTip("Unifica los personajes seleccionados bajo un único nombre.")
        self.merge_button.clicked.connect(self.merge_selected_characters)
        self.merge_button.setEnabled(False)
        self.trim_spaces_button = QPushButton(" Limpiar Nombres")
        if get_icon: self.trim_spaces_button.setIcon(get_icon("adjust_dialogs_icon.svg")); self.trim_spaces_button.setIconSize(icon_size)
        self.trim_spaces_button.setToolTip("Elimina espacios en blanco al inicio y final de TODOS los nombres de personaje.")
        self.trim_spaces_button.clicked.connect(self.trim_all_character_names_in_script)
        self.uppercase_button = QPushButton(" Convertir a Mayúsculas")
        if get_icon: self.uppercase_button.setIcon(get_icon("uppercase_icon.svg")); self.uppercase_button.setIconSize(icon_size)
        self.uppercase_button.setToolTip("Convierte todos los nombres de personaje a mayúsculas.")
        self.uppercase_button.clicked.connect(self.convert_all_characters_to_uppercase)
        self.delete_button = QPushButton(" Eliminar Personaje")
        if get_icon: self.delete_button.setIcon(get_icon("delete_row_icon.svg")); self.delete_button.setIconSize(icon_size)
        self.delete_button.setToolTip("Elimina TODAS las intervenciones del personaje seleccionado.")
        self.delete_button.clicked.connect(self.delete_selected_character)
        self.delete_button.setEnabled(False)
        self.import_button = QPushButton(" Importar Reparto")
        if get_icon: self.import_button.setIcon(get_icon("import_excel_icon.svg")); self.import_button.setIconSize(icon_size)
        self.import_button.setToolTip("Importa una lista de Personaje/Reparto desde un archivo Excel.")
        self.import_button.clicked.connect(self.import_reparto)
        self.export_button = QPushButton(" Exportar Reparto")
        if get_icon: self.export_button.setIcon(get_icon("export_excel_icon.svg")); self.export_button.setIconSize(icon_size)
        self.export_button.setToolTip("Exporta la lista de Personaje/Reparto a un archivo Excel.")
        self.export_button.clicked.connect(self.export_reparto)
        bottom_button_layout.addWidget(self.split_button)
        bottom_button_layout.addWidget(self.merge_button)
        bottom_button_layout.addWidget(self.delete_button)
        bottom_button_layout.addStretch()
        bottom_button_layout.addWidget(self.import_button)
        bottom_button_layout.addWidget(self.export_button)
        bottom_button_layout.addWidget(self.trim_spaces_button)
        bottom_button_layout.addWidget(self.uppercase_button)
        layout.addLayout(bottom_button_layout)
        self.setLayout(layout)
        self.populate_table()

    def create_table_widget(self):
        table = QTableWidget()
        table.setColumnCount(len(self.HEADER_LABELS))
        table.setHorizontalHeaderLabels(self.HEADER_LABELS)
        
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setWordWrap(False)

        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        char_delegate = CastCharacterDelegate(get_names_callback=self.get_character_names_for_completer, parent=table)
        table.setItemDelegateForColumn(self.COL_PERSONAJE, char_delegate)
        
        reparto_delegate = CastRepartoDelegate(get_names_callback=self.get_reparto_names_for_completer, parent=table)
        table.setItemDelegateForColumn(self.COL_REPARTO, reparto_delegate)

        header = table.horizontalHeader()
        header.setSectionsMovable(True)
        
        header.setSectionResizeMode(self.COL_ID, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_PERSONAJE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_REPARTO, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(self.COL_INTERVENCIONES, QHeaderView.ResizeMode.Interactive)

        header.setSortIndicatorShown(True)
        
        header.sectionClicked.connect(self.sort_by_column)
        table.verticalHeader().setVisible(False)
        table.itemChanged.connect(self.on_item_changed)
        
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show_context_menu)
        
        table.cellClicked.connect(self.handle_cell_click)
        
        return table

    # --- LÓGICA DE PERSISTENCIA Y DISTRIBUCIÓN ---
    def _distribute_columns_initially(self):
        """Distribuye las columnas para ocupar todo el ancho disponible."""
        if not self.isVisible(): return
        
        total_width = self.table_widget.viewport().width()
        if total_width <= 0: return
        
        # Anchos fijos para ID e Intervenciones
        id_width = 50
        count_width = 100
        
        # Calcular espacio restante
        remaining_width = total_width - id_width - count_width - 20 # Margen seguridad scrollbar
        
        if remaining_width > 100:
            # Repartir 50/50
            char_width = int(remaining_width * 0.5)
            reparto_width = int(remaining_width * 0.5)
        else:
            char_width = 300
            reparto_width = 300

        self.table_widget.setColumnWidth(self.COL_ID, id_width)
        self.table_widget.setColumnWidth(self.COL_INTERVENCIONES, count_width)
        self.table_widget.setColumnWidth(self.COL_PERSONAJE, char_width)
        self.table_widget.setColumnWidth(self.COL_REPARTO, reparto_width)

    def showEvent(self, event):
        super().showEvent(event)
        if self._first_show:
            if not self._settings_loaded:
                self._distribute_columns_initially()
            self._first_show = False

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    def _save_settings(self):
        settings = QSettings("TuEmpresa", "EditorDeGuion")
        settings.setValue("cast_window_geometry", self.saveGeometry())
        settings.setValue("cast_table_header_state", self.table_widget.horizontalHeader().saveState())

    def _load_settings(self):
        settings = QSettings("TuEmpresa", "EditorDeGuion")
        geometry = settings.value("cast_window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        
        header_state = settings.value("cast_table_header_state")
        if header_state:
            self.table_widget.horizontalHeader().restoreState(header_state)
            self._settings_loaded = True
        else:
            self._settings_loaded = False
    # --- FIN LÓGICA PERSISTENCIA ---

    def get_character_names_for_completer(self) -> list[str]:
        df = self.pandas_model.dataframe()
        if df is None or df.empty or C.COL_PERSONAJE not in df.columns: return []
        unique_names = pd.Series(df[C.COL_PERSONAJE].unique()).astype(str).str.strip()
        return sorted(list(unique_names[unique_names != ""]))

    def sort_by_column(self, logical_index):
        if self.current_sort_column == logical_index:
            self.current_sort_order = Qt.SortOrder.AscendingOrder if self.current_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        else:
            self.current_sort_column = logical_index
            self.current_sort_order = Qt.SortOrder.DescendingOrder if logical_index == self.COL_INTERVENCIONES else Qt.SortOrder.AscendingOrder
        
        self.populate_table()

    def refresh_table_data(self):
        self.populate_table()
        if self.isVisible():
            self.activateWindow()
            self.raise_()

    def populate_table(self):
        df = self.pandas_model.dataframe()
        if df is None or df.empty or C.COL_PERSONAJE not in df.columns:
            self.table_widget.setRowCount(0)
            return
            
        # --- LIMPIEZA PREVIA DE DATOS EN MEMORIA DEL DATAFRAME ---
        # Esto no modifica el guion original permanentemente, solo la vista de estadísticas
        # Sin embargo, si usamos la función de limpieza global, mejoramos la calidad.
        # Pero para esta vista, limpiaremos al vuelo:
        char_series = df[C.COL_PERSONAJE].astype(str).apply(self.clean_text_data)
        char_counts = char_series.value_counts()
        char_counts = char_counts[char_counts.index != ""]
        
        items_to_sort = [{'personaje': char, 'reparto': self.reparto_data.get(char, ""), 'count': count} for char, count in char_counts.items()]
        
        if hasattr(self, 'filter_edit'):
            filter_text = self.filter_edit.text().lower().strip()
            if filter_text:
                items_to_sort = [item for item in items_to_sort if filter_text in item['personaje'].lower()]
        
        if self.current_sort_column == self.COL_PERSONAJE:
            sort_reverse = (self.current_sort_order == Qt.SortOrder.DescendingOrder)
            items_to_sort.sort(key=lambda x: x['personaje'].lower(), reverse=sort_reverse)
        elif self.current_sort_column == self.COL_INTERVENCIONES:
            if self.current_sort_order == Qt.SortOrder.DescendingOrder:
                items_to_sort.sort(key=lambda x: (-x['count'], x['personaje'].lower()))
            else:
                items_to_sort.sort(key=lambda x: (x['count'], x['personaje'].lower()))
        elif self.current_sort_column == self.COL_REPARTO:
             sort_reverse = (self.current_sort_order == Qt.SortOrder.DescendingOrder)
             items_to_sort.sort(key=lambda x: (x['reparto'].lower(), x['personaje'].lower()), reverse=sort_reverse)
        
        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)

        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(len(items_to_sort))
        total_interventions_in_view = 0
        for row_idx, item_data in enumerate(items_to_sort):
            id_item = QTableWidgetItem(str(row_idx + 1)); id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row_idx, self.COL_ID, id_item)
            
            # Aplicamos el nombre limpio
            clean_name = str(item_data['personaje'])
            char_item = self.set_table_item(row_idx, self.COL_PERSONAJE, clean_name)
            # Tooltip para ver si hay basura oculta (debug para el usuario)
            char_item.setToolTip(f"'{clean_name}'")

            reparto_value = str(item_data['reparto'])
            reparto_item = self.set_table_item(row_idx, self.COL_REPARTO, reparto_value)
            if not reparto_value:
                reparto_item.setBackground(QColor(60, 30, 30, 180))
            
            count_item = QTableWidgetItem()
            count_item.setData(Qt.ItemDataRole.DisplayRole, str(item_data['count']))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            font = count_item.font()
            font.setUnderline(True)
            count_item.setFont(font)
            count_item.setForeground(QColor("#80aaff"))
            count_item.setToolTip(f"Hacer clic para buscar las {item_data['count']} intervenciones de {item_data['personaje']}")
            self.table_widget.setItem(row_idx, self.COL_INTERVENCIONES, count_item)
            total_interventions_in_view += item_data['count']

        self.table_widget.blockSignals(False)
        
        if hasattr(self, 'char_count_label'):
            self.char_count_label.setText(f"Personajes Mostrados: {len(items_to_sort)}")
            self.intervention_count_label.setText(f"Suma de Intervenciones: {total_interventions_in_view}")

    def set_table_item(self, row, column, value):
        item = QTableWidgetItem(value)
        item.setData(Qt.ItemDataRole.UserRole, value)
        self.table_widget.setItem(row, column, item)
        return item

    def find_character_in_script(self, character_name: str):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        if self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            get_icon = self.parent_main_window.get_icon_func_for_dialogs()
            dialog = FindReplaceDialog(self.parent_main_window.tableWindow, get_icon_func=get_icon)
            dialog.set_search_parameters(find_text=character_name, search_character=True, search_dialogue=False)
            dialog.exec()

    def export_reparto(self):
        if self.table_widget.rowCount() == 0:
            QMessageBox.information(self, "Exportar", "No hay datos para exportar.")
            return
        reparto_data = [{C.COL_PERSONAJE: self.table_widget.item(row, self.COL_PERSONAJE).text(),
                         C.COL_REPARTO: self.table_widget.item(row, self.COL_REPARTO).text()}
                        for row in range(self.table_widget.rowCount())]
        reparto_df = pd.DataFrame(reparto_data)
        filename = "Reparto.xlsx"
        try:
            tw = self.parent_main_window.tableWindow
            filename = tw._generate_default_filename("xlsx").replace(".xlsx", "")
            filename = f"Reparto_{filename}.xlsx"
        except Exception: pass
        path, _ = QFileDialog.getSaveFileName(self, "Exportar Reparto", filename, "Archivos Excel (*.xlsx)")
        if path:
            try:
                reparto_df.to_excel(path, index=False)
                QMessageBox.information(self, "Éxito", f"Reparto exportado a:\n{path}")
            except Exception as e:
                QMessageBox.critical(self, "Error de Exportación", f"No se pudo guardar el archivo:\n{e}")

    def show_context_menu(self, position):
        menu = QMenu(self)
        selected_rows = self.table_widget.selectionModel().selectedRows()
        num_selected = len(selected_rows)
        if num_selected == 1:
            row_index = selected_rows[0].row()
            char_name = self.table_widget.item(row_index, self.COL_PERSONAJE).text()
            find_action = menu.addAction(f"Buscar intervenciones de '{char_name}'")
            find_action.triggered.connect(lambda: self.find_character_in_script(char_name))
            menu.addSeparator()
            split_action = menu.addAction("Separar Personaje...")
            split_action.triggered.connect(self.split_selected_character)
            delete_action = menu.addAction("Eliminar Personaje del Guion...")
            delete_action.triggered.connect(self.delete_selected_character)
        elif num_selected > 1:
            merge_action = menu.addAction(f"Unificar {num_selected} Personajes...")
            merge_action.triggered.connect(self.merge_selected_characters)
        if num_selected > 0:
            menu.exec(self.table_widget.mapToGlobal(position))

    def handle_cell_click(self, row, column):
        if column == self.COL_INTERVENCIONES:
            char_name_item = self.table_widget.item(row, self.COL_PERSONAJE)
            if char_name_item:
                self.find_character_in_script(char_name_item.text())

    def update_button_states(self):
        num_selected = len(self.table_widget.selectionModel().selectedRows())
        self.split_button.setEnabled(num_selected == 1)
        self.merge_button.setEnabled(num_selected > 1)
        self.delete_button.setEnabled(num_selected == 1)

    def trim_all_character_names_in_script(self):
        if not self.parent_main_window or not hasattr(self.parent_main_window, 'tableWindow'): return
        reply = QMessageBox.question(self, "Confirmar Acción",
                                     "¿Eliminar espacios sobrantes de TODOS los nombres de personaje?\n(Reversible con Ctrl+Z)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_main_window.tableWindow.trim_all_character_names()

    def split_selected_character(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if len(selected_rows) != 1: return
        original_name = self.table_widget.item(selected_rows[0].row(), self.COL_PERSONAJE).text()
        dialog = SplitCharacterDialog(original_name, self)
        if dialog.exec():
            names = dialog.get_names()
            if names and self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
                name1, name2 = names
                reply = QMessageBox.question(self, "Confirmar Separación",
                                             f"¿Reemplazar todas las intervenciones de '{original_name}' por dos intervenciones para '{name1}' y '{name2}'?\n(Reversible con Ctrl+Z)",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
                if reply == QMessageBox.StandardButton.Yes:
                    self.parent_main_window.tableWindow.split_character_rows(original_name, name1, name2)

    def merge_selected_characters(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if len(selected_rows) < 2: return
        old_names = [self.table_widget.item(row.row(), self.COL_PERSONAJE).text() for row in selected_rows]
        new_name, ok = QInputDialog.getText(self, "Unificar Personajes", "Nombre final para los personajes:", QLineEdit.EchoMode.Normal, max(old_names, key=len))
        if ok and new_name.strip() and self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            final_name = new_name.strip()
            reply = QMessageBox.question(self, "Confirmar Unificación",
                                         f"¿Renombrar los personajes seleccionados a '{final_name}'?\n(Reversible con Ctrl+Z)",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.parent_main_window.tableWindow.update_multiple_character_names(old_names, final_name)

    def convert_all_characters_to_uppercase(self):
        if not self.parent_main_window or not hasattr(self.parent_main_window, 'tableWindow'): return
        reply = QMessageBox.question(self, "Confirmar Acción",
                                     "¿Convertir todos los nombres de personaje a MAYÚSCULAS?\n(Reversible con Ctrl+Z)",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            self.parent_main_window.tableWindow.convert_all_characters_to_uppercase()

    def get_reparto_names_for_completer(self) -> list[str]:
        if not self.reparto_data: return []
        unique_actors = sorted(list(set(actor for actor in self.reparto_data.values() if actor and str(actor).strip())))
        return unique_actors

    def delete_selected_character(self):
        selected_rows = self.table_widget.selectionModel().selectedRows()
        if len(selected_rows) != 1: return
        character_name = self.table_widget.item(selected_rows[0].row(), self.COL_PERSONAJE).text()
        if self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            self.parent_main_window.tableWindow.delete_all_interventions_by_character(character_name)
            self.refresh_table_data()

    def import_reparto(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar Reparto", "", "Archivos Excel (*.xlsx)")
        if not path: return
        try:
            df = pd.read_excel(path)
            if C.COL_PERSONAJE not in df.columns or C.COL_REPARTO not in df.columns:
                QMessageBox.warning(self, "Error de Formato", f"El archivo Excel debe contener las columnas '{C.COL_PERSONAJE}' y '{C.COL_REPARTO}'.")
                return
            df[C.COL_REPARTO] = df[C.COL_REPARTO].fillna('').astype(str)
            imported_data = pd.Series(df[C.COL_REPARTO].values, index=df[C.COL_PERSONAJE]).to_dict()
            self.reparto_data.update(imported_data)
            self.populate_table()
            QMessageBox.information(self, "Éxito", "Datos de reparto importados y fusionados correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error de Importación", f"No se pudo leer el archivo:\n{e}")