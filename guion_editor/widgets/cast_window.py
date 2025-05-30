# guion_editor/widgets/cast_window.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
from PyQt6.QtCore import Qt, QAbstractItemModel
import pandas as pd

class CastWindow(QWidget):
    HEADER_LABELS = ["Personaje", "Intervenciones"]
    COL_PERSONAJE = 0
    COL_INTERVENCIONES = 1

    def __init__(self, pandas_table_model: QAbstractItemModel, parent_main_window=None): # Changed parameter
        super().__init__()
        self.pandas_model = pandas_table_model # Store the model
        self.parent_main_window = parent_main_window # For updating character names globally if needed
        
        self.current_sort_column = self.COL_INTERVENCIONES
        self.current_sort_order = Qt.SortOrder.DescendingOrder
        
        self.init_window()
        self.setup_ui()
        # Connect to model signals if needed for live updates, or refresh on showEvent
        self.pandas_model.dataChanged.connect(self.refresh_table_data)
        self.pandas_model.layoutChanged.connect(self.refresh_table_data)


    def init_window(self):
        self.setWindowTitle("Reparto Completo")
        self.setGeometry(200, 200, 400, 600)

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
        table_widget.horizontalHeader().setStretchLastSection(True)
        table_widget.horizontalHeader().setSectionResizeMode(self.COL_PERSONAJE, QHeaderView.ResizeMode.Stretch) # Stretch Personaje
        table_widget.horizontalHeader().setSectionResizeMode(self.COL_INTERVENCIONES, QHeaderView.ResizeMode.ResizeToContents) # Resize Intervenciones
        table_widget.itemChanged.connect(self.on_item_changed)
        table_widget.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        table_widget.setSortingEnabled(False) 
        return table_widget

    def sort_by_column(self, logical_index):
        if self.current_sort_column == logical_index:
            self.current_sort_order = Qt.SortOrder.AscendingOrder if self.current_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        else:
            self.current_sort_column = logical_index
            self.current_sort_order = Qt.SortOrder.AscendingOrder if logical_index == self.COL_PERSONAJE else Qt.SortOrder.DescendingOrder
        self.populate_table()

    def refresh_table_data(self):
        # This is a slot connected to model's dataChanged or layoutChanged
        self.populate_table()

    def populate_table(self):
        dataframe = self.pandas_model.dataframe() # Get current dataframe from model
        if dataframe is None or dataframe.empty or 'PERSONAJE' not in dataframe.columns:
             self.table_widget.setRowCount(0)
             return

        # Ensure 'PERSONAJE' column is treated as string for value_counts and filtering
        character_series = dataframe['PERSONAJE'].astype(str).str.strip()
        # Filter out empty strings after stripping, before value_counts
        character_counts = character_series[character_series != ""].value_counts()
        items_to_sort = list(character_counts.items())

        if self.current_sort_column == self.COL_PERSONAJE:
            items_to_sort.sort(key=lambda item: str(item[0]).lower(), 
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))
        elif self.current_sort_column == self.COL_INTERVENCIONES:
            items_to_sort.sort(key=lambda item: item[1], 
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))

        self.table_widget.setRowCount(0) # Clear before populating
        self.table_widget.setRowCount(len(items_to_sort))
        self.table_widget.blockSignals(True)
        for row, (character, count) in enumerate(items_to_sort):
            self.set_table_item(row, self.COL_PERSONAJE, str(character))
            self.set_table_item(row, self.COL_INTERVENCIONES, str(count))
        self.table_widget.blockSignals(False)

        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)

    def set_table_item(self, row, column, value):
        item = QTableWidgetItem(value)
        if column == self.COL_PERSONAJE:
            item.setData(Qt.ItemDataRole.UserRole, value) # Store original name for editing
        elif column == self.COL_INTERVENCIONES:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table_widget.setItem(row, column, item)

    def on_item_changed(self, item: QTableWidgetItem):
        if item.column() == self.COL_PERSONAJE:
            old_name = item.data(Qt.ItemDataRole.UserRole)
            new_name = item.text().strip()
            
            if not new_name: # Empty new name
                QMessageBox.warning(self, "Entrada no válida", "El nombre del personaje no puede estar vacío.")
                self.table_widget.blockSignals(True); item.setText(old_name); self.table_widget.blockSignals(False)
                return
            
            if old_name and old_name != new_name:
                # Check for duplicates (case-insensitive) among other rows
                all_other_character_names = [
                    self.table_widget.item(r, self.COL_PERSONAJE).text().lower()
                    for r in range(self.table_widget.rowCount())
                    if r != item.row() and self.table_widget.item(r, self.COL_PERSONAJE) # Ensure item exists
                ]
                if new_name.lower() in all_other_character_names:
                    QMessageBox.warning(self, "Nombre Duplicado", f"El nombre '{new_name}' ya existe. Use un nombre diferente.")
                    self.table_widget.blockSignals(True); item.setText(old_name); self.table_widget.blockSignals(False)
                    return

                self.update_character_name_in_main_table(old_name, new_name)
                item.setData(Qt.ItemDataRole.UserRole, new_name) # Update stored original name
                # No need for QMessageBox here, change is reflected in main table's undo stack
            elif not old_name and new_name: # Should not happen if populated correctly
                 item.setData(Qt.ItemDataRole.UserRole, new_name)


    def update_character_name_in_main_table(self, old_name, new_name):
        # Communicate back to TableWindow (via MainWindow or directly if reference is kept)
        # to update names in the main table's model using its undo stack.
        if self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            self.parent_main_window.tableWindow.update_character_name(old_name, new_name)
        # If TableWindow's update_character_name emits character_name_changed,
        # this CastWindow will get notified via self.refresh_table_data if connected.

    def showEvent(self, event):
        super().showEvent(event)
        self.populate_table() # Refresh data when window is shown