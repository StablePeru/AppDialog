# guion_editor/widgets/excel_mapping_dialog.py
import pandas as pd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView,
    QGridLayout, QLabel, QComboBox, QPushButton, QHBoxLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt

class ExcelMappingDialog(QDialog):
    # Columnas que nuestra aplicación espera. El orden aquí define el orden en el diálogo.
    REQUIRED_COLUMNS = ['SCENE', 'IN', 'OUT', 'PERSONAJE', 'DIÁLOGO', 'EUSKERA', 'OHARRAK']

    def __init__(self, raw_dataframe: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.raw_df = raw_dataframe
        self.setWindowTitle("Asistente de Importación de Excel")
        self.setMinimumSize(800, 600)
        
        self.mapping_combos: dict[str, QComboBox] = {}
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Etiqueta de instrucciones
        main_layout.addWidget(QLabel(
            "El archivo Excel no tiene el formato esperado. Por favor, asigne las columnas de su archivo (derecha) "
            "a las columnas requeridas por la aplicación (izquierda)."
        ))

        # 2. Layout de mapeo
        mapping_layout = QGridLayout()
        mapping_layout.setColumnStretch(1, 1) # Estirar la columna de los ComboBox

        excel_columns = ["--- NO ASIGNAR / USAR VALOR POR DEFECTO ---"] + list(self.raw_df.columns)
        
        for row_idx, required_col in enumerate(self.REQUIRED_COLUMNS):
            label = QLabel(f"{required_col}:")
            combo = QComboBox()
            combo.addItems(excel_columns)
            
            # Intentar adivinar la columna correcta
            best_guess_idx = 0 # Por defecto "NO ASIGNAR"
            for i, excel_col in enumerate(excel_columns):
                if str(required_col).lower() == str(excel_col).lower():
                    best_guess_idx = i
                    break
            combo.setCurrentIndex(best_guess_idx)

            mapping_layout.addWidget(label, row_idx, 0)
            mapping_layout.addWidget(combo, row_idx, 1)
            self.mapping_combos[required_col] = combo
            
        main_layout.addLayout(mapping_layout)

        # 3. Vista previa de la tabla
        main_layout.addWidget(QLabel("Vista previa de los datos importados:"))
        preview_table = QTableWidget()
        preview_table.setRowCount(min(50, len(self.raw_df))) # Mostrar hasta 50 filas
        preview_table.setColumnCount(len(self.raw_df.columns))
        preview_table.setHorizontalHeaderLabels(self.raw_df.columns.astype(str))
        
        for row in range(preview_table.rowCount()):
            for col in range(preview_table.columnCount()):
                item_value = self.raw_df.iat[row, col]
                preview_table.setItem(row, col, QTableWidgetItem(str(item_value)))

        preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        main_layout.addWidget(preview_table)

        # 4. Botones de Aceptar/Cancelar
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def get_mapping(self) -> dict[str, str]:
        """Devuelve el mapeo seleccionado por el usuario."""
        mapping = {}
        for required_col, combo in self.mapping_combos.items():
            selected_excel_col = combo.currentText()
            mapping[required_col] = selected_excel_col
        return mapping