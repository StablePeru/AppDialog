from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QMessageBox 
from PyQt6.QtCore import Qt 

class CastWindow(QWidget):
    HEADER_LABELS = ["Personaje", "Intervenciones"]
    COL_PERSONAJE = 0
    COL_INTERVENCIONES = 1

    def __init__(self, parent_table_window):
        super().__init__()
        self.parent_table_window = parent_table_window
        
        self.current_sort_column = self.COL_INTERVENCIONES
        self.current_sort_order = Qt.SortOrder.DescendingOrder # CAMBIO
        
        self.init_window()
        self.setup_ui()

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
        table_widget.itemChanged.connect(self.on_item_changed)
        table_widget.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        table_widget.setSortingEnabled(False) 
        return table_widget

    def sort_by_column(self, logical_index):
        if self.current_sort_column == logical_index:
            self.current_sort_order = Qt.SortOrder.AscendingOrder if self.current_sort_order == Qt.SortOrder.DescendingOrder else Qt.SortOrder.DescendingOrder # CAMBIO
        else:
            self.current_sort_column = logical_index
            if logical_index == self.COL_PERSONAJE:
                self.current_sort_order = Qt.SortOrder.AscendingOrder # CAMBIO
            else: 
                self.current_sort_order = Qt.SortOrder.DescendingOrder # CAMBIO
        self.populate_table()

    def populate_table(self):
        if self.parent_table_window.dataframe is None or self.parent_table_window.dataframe.empty:
             self.table_widget.setRowCount(0)
             return

        character_counts = self.parent_table_window.dataframe['PERSONAJE'].value_counts()
        items_to_sort = list(character_counts.items())

        if self.current_sort_column == self.COL_PERSONAJE:
            items_to_sort.sort(key=lambda item: str(item[0]).lower(), # Asegurar que item[0] sea string
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder)) # CAMBIO
        elif self.current_sort_column == self.COL_INTERVENCIONES:
            items_to_sort.sort(key=lambda item: item[1], 
                               reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder)) # CAMBIO

        self.table_widget.setRowCount(len(items_to_sort))
        self.table_widget.blockSignals(True)
        for row, (character, count) in enumerate(items_to_sort):
            self.set_table_item(row, self.COL_PERSONAJE, str(character)) # Asegurar string
            self.set_table_item(row, self.COL_INTERVENCIONES, str(count))
        self.table_widget.blockSignals(False)

        self.table_widget.horizontalHeader().setSortIndicator(
            self.current_sort_column, 
            self.current_sort_order
        )
        self.table_widget.horizontalHeader().setSortIndicatorShown(True)

    def set_table_item(self, row, column, value):
        item = QTableWidgetItem(value)
        if column == self.COL_PERSONAJE:
            # Qt.UserRole -> Qt.ItemDataRole.UserRole
            item.setData(Qt.ItemDataRole.UserRole, value) # CAMBIO
        
        if column == self.COL_INTERVENCIONES:
            # Qt.ItemIsEditable -> Qt.ItemFlag.ItemIsEditable
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) # CAMBIO para quitar flag
            # Qt.AlignCenter -> Qt.AlignmentFlag.AlignCenter
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter) # CAMBIO

        self.table_widget.setItem(row, column, item)

    def on_item_changed(self, item: QTableWidgetItem): # CAMBIO: tipo item
        if item.column() == self.COL_PERSONAJE:
            # Qt.UserRole -> Qt.ItemDataRole.UserRole
            old_name = item.data(Qt.ItemDataRole.UserRole) # CAMBIO
            new_name = item.text().strip()
            
            if not new_name:
                QMessageBox.warning(self, "Entrada no válida", "El nombre del personaje no puede estar vacío.")
                self.table_widget.blockSignals(True)
                item.setText(old_name)
                self.table_widget.blockSignals(False)
                return
            
            if old_name and old_name != new_name:
                all_character_names = [
                    self.table_widget.item(r, self.COL_PERSONAJE).text()
                    for r in range(self.table_widget.rowCount())
                    if r != item.row()
                ]
                if new_name.lower() in [name.lower() for name in all_character_names]:
                    QMessageBox.warning(self, "Nombre Duplicado", 
                                        f"El nombre de personaje '{new_name}' ya existe. "
                                        "Por favor, elige un nombre diferente.")
                    self.table_widget.blockSignals(True)
                    item.setText(old_name)
                    self.table_widget.blockSignals(False)
                    return

                self.update_character_name(old_name, new_name)
                item.setData(Qt.ItemDataRole.UserRole, new_name) # CAMBIO
                QMessageBox.information(
                    self, "Nombre Actualizado",
                    f"'{old_name}' ha sido cambiado a '{new_name}' en el guion."
                )

    def update_character_name(self, old_name, new_name):
        try:
            self.parent_table_window.update_character_name(old_name, new_name)
        except AttributeError: # Puede ser que parent_table_window no esté completamente listo
            QMessageBox.warning(self, "Error", "No se pudo actualizar el nombre del personaje en la tabla principal (referencia inválida).")

    def showEvent(self, event):
        super().showEvent(event)
        self.populate_table()