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
        self.setGeometry(200, 200, 400, 600) # Puedes ajustar el tamaño si es necesario

    def setup_ui(self):
        layout = QVBoxLayout()
        self.table_widget = self.create_table_widget()
        layout.addWidget(self.table_widget)
        self.setLayout(layout)
        self.populate_table() # Llamar después de que table_widget esté completamente configurado

    def create_table_widget(self):
        table_widget = QTableWidget()
        table_widget.setColumnCount(len(self.HEADER_LABELS))
        table_widget.setHorizontalHeaderLabels(self.HEADER_LABELS)
        
        # Configuración de la cabecera horizontal
        header = table_widget.horizontalHeader()
        header.setStretchLastSection(True) # Para que la última columna (Intervenciones) se estire
        header.setSectionResizeMode(self.COL_PERSONAJE, QHeaderView.ResizeMode.Stretch) 
        header.setSectionResizeMode(self.COL_INTERVENCIONES, QHeaderView.ResizeMode.ResizeToContents) # Que se ajuste al contenido
        header.sectionClicked.connect(self.sort_by_column)
        # No es necesario table_widget.setSortingEnabled(False) si manejas el sort manualmente

        # CAMBIO: Ocultar la cabecera vertical
        table_widget.verticalHeader().setVisible(False)

        table_widget.itemChanged.connect(self.on_item_changed)
        # table_widget.setAlternatingRowColors(True) # El estilo ya lo maneja QTableWidget en main.css
        
        return table_widget

    def sort_by_column(self, logical_index):
        if self.current_sort_column == logical_index:
            self.current_sort_order = Qt.SortOrder.AscendingOrder if self.current_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder
        else:
            self.current_sort_column = logical_index
            # Por defecto, Personaje ascendente, Intervenciones descendente
            self.current_sort_order = Qt.SortOrder.AscendingOrder if logical_index == self.COL_PERSONAJE else Qt.SortOrder.DescendingOrder
        
        self.populate_table()
        # Actualizar indicador de ordenación en la cabecera
        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)


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
            # Para números, convertir a int para la ordenación
            items_to_sort.sort(key=lambda item: int(item[1]), 
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))

        self.table_widget.blockSignals(True) # Bloquear señales mientras se repuebla
        self.table_widget.setRowCount(0) 
        self.table_widget.setRowCount(len(items_to_sort))
        
        for row, (character, count) in enumerate(items_to_sort):
            self.set_table_item(row, self.COL_PERSONAJE, str(character))
            # Asegurarse que el conteo se establece como string pero se alinea como número
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # Centrar conteo
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable) # No editable
            self.table_widget.setItem(row, self.COL_INTERVENCIONES, count_item)
            
        self.table_widget.blockSignals(False) # Restaurar señales

        # El indicador de ordenación se actualiza en sort_by_column
        # self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        # self.table_widget.horizontalHeader().setSortIndicatorShown(True)


    def set_table_item(self, row, column, value):
        item = QTableWidgetItem(value)
        if column == self.COL_PERSONAJE:
            item.setData(Qt.ItemDataRole.UserRole, value) 
        # La configuración de COL_INTERVENCIONES se hace directamente en populate_table
        self.table_widget.setItem(row, column, item)

    def on_item_changed(self, item: QTableWidgetItem):
        if item.column() == self.COL_PERSONAJE:
            old_name = item.data(Qt.ItemDataRole.UserRole)
            new_name = item.text().strip()
            
            if not new_name: 
                QMessageBox.warning(self, "Entrada no válida", "El nombre del personaje no puede estar vacío.")
                self.table_widget.blockSignals(True); item.setText(old_name); self.table_widget.blockSignals(False)
                return
            
            if old_name and old_name != new_name:
                all_other_character_names = [
                    self.table_widget.item(r, self.COL_PERSONAJE).text().lower()
                    for r in range(self.table_widget.rowCount())
                    if r != item.row() and self.table_widget.item(r, self.COL_PERSONAJE) 
                ]
                if new_name.lower() in all_other_character_names:
                    QMessageBox.warning(self, "Nombre Duplicado", f"El nombre '{new_name}' ya existe. Use un nombre diferente.")
                    self.table_widget.blockSignals(True); item.setText(old_name); self.table_widget.blockSignals(False)
                    return

                self.update_character_name_in_main_table(old_name, new_name)
                item.setData(Qt.ItemDataRole.UserRole, new_name) 
            elif not old_name and new_name: 
                 item.setData(Qt.ItemDataRole.UserRole, new_name)


    def update_character_name_in_main_table(self, old_name, new_name):
        if self.parent_main_window and hasattr(self.parent_main_window, 'tableWindow'):
            self.parent_main_window.tableWindow.update_character_name(old_name, new_name)

    def showEvent(self, event):
        super().showEvent(event)
        self.populate_table() 
        # Asegurar que el indicador de ordenación se muestre correctamente al mostrar la ventana
        self.table_widget.horizontalHeader().setSortIndicator(self.current_sort_column, self.current_sort_order)
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)