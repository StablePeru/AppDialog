# guion_editor/widgets/cast_window.py
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QMessageBox, QHeaderView, QPushButton, QApplication, QHBoxLayout
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QSize
from PyQt6.QtGui import QIcon

# -> NUEVO: Importar el delegado de personaje que vamos a reutilizar
from guion_editor.delegates.custom_delegates import CharacterDelegate
# -> NUEVO: Importar pandas para la lógica del autocompletador
import pandas as pd

class CastWindow(QWidget):
    HEADER_LABELS = ["Personaje", "Intervenciones", "Acción"]
    COL_PERSONAJE = 0
    COL_INTERVENCIONES = 1
    COL_ACCION = 2

    def __init__(self, pandas_table_model: QAbstractItemModel, parent_main_window=None):
        super().__init__()
        self.pandas_model = pandas_table_model
        self.parent_main_window = parent_main_window
        
        self.current_sort_column = self.COL_INTERVENCIONES
        self.current_sort_order = Qt.SortOrder.DescendingOrder
        
        self.init_window()
        self.setup_ui()
        self.pandas_model.dataChanged.connect(self.refresh_table_data)
        self.pandas_model.layoutChanged.connect(self.refresh_table_data)

    def init_window(self):
        self.setWindowTitle("Reparto Completo")
        self.setGeometry(200, 200, 500, 600) 

    def setup_ui(self):
        layout = QVBoxLayout()
        self.table_widget = self.create_table_widget()
        layout.addWidget(self.table_widget)
        
        bottom_button_layout = QHBoxLayout()
        self.uppercase_button = QPushButton(" Convertir a Mayúsculas")
        if self.parent_main_window and hasattr(self.parent_main_window, 'get_icon_func_for_dialogs'):
            get_icon = self.parent_main_window.get_icon_func_for_dialogs()
            if get_icon:
                try: # Añadir try-except por si el icono no existe
                    self.uppercase_button.setIcon(get_icon("uppercase_icon.svg"))
                    self.uppercase_button.setIconSize(QSize(16, 16))
                except: pass # Si el icono falla, no es crítico
        
        self.uppercase_button.setToolTip("Convierte todos los nombres de personaje a mayúsculas en el guion principal.")
        self.uppercase_button.clicked.connect(self.convert_all_characters_to_uppercase)

        bottom_button_layout.addStretch()
        bottom_button_layout.addWidget(self.uppercase_button)
        
        layout.addLayout(bottom_button_layout)

        self.setLayout(layout)
        self.populate_table()
        
    def convert_all_characters_to_uppercase(self):
        if not self.parent_main_window or not hasattr(self.parent_main_window, 'tableWindow'):
            QMessageBox.warning(self, "Error", "No se puede acceder a la ventana principal del guion.")
            return

        reply = QMessageBox.question(self, "Confirmar Acción",
                                     "¿Está seguro de que desea convertir todos los nombres de personaje a MAYÚSCULAS?\n\n"
                                     "Podrá deshacer esta acción con Ctrl+Z en la ventana principal.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)

        if reply == QMessageBox.StandardButton.Yes:
            self.parent_main_window.tableWindow.convert_all_characters_to_uppercase()
            QMessageBox.information(self, "Éxito", "Nombres de personaje convertidos a mayúsculas.")

    # -> NUEVO: Método para obtener la lista de nombres para el autocompletador
    def get_character_names_for_completer(self) -> list[str]:
        """Obtiene la lista de nombres de personajes únicos del modelo de datos principal."""
        dataframe = self.pandas_model.dataframe()
        if dataframe is None or dataframe.empty or 'PERSONAJE' not in dataframe.columns:
            return []
        
        # Obtenemos los nombres únicos, los convertimos a string y quitamos espacios
        unique_names = pd.Series(dataframe['PERSONAJE'].unique()).astype(str).str.strip()
        # Filtramos los que queden vacíos y devolvemos una lista ordenada
        return sorted(list(unique_names[unique_names != ""]))

    # -> MODIFICADO: create_table_widget para añadir el delegado
    def create_table_widget(self):
        table_widget = QTableWidget()
        table_widget.setColumnCount(len(self.HEADER_LABELS))
        table_widget.setHorizontalHeaderLabels(self.HEADER_LABELS)
        
        # --- Asignación del delegado ---
        # Creamos una instancia de CharacterDelegate
        char_delegate = CharacterDelegate(
            get_names_callback=self.get_character_names_for_completer,
            parent=table_widget,
            # Importante: No pasamos table_window_instance para que el delegado
            # no intente usar la pila de undo directamente. Dejamos que la señal
            # itemChanged de esta ventana se encargue de ello.
            table_window_instance=None 
        )
        # Lo asignamos a la columna de personajes (COL_PERSONAJE)
        table_widget.setItemDelegateForColumn(self.COL_PERSONAJE, char_delegate)
        # --- Fin de la asignación ---

        header = table_widget.horizontalHeader()
        header.setSectionResizeMode(self.COL_PERSONAJE, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(self.COL_INTERVENCIONES, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeMode.ResizeToContents) 

        header.sectionClicked.connect(self.sort_by_column)
        table_widget.verticalHeader().setVisible(False)
        table_widget.itemChanged.connect(self.on_item_changed)
        
        return table_widget

    # ... (el resto del archivo no necesita cambios)
    def sort_by_column(self, logical_index):
        if logical_index == self.COL_ACCION:
            return

        if self.current_sort_column == logical_index:
            self.current_sort_order = Qt.SortOrder.AscendingOrder if self.current_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        else:
            self.current_sort_column = logical_index
            self.current_sort_order = Qt.SortOrder.AscendingOrder if logical_index == self.COL_PERSONAJE else Qt.SortOrder.DescendingOrder
        
        self.populate_table()

    def refresh_table_data(self):
        self.populate_table()

    def populate_table(self):
        dataframe = self.pandas_model.dataframe()
        if dataframe is None or dataframe.empty or 'PERSONAJE' not in dataframe.columns:
            self.table_widget.setRowCount(0)
            return

        character_series = dataframe['PERSONAJE'].astype(str).str.strip()
        character_counts = character_series[character_series != ""].value_counts()
        items_to_sort = list(character_counts.items())

        if self.current_sort_column == self.COL_PERSONAJE:
            items_to_sort.sort(key=lambda item: str(item[0]).lower(),
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))
        elif self.current_sort_column == self.COL_INTERVENCIONES:
            items_to_sort.sort(key=lambda item: int(item[1]),
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))

        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(0)
        self.table_widget.setRowCount(len(items_to_sort))

        current_get_icon_func = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'get_icon_func_for_dialogs'):
            current_get_icon_func = self.parent_main_window.get_icon_func_for_dialogs()

        icon_button_size = QSize(28, 28)
        icon_itself_size = QSize(16, 16)
        
        search_icon_instance = None
        if current_get_icon_func:
            try:
                search_icon_instance = current_get_icon_func("find_next_icon.svg")
            except Exception as e:
                search_icon_instance = None 

        for row, (character, count) in enumerate(items_to_sort):
            self.set_table_item(row, self.COL_PERSONAJE, str(character))

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row, self.COL_INTERVENCIONES, count_item)

            find_button = QPushButton()
            if search_icon_instance and not search_icon_instance.isNull():
                find_button.setIcon(search_icon_instance)
                find_button.setIconSize(icon_itself_size)
                find_button.setFixedSize(icon_button_size)
                find_button.setStyleSheet("QPushButton { border: none; background-color: transparent; padding: 0px; margin: 0px; }") 
            else:
                find_button.setText("...")
                find_button.setFixedSize(icon_button_size)

            find_button.setToolTip(f"Buscar intervenciones de {character}")
            find_button.clicked.connect(partial(self.find_character_in_script, str(character)))
            self.table_widget.setCellWidget(row, self.COL_ACCION, find_button)

        self.table_widget.blockSignals(False)

        if self.current_sort_column != self.COL_ACCION:
            if self.table_widget.horizontalHeader().sortIndicatorSection() != self.current_sort_column or \
               self.table_widget.horizontalHeader().sortIndicatorOrder() != self.current_sort_order:
                self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
            self.table_widget.horizontalHeader().setSortIndicatorShown(True)
        else:
            self.table_widget.horizontalHeader().setSortIndicatorShown(False)

    def set_table_item(self, row, column, value):
        item = QTableWidgetItem(value)
        if column == self.COL_PERSONAJE:
            item.setData(Qt.ItemDataRole.UserRole, value) 
        self.table_widget.setItem(row, column, item)

    def find_character_in_script(self, character_name: str):
        from guion_editor.widgets.find_replace_dialog import FindReplaceDialog
        
        retrieved_get_icon_func = None
        if self.parent_main_window and hasattr(self.parent_main_window, 'get_icon_func_for_dialogs'):
            retrieved_get_icon_func = self.parent_main_window.get_icon_func_for_dialogs()
        elif self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow') and \
             hasattr(self.parent_main_window.tableWindow, 'get_icon'):
            retrieved_get_icon_func = self.parent_main_window.tableWindow.get_icon 

        if not self.parent_main_window or not hasattr(self.parent_main_window, 'tableWindow'):
            QMessageBox.warning(self, "Error", "No se puede acceder a la ventana principal del guion.")
            return

        dialog = FindReplaceDialog(self.parent_main_window.tableWindow, get_icon_func=retrieved_get_icon_func)
        
        if hasattr(dialog, 'set_search_parameters'):
            dialog.set_search_parameters(find_text=character_name, search_character=True, search_dialogue=False)
        else: 
            dialog.find_text_input.setText(character_name)
            dialog.search_in_character.setChecked(True)
            dialog.search_in_dialogue.setChecked(False)
            dialog.reset_search() 

        dialog.exec()

    def on_item_changed(self, item: QTableWidgetItem):
        if item.column() != self.COL_PERSONAJE:
            return

        old_name = item.data(Qt.ItemDataRole.UserRole)
        current_text_in_cell = item.text()
        new_name = current_text_in_cell.strip()

        if not new_name:
            QMessageBox.warning(self, "Entrada no válida", "El nombre del personaje no puede estar vacío.")
            self.table_widget.blockSignals(True)
            item.setText(old_name)
            self.table_widget.blockSignals(False)
            return

        if old_name == new_name:
            if current_text_in_cell != new_name:
                self.table_widget.blockSignals(True)
                item.setText(new_name)
                self.table_widget.blockSignals(False)
            return

        all_other_character_names_lower = [
            self.table_widget.item(r, self.COL_PERSONAJE).text().lower()
            for r in range(self.table_widget.rowCount())
            if r != item.row() and self.table_widget.item(r, self.COL_PERSONAJE)
        ]
        is_duplicate = new_name.lower() in all_other_character_names_lower

        if is_duplicate:
            message = (f"El nombre de personaje '{new_name}' ya existe.\n\n"
                       f"¿Desea cambiar '{old_name}' a '{new_name}'?\n\n"
                       f"Esto combinará todas las intervenciones de '{old_name}' "
                       f"con las de '{new_name}' bajo el único nombre '{new_name}'.")
            reply = QMessageBox.question(self, "Confirmar Fusión de Personajes", message,
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.No:
                self.table_widget.blockSignals(True)
                item.setText(old_name)
                self.table_widget.blockSignals(False)
                return
        
        self.update_character_name_in_main_table(old_name, new_name)
        self.populate_table()

    def update_character_name_in_main_table(self, old_name, new_name):
        if self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            self.parent_main_window.tableWindow.update_character_name(old_name, new_name)

    def showEvent(self, event):
        super().showEvent(event)
        self.populate_table() 
        if self.current_sort_column != self.COL_ACCION:
            self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
            self.table_widget.horizontalHeader().setSortIndicatorShown(True)
        else:
            self.table_widget.horizontalHeader().setSortIndicatorShown(False)