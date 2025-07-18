# guion_editor/widgets/cast_window.py
from functools import partial
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QMessageBox, QHeaderView, QPushButton, QApplication
)
from PyQt6.QtCore import Qt, QAbstractItemModel, QSize # Added QSize
from PyQt6.QtGui import QIcon # Added QIcon for isNull check if needed

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
        # Adjusted width slightly, icon buttons are more compact
        self.setGeometry(200, 200, 500, 600) 

    def setup_ui(self):
        layout = QVBoxLayout()
        self.table_widget = self.create_table_widget()
        layout.addWidget(self.table_widget)
        self.setLayout(layout)
        self.populate_table()

    def create_table_widget(self):
        table_widget = QTableWidget()
        table_widget.setColumnCount(len(self.HEADER_LABELS))
        table_widget.setHorizontalHeaderLabels(self.HEADER_LABELS)
        
        header = table_widget.horizontalHeader()
        header.setSectionResizeMode(self.COL_PERSONAJE, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(self.COL_INTERVENCIONES, QHeaderView.ResizeMode.ResizeToContents)
        # ResizeToContents should work well with consistently sized icon buttons
        header.setSectionResizeMode(self.COL_ACCION, QHeaderView.ResizeMode.ResizeToContents) 

        header.sectionClicked.connect(self.sort_by_column)
        table_widget.verticalHeader().setVisible(False)
        table_widget.itemChanged.connect(self.on_item_changed)
        
        return table_widget

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
            print(f"CastWindow: get_icon_func is available: {callable(current_get_icon_func)}") # DEBUG
        else:
            print("CastWindow: get_icon_func is NOT available from parent_main_window.") # DEBUG


        icon_button_size = QSize(28, 28)
        icon_itself_size = QSize(16, 16)
        
        # Load the icon once if possible, for efficiency and easier debugging
        search_icon_instance = None
        if current_get_icon_func:
            try:
                print("CastWindow: Attempting to load 'find_next_icon.svg'") # DEBUG
                search_icon_instance = current_get_icon_func("find_next_icon.svg")
                if search_icon_instance.isNull():
                    print("CastWindow: 'find_next_icon.svg' loaded as QIcon, but it's NULL (icon not found or invalid).") # DEBUG
                else:
                    print(f"CastWindow: 'find_next_icon.svg' loaded. Name: {search_icon_instance.name()}, Sizes: {search_icon_instance.availableSizes()}") # DEBUG
            except Exception as e:
                print(f"CastWindow: EXCEPTION while loading 'find_next_icon.svg': {e}") # DEBUG
                search_icon_instance = None # Ensure it's None on error

        for row, (character, count) in enumerate(items_to_sort):
            self.set_table_item(row, self.COL_PERSONAJE, str(character))

            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table_widget.setItem(row, self.COL_INTERVENCIONES, count_item)

            find_button = QPushButton()
            # Use the pre-loaded search_icon_instance
            if search_icon_instance and not search_icon_instance.isNull():
                find_button.setIcon(search_icon_instance)
                find_button.setIconSize(icon_itself_size)
                find_button.setFixedSize(icon_button_size)
                # Optional: make it look more like a pure icon
                find_button.setStyleSheet("QPushButton { border: none; background-color: transparent; padding: 0px; margin: 0px; }") 
            else:
                # Fallback if icon function or specific icon is not available/loaded
                if row == 0: # Print fallback reason only once
                    print("CastWindow: Fallback - using text '...' for find button because icon was not loaded.") # DEBUG
                find_button.setText("...") # Compact fallback text
                find_button.setFixedSize(icon_button_size) # Still set fixed size for alignment

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

    # ... (on_item_changed, update_character_name_in_main_table, showEvent remain the same)
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